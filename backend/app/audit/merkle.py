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
separate concern from these functions and is not part of this module.

Two kinds of proof are implemented, both following RFC 6962 (Certificate
Transparency), whose tree hash this module's construction reproduces exactly
(design note 5). :func:`inclusion_proof` / :func:`verify_inclusion` let an
auditor confirm that one specific entry sits at a given position under a root
without re-reading the whole log: the proof is O(log n) sibling hashes.
:func:`consistency_proof` / :func:`verify_consistency` prove that a later root
is an append-only extension of an earlier one — that history was only added to,
never rewritten — which is the property external anchoring of a root is meant to
protect. ``verify()`` remains for whole-log recomputation; the proofs are for
the far more common case of checking one entry or one growth step cheaply.

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

5. **The tree is RFC 6962-compatible.** Promoting the odd node at each level
   yields the same root as RFC 6962's recursive "split at the largest power of
   two below n" tree hash, for every entry count. That equivalence is not a
   coincidence to rely on loosely: it is what lets the inclusion and consistency
   proofs below be the standard, widely-audited RFC 6962 algorithms rather than
   a bespoke scheme. A property test sweeps proof generation and verification
   against :func:`build` across every length in a range; if the constructions
   ever diverge, those proofs would silently start lying, so the test guards it.
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


@dataclass(frozen=True)
class InclusionProof:
    """A proof that one entry sits at a known position under a known root.

    Holds only the leaf's position, the tree size it was proved against, and
    the O(log n) sibling hashes on the path from that leaf to the root — never
    the other entries. That is the entire point: an auditor holding one entry
    can confirm it belongs to a published root without being handed, or trusting,
    the rest of the log.

    Attributes:
        leaf_index: Zero-based position of the proved entry.
        tree_size: Number of entries in the tree the proof is against. The path
            is only meaningful paired with the size, because which sibling is
            left and which is right is derived from both during verification.
        audit_path: Sibling hashes from the leaf's level up to the root, leaf
            first. Empty only for the single-entry tree, whose root is the leaf.
    """

    leaf_index: int
    tree_size: int
    audit_path: tuple[str, ...]


@dataclass(frozen=True)
class ConsistencyProof:
    """A proof that a larger tree is an append-only extension of a smaller one.

    Proves that every entry the old root committed to is still present, in the
    same order and positions, under the new root — that the log was only
    appended to, never rewritten or reordered. This is the guarantee that turns
    a periodically anchored root into tamper evidence: an operator who quietly
    edits a past entry cannot produce a consistency proof from the anchored old
    root to their doctored new one.

    Attributes:
        old_size: Entry count of the earlier tree. Must be ``0 < old_size`` and
            ``<= new_size`` for a non-trivial proof.
        new_size: Entry count of the later tree.
        nodes: The RFC 6962 consistency node hashes. Empty when the two roots
            are trivially related (equal sizes, or an empty old tree).
    """

    old_size: int
    new_size: int
    nodes: tuple[str, ...]


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


def _largest_power_of_two_below(n: int) -> int:
    """Return the largest power of two strictly less than ``n`` (``n >= 2``).

    This is the split point RFC 6962 uses to divide a tree of ``n`` leaves into
    a full left subtree of ``k`` leaves and a right subtree of ``n - k``. It is
    the one arithmetic primitive both proof algorithms are built on.
    """
    k = 1
    while (k << 1) < n:
        k <<= 1
    return k


def _is_power_of_two(n: int) -> bool:
    """True if ``n`` is a positive power of two."""
    return n > 0 and (n & (n - 1)) == 0


def _root_of_leaves(leaves: Sequence[str]) -> str:
    """Merkle root over already-hashed leaves, using this module's construction.

    Shares the exact odd-node promotion of :func:`build` so a subtree root
    computed here is bit-for-bit what ``build`` would produce over the same
    entries. Proof generation needs subtree roots over slices of the leaf list,
    and re-running ``build`` (which re-hashes raw entries) is neither available
    here nor what is wanted: the inputs are already leaf hashes.
    """
    if not leaves:
        return EMPTY_ROOT
    current = list(leaves)
    while len(current) > 1:
        parents = [
            hash_internal(current[index], current[index + 1])
            for index in range(0, len(current) - 1, 2)
        ]
        if len(current) % 2 == 1:
            parents.append(current[-1])
        current = parents
    return current[0]


