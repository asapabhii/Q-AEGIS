"""Merkle tree construction and verification, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

``build()`` and ``verify()`` are pure functions with no side effects: no I/O, no
logging, no database access, no mutation of their arguments. That is a
requirement, not a style preference. ``PRD.md`` FR-7 requires verification to be
runnable by a party that does not trust the system's operators, which means
verification cannot depend on any state this system controls, and must never
consult a stored "valid" flag. Given the same entries, these functions produce
the same root on any machine, in any process, in any order of invocation.

This module is NOT a stub. The tree construction and verification implemented
here are complete and are the intended implementation.

Scope note: database-level append-only enforcement for ``audit_log`` (the
Postgres trigger rejecting UPDATE and DELETE required by ``SPEC.md`` 3.8) is a
separate concern from these functions and is not part of this module. Inclusion
proofs, which let an auditor verify one entry without re-reading the whole log,
are also not implemented yet, ``verify()`` currently recomputes the full root.

Design choices worth not undoing:

1. **Domain separation.** Leaves are hashed with a ``0x00`` prefix and internal
   nodes with ``0x01``, following RFC 6962. Without this, an attacker could
   present an internal node's hash as though it were a leaf, because the two
   would be computed identically. This is a second-preimage defense.

2. **Odd nodes are promoted, not duplicated.** When a level has an odd node
   count, the last node is carried up unchanged rather than hashed against
   itself. Duplicating the final node is the widely-copied Bitcoin approach and
   it introduces a malleability flaw (the CVE-2012-2459 class of bug), where two
   distinct entry lists can produce an identical root. For a log whose entire
   purpose is detecting alteration, two inputs sharing a root is precisely the
   property that must not exist.

4. **``build()`` and ``extend_frontier()`` must always agree.** There are two
   ways to reach a root here, one reading every entry and one carrying forward
   O(log n) state. They are not alternatives to pick between: the incremental
   path exists so appending to a log is not quadratic, and the full path exists
   so a verifier never has to trust carried-forward state. A property test
   asserts they produce identical roots across a range of lengths. If a change
   makes them diverge, the change is wrong, not the test.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

#: Prefix applied when hashing a leaf. See design note 1 in the module docstring.
LEAF_PREFIX = b"\x00"

#: Prefix applied when hashing an internal node.
NODE_PREFIX = b"\x01"

#: Root of the empty tree, defined as the hash of the empty string per RFC 6962.
#:
#: An empty log needs a well-defined root so that "the log is empty" is itself a
#: verifiable claim. Raising on empty input instead would leave a fresh,
#: never-written-to log in an unverifiable state.
EMPTY_ROOT = hashlib.sha256(b"").hexdigest()


@dataclass(frozen=True)
class MerkleTree:
    """A built Merkle tree.

    Frozen because a built tree is a snapshot of a specific entry sequence.
    Mutating one would make its ``root`` disagree with its ``levels``.

    Attributes:
        root: Hex-encoded SHA-256 root hash.
        leaf_count: Number of entries the tree was built from.
        levels: Tree levels from leaves upward. ``levels[0]`` holds the leaf
            hashes; the last level holds the single root. Retained so a
            verifier can inspect intermediate state rather than being handed
            only a root to trust.
    """

    root: str
    leaf_count: int
    levels: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Subtree:
    """One complete subtree in a frontier.

    Attributes:
        size: Number of leaves beneath it. Always a power of two, because only a
            complete subtree can be summarized by a single hash.
        hash: Hex-encoded root hash of that subtree.
    """

    size: int
    hash: str


@dataclass(frozen=True)
class Frontier:
    """The O(log n) state an append needs, instead of every prior entry.

    Frozen, and :func:`extend_frontier` returns a new one rather than mutating.
    A frontier is a claim about a specific entry sequence; a mutable one could be
    advanced past the entries it was read alongside.

    Attributes:
        subtrees: Complete subtrees covering the entries so far, left to right,
            with strictly decreasing sizes. Their sizes are the set bits of the
            entry count, so a chain of 11 entries holds subtrees of 8, 2, and 1.
    """

    subtrees: tuple[Subtree, ...] = ()

    @property
    def leaf_count(self) -> int:
        """Number of entries this frontier covers."""
        return sum(subtree.size for subtree in self.subtrees)


#: Frontier over no entries. The starting point for a chain's first append.
EMPTY_FRONTIER = Frontier()


@dataclass(frozen=True)
class VerificationResult:
    """The outcome of a verification run.

    Both roots are returned, not just the boolean, so a failure report can show
    what was expected against what the entries actually produce. A bare
    ``False`` gives an auditor nothing to act on.

    Attributes:
        is_valid: True only if the recomputed root matches the expected root.
        computed_root: Root recomputed from the supplied entries.
        expected_root: Root that was claimed.
        leaf_count: Number of entries verified.
    """

    is_valid: bool
    computed_root: str
    expected_root: str
    leaf_count: int


def canonicalize(entry: Mapping[str, Any]) -> bytes:
    """Serialize a mapping to deterministic bytes suitable for hashing.

    Hashing is only meaningful if the same logical entry always serializes
    identically. Python dict iteration order reflects insertion order, so two
    equal mappings built differently would otherwise hash differently and a
    clean log would fail verification for no real reason.

    Keys are sorted, separators are fixed to remove incidental whitespace, and
    non-ASCII characters are preserved as UTF-8 rather than escaped.

    Args:
        entry: The audit entry as a mapping.

    Returns:
        UTF-8 encoded canonical JSON.

    Raises:
        TypeError: if ``entry`` contains values that are not JSON-serializable.
            Left to propagate deliberately: silently coercing an unexpected type
            to a string would let two different values hash the same.
    """
    return json.dumps(
        entry,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def hash_leaf(entry: bytes) -> str:
    """Hash one leaf, with the leaf domain-separation prefix applied."""
    return hashlib.sha256(LEAF_PREFIX + entry).hexdigest()


def hash_internal(left: str, right: str) -> str:
    """Hash two child hashes into their parent, with the node prefix applied.

    Args:
        left: Hex-encoded left child hash.
        right: Hex-encoded right child hash.

    Returns:
        Hex-encoded parent hash.

    Raises:
        ValueError: if either input is not valid hex. Child hashes are converted
            from hex back to raw bytes before hashing so the tree operates on
            32-byte digests rather than their 64-character text representation.
    """
    return hashlib.sha256(
        NODE_PREFIX + bytes.fromhex(left) + bytes.fromhex(right)
    ).hexdigest()


def build(entries: Sequence[bytes]) -> MerkleTree:
    """Build a Merkle tree over ``entries``.

    Pure function: ``entries`` is not modified, and nothing outside the returned
    value is touched.

    Args:
        entries: Ordered entry payloads. Order is significant, it is part of
            what the root commits to, so a reordered log fails verification.
            Use :func:`canonicalize` to convert mappings to bytes first.

    Returns:
        The built :class:`MerkleTree`. For an empty sequence, a tree with
        ``root == EMPTY_ROOT``, ``leaf_count == 0``, and one empty level.
    """
    leaves = [hash_leaf(entry) for entry in entries]

    if not leaves:
        return MerkleTree(root=EMPTY_ROOT, leaf_count=0, levels=((),))

    levels: list[tuple[str, ...]] = [tuple(leaves)]
    current: list[str] = leaves

    while len(current) > 1:
        parents: list[str] = [
            hash_internal(current[index], current[index + 1])
            for index in range(0, len(current) - 1, 2)
        ]
        if len(current) % 2 == 1:
            # Odd node out: promote unchanged. See design note 2 in the module
            # docstring for why this is not hashed against itself.
            parents.append(current[-1])
        levels.append(tuple(parents))
        current = parents

    return MerkleTree(
        root=current[0],
        leaf_count=len(leaves),
        levels=tuple(levels),
    )


def extend_frontier(frontier: Frontier, entry: bytes) -> Frontier:
    """Return the frontier covering ``frontier``'s entries followed by ``entry``.

    Pure function. This is the append path's answer to a log that only grows:
    computing a root by reading every prior entry costs O(n) per append and so
    O(n^2) over the life of a chain, and the audit log is written to by every
    decision the system makes.

    How it stays correct. A tree of ``n`` leaves under this module's construction
    decomposes into exactly one complete subtree per set bit of ``n``, largest
    first, and that set of subtree roots is all the state an append needs. Adding
    a leaf pushes a subtree of size one, then merges equal-sized neighbours while
    the two rightmost match, which is binary increment carried out over hashes.
    Design note 4 in the module docstring covers why this must agree with
    :func:`build`, and a property test enforces it.

    Args:
        frontier: Frontier over the entries so far. Use :data:`EMPTY_FRONTIER`
            for an empty chain.
        entry: The new entry's canonical bytes, as :func:`canonicalize` returns.

    Returns:
        A new frontier. ``frontier`` is not modified.
    """
    subtrees = list(frontier.subtrees) + [Subtree(size=1, hash=hash_leaf(entry))]

    while len(subtrees) > 1 and subtrees[-1].size == subtrees[-2].size:
        right = subtrees.pop()
        left = subtrees.pop()
        subtrees.append(
            Subtree(
                size=left.size + right.size,
                hash=hash_internal(left.hash, right.hash),
            )
        )

    return Frontier(subtrees=tuple(subtrees))


def root_of(frontier: Frontier) -> str:
    """Return the Merkle root a frontier commits to.

    The subtrees are folded from the right, which is what promoting an odd node
    means expressed over subtree roots: a smaller trailing subtree is combined
    into what sits to its left rather than being padded out to match it.

    Args:
        frontier: Any frontier, including :data:`EMPTY_FRONTIER`.

    Returns:
        Hex-encoded root. :data:`EMPTY_ROOT` for an empty frontier.
    """
    if not frontier.subtrees:
        return EMPTY_ROOT

    root = frontier.subtrees[-1].hash
    for subtree in reversed(frontier.subtrees[:-1]):
        root = hash_internal(subtree.hash, root)
    return root


def frontier_to_json(frontier: Frontier) -> list[list[Any]]:
    """Return ``frontier`` as JSON-safe data, for storage beside an entry.

    Each subtree becomes ``[size, hash]``. Sizes are stored rather than inferred
    from a separate leaf count so the value is self-describing: it can be
    validated on its own, and a chain's length is the sum of them.
    """
    return [[subtree.size, subtree.hash] for subtree in frontier.subtrees]


def frontier_from_json(raw: Any) -> Frontier:
    """Rebuild a frontier from what :func:`frontier_to_json` produced.

    Validates rather than trusting. This value comes back out of the database,
    and a malformed or tampered frontier would otherwise produce a plausible but
    wrong root for every entry appended after it. Cheap to check here; expensive
    to discover later.

    Args:
        raw: The stored value.

    Returns:
        The frontier it represents.

    Raises:
        ValueError: if the structure, sizes, or hashes are not what this module
            writes. Sizes must be descending powers of two, since any other
            shape cannot have come from :func:`extend_frontier`.
    """
    if not isinstance(raw, list):
        raise ValueError(f"Frontier must be a list, got {type(raw).__name__}.")

    subtrees: list[Subtree] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("Each frontier element must be a [size, hash] pair.")
        size, digest = item
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise ValueError(f"Frontier subtree size must be a positive int: {size!r}.")
        if size & (size - 1):
            raise ValueError(f"Frontier subtree size must be a power of two: {size}.")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Frontier subtree hash must be a 64-character hex digest.")
        try:
            bytes.fromhex(digest)
        except ValueError:
            raise ValueError(
                "Frontier subtree hash must be a 64-character hex digest."
            ) from None
        subtrees.append(Subtree(size=size, hash=digest))

    for left, right in zip(subtrees, subtrees[1:]):
        if left.size <= right.size:
            raise ValueError(
                "Frontier subtree sizes must strictly decrease: "
                f"{left.size} is not greater than {right.size}."
            )

    return Frontier(subtrees=tuple(subtrees))


def verify(entries: Sequence[bytes], expected_root: str) -> VerificationResult:
    """Recompute the root from ``entries`` and compare it to ``expected_root``.

    Detects any alteration to any entry, any reordering, any insertion, and any
    truncation, because all of those change the recomputed root.

    Pure function. It does not read a stored validity flag, and deliberately
    takes no database handle or connection: an auditor can call this with
    entries exported from the system and a root obtained independently, which
    is what makes ``PRD.md`` FR-7's independent verification possible.

    Args:
        entries: The entries to verify, in their original order.
        expected_root: The hex-encoded root being claimed.

    Returns:
        A :class:`VerificationResult`.
    """
    computed = build(entries)
    return VerificationResult(
        # Constant-time comparison. The timing side channel is not a realistic
        # attack on a public root hash, but comparing digests this way is the
        # correct default and costs nothing.
        is_valid=hmac.compare_digest(computed.root, expected_root),
        computed_root=computed.root,
        expected_root=expected_root,
        leaf_count=computed.leaf_count,
    )