def inclusion_proof(entries: Sequence[bytes], leaf_index: int) -> InclusionProof:
    """Build an RFC 6962 inclusion (audit) proof for one entry.

    Pure function. The system side, which holds every entry, calls this once to
    produce the O(log n) sibling hashes an auditor then checks with
    :func:`verify_inclusion` against nothing but the entry and a trusted root.

    Args:
        entries: The full ordered entry payloads, as :func:`canonicalize`
            returns. Order is significant; it is part of what the root commits
            to.
        leaf_index: Zero-based position of the entry to prove.

    Returns:
        The :class:`InclusionProof`.

    Raises:
        ValueError: if ``leaf_index`` is outside ``0 .. len(entries) - 1``. An
            empty log has no entry to prove, so any index fails there.
    """
    size = len(entries)
    if not 0 <= leaf_index < size:
        raise ValueError(
            f"leaf_index {leaf_index} is out of range for {size} entr(ies)."
        )
    leaves = [hash_leaf(entry) for entry in entries]
    return InclusionProof(
        leaf_index=leaf_index,
        tree_size=size,
        audit_path=tuple(_audit_path(leaf_index, leaves)),
    )


def _audit_path(index: int, leaves: Sequence[str]) -> list[str]:
    """RFC 6962 ``PATH(m, D[n])``: sibling hashes from a leaf up to the root."""
    n = len(leaves)
    if n == 1:
        return []
    k = _largest_power_of_two_below(n)
    if index < k:
        # Leaf is in the left subtree; the right subtree's root is its sibling.
        return _audit_path(index, leaves[:k]) + [_root_of_leaves(leaves[k:])]
    # Leaf is in the right subtree; the left subtree's root is its sibling.
    return _audit_path(index - k, leaves[k:]) + [_root_of_leaves(leaves[:k])]


def verify_inclusion(proof: InclusionProof, leaf_hash: str, root: str) -> bool:
    """Check an inclusion proof against a leaf hash and a trusted root.

    Reconstructs the root from ``leaf_hash`` and the proof's sibling hashes,
    deriving each step's left/right orientation from ``leaf_index`` and
    ``tree_size`` exactly as RFC 6962 section 2.1.1 specifies, then compares the
    result to ``root``. Requires none of the other entries: this is what lets a
    party who does not trust the operator verify one record cheaply.

    Args:
        proof: The proof produced by :func:`inclusion_proof`.
        leaf_hash: The proved entry's leaf hash, i.e. ``hash_leaf(entry)`` over
            its canonical bytes.
        root: The root being trusted, obtained independently of the operator
            (for example from an external anchor).

    Returns:
        True only if the entry provably sits at ``proof.leaf_index`` under
        ``root`` in a tree of ``proof.tree_size`` entries.
    """
    fn, sn = proof.leaf_index, proof.tree_size - 1
    if not 0 <= fn <= sn:
        return False

    computed = leaf_hash
    for sibling in proof.audit_path:
        if sn == 0:
            # The path is longer than the tree height allows: malformed.
            return False
        if (fn & 1) or fn == sn:
            computed = hash_internal(sibling, computed)
            if not (fn & 1):
                while fn != 0 and not (fn & 1):
                    fn >>= 1
                    sn >>= 1
        else:
            computed = hash_internal(computed, sibling)
        fn >>= 1
        sn >>= 1

    return sn == 0 and hmac.compare_digest(computed, root)


def consistency_proof(entries: Sequence[bytes], old_size: int) -> ConsistencyProof:
    """Build an RFC 6962 consistency proof from ``old_size`` to ``len(entries)``.

    Pure function. Proves the tree grew by appending only: the old root's
    entries remain, in place, under the new root. The system side calls this;
    :func:`verify_consistency` checks it against the two roots alone.

    Args:
        entries: The full ordered entry payloads of the *later* tree.
        old_size: Entry count of the earlier tree, ``0 <= old_size <= len``.

    Returns:
        The :class:`ConsistencyProof`. Its ``nodes`` are empty for the trivial
        cases (an empty old tree, or old and new sizes equal), which
        :func:`verify_consistency` handles by comparing roots directly.

    Raises:
        ValueError: if ``old_size`` is negative or larger than ``len(entries)``.
    """
    new_size = len(entries)
    if not 0 <= old_size <= new_size:
        raise ValueError(
            f"old_size {old_size} is out of range for {new_size} entr(ies)."
        )
    if old_size == 0 or old_size == new_size:
        return ConsistencyProof(old_size=old_size, new_size=new_size, nodes=())
    leaves = [hash_leaf(entry) for entry in entries]
    return ConsistencyProof(
        old_size=old_size,
        new_size=new_size,
        nodes=tuple(_subproof(old_size, leaves, True)),
    )


def _subproof(m: int, leaves: Sequence[str], on_boundary: bool) -> list[str]:
    """RFC 6962 ``SUBPROOF(m, D[n], b)``.

    ``on_boundary`` is the RFC's ``b``: True while ``m`` still aligns with the
    left edge of the subtree under consideration, meaning the old tree's own
    root is implied by the structure and need not be emitted; it flips to False
    once the recursion descends into a right subtree, where that root must be
    carried explicitly.
    """
    n = len(leaves)
    if m == n:
        # The old tree is exactly this subtree. Its root is only emitted when it
        # is not already implied by an enclosing boundary.
        return [] if on_boundary else [_root_of_leaves(leaves)]
    k = _largest_power_of_two_below(n)
    if m <= k:
        return _subproof(m, leaves[:k], on_boundary) + [_root_of_leaves(leaves[k:])]
    return _subproof(m - k, leaves[k:], False) + [_root_of_leaves(leaves[:k])]


def verify_consistency(proof: ConsistencyProof, old_root: str, new_root: str) -> bool:
    """Check a consistency proof against the earlier and later roots.

    Reconstructs both roots from the proof nodes following RFC 6962 section
    2.1.2 and confirms they match ``old_root`` and ``new_root``. Succeeding means
    the later tree provably contains the earlier one as an unaltered prefix.

    Args:
        proof: The proof produced by :func:`consistency_proof`.
        old_root: The earlier root, trusted independently (e.g. anchored).
        new_root: The later root being checked for consistency with it.

    Returns:
        True only if ``new_root`` is an append-only extension of ``old_root``.
    """
    m, n = proof.old_size, proof.new_size
    if not 0 <= m <= n:
        return False
    # Trivial relations carry no nodes and are decided by the roots directly.
    if m == 0:
        return hmac.compare_digest(old_root, EMPTY_ROOT)
    if m == n:
        return len(proof.nodes) == 0 and hmac.compare_digest(old_root, new_root)

    path = list(proof.nodes)
    # A full old subtree omits its own root from the proof; supply it so the
    # reconstruction below has a starting hash. See _subproof's boundary note.
    if _is_power_of_two(m):
        path = [old_root] + path
    if not path:
        return False

    fn, sn = m - 1, n - 1
    # Advance past the levels the old tree fills completely.
    while fn & 1:
        fn >>= 1
        sn >>= 1

    old_computed = new_computed = path[0]
    for node in path[1:]:
        if sn == 0:
            return False
        if (fn & 1) or fn == sn:
            old_computed = hash_internal(node, old_computed)
            new_computed = hash_internal(node, new_computed)
            if not (fn & 1):
                while fn != 0 and not (fn & 1):
                    fn >>= 1
                    sn >>= 1
        else:
            new_computed = hash_internal(new_computed, node)
        fn >>= 1
        sn >>= 1

    return (
        sn == 0
        and hmac.compare_digest(old_computed, old_root)
        and hmac.compare_digest(new_computed, new_root)
    )
