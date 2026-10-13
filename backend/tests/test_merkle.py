"""Tests for the Merkle tree, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

``AGENTS.md`` requires explicit tampered-entry and odd-count-of-leaves cases
here, not just a clean-chain verification test. Both are covered below, and the
tampering cases are parameterized across odd and even leaf counts because the
promoted odd node follows a different path up the tree than a paired node does.

``PRD.md`` Section 8 sets zero tolerance for false negatives on tamper
detection, so these tests assert detection of alteration, reordering,
insertion, and truncation independently rather than trusting one representative
case to cover all four.
"""

import hashlib
from dataclasses import replace

import pytest

from app.audit.merkle import (
    EMPTY_FRONTIER,
    EMPTY_ROOT,
    LEAF_PREFIX,
    NODE_PREFIX,
    build,
    canonicalize,
    consistency_proof,
    extend_frontier,
    frontier_from_json,
    frontier_to_json,
    hash_internal,
    hash_leaf,
    inclusion_proof,
    root_of,
    verify,
    verify_consistency,
    verify_inclusion,
)


def frontier_over(count: int):
    """Return the frontier reached by appending ``count`` entries one at a time."""
    frontier = EMPTY_FRONTIER
    for entry in entries(count):
        frontier = extend_frontier(frontier, entry)
    return frontier


def entries(count: int) -> list[bytes]:
    """Build ``count`` distinct, deterministic entry payloads."""
    return [f"audit-entry-{index}".encode("utf-8") for index in range(count)]


# --------------------------------------------------------------------------
# build(): structure and determinism
# --------------------------------------------------------------------------


def test_build_empty_returns_defined_empty_root() -> None:
    """An empty log has a defined, verifiable root rather than being an error."""
    tree = build([])
    assert tree.root == EMPTY_ROOT
    assert tree.leaf_count == 0
    assert tree.levels == ((),)


def test_build_single_entry_root_is_the_leaf_hash() -> None:
    """A one-entry tree's root is that entry's leaf hash, with no node hashing."""
    payload = b"only-entry"
    tree = build([payload])
    assert tree.root == hash_leaf(payload)
    assert tree.leaf_count == 1
    assert tree.levels == ((hash_leaf(payload),),)


def test_build_is_deterministic_across_calls() -> None:
    """Same entries, same root. This is what makes verification portable."""
    payloads = entries(6)
    assert build(payloads).root == build(payloads).root


def test_build_does_not_mutate_its_input() -> None:
    """build() is pure: the caller's sequence is untouched."""
    payloads = entries(5)
    snapshot = list(payloads)
    build(payloads)
    assert payloads == snapshot


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17])
def test_build_reports_leaf_count_and_terminates_in_single_root(count: int) -> None:
    """Every size collapses to exactly one root, odd counts included."""
    tree = build(entries(count))
    assert tree.leaf_count == count
    assert len(tree.levels[0]) == count
    assert len(tree.levels[-1]) == 1
    assert tree.levels[-1][0] == tree.root


def test_build_three_entries_promotes_the_odd_leaf() -> None:
    """The odd leaf is carried up unchanged, not hashed against itself.

    Asserted on the level structure directly, because this is the specific
    behavior that the malleability test below depends on.
    """
    payloads = entries(3)
    leaves = [hash_leaf(payload) for payload in payloads]
    tree = build(payloads)

    expected_pair = hash_internal(leaves[0], leaves[1])
    assert tree.levels[0] == tuple(leaves)
    assert tree.levels[1] == (expected_pair, leaves[2])
    assert tree.root == hash_internal(expected_pair, leaves[2])


# --------------------------------------------------------------------------
# Tamper detection: the required cases
# --------------------------------------------------------------------------


@pytest.mark.parametrize("count", [2, 3, 4, 5, 7, 8, 9])
@pytest.mark.parametrize("position", ["first", "middle", "last"])
def test_verify_detects_a_tampered_entry(count: int, position: str) -> None:
    """A single altered entry fails verification, at any position, any size.

    The ``last`` position matters disproportionately: at odd levels that entry
    is promoted rather than paired, so it travels a different path to the root
    and a flaw in the promotion branch would hide tampering there specifically.
    """
    original = entries(count)
    root = build(original).root

    index = {"first": 0, "middle": count // 2, "last": count - 1}[position]
    tampered = list(original)
    tampered[index] = tampered[index] + b"-TAMPERED"

    result = verify(tampered, root)
    assert result.is_valid is False
    assert result.computed_root != root
    assert result.expected_root == root


def test_verify_detects_a_single_flipped_bit() -> None:
    """Detection does not require a large edit; one bit is enough."""
    original = [b"entry-a", b"entry-b", b"entry-c"]
    root = build(original).root

    mutated = bytearray(original[1])
    mutated[0] ^= 0b0000_0001
    tampered = [original[0], bytes(mutated), original[2]]

    assert verify(tampered, root).is_valid is False


def test_verify_detects_reordering() -> None:
    """Order is part of what the root commits to."""
    original = entries(4)
    root = build(original).root
    reordered = [original[1], original[0], original[2], original[3]]
    assert reordered != original
    assert verify(reordered, root).is_valid is False


def test_verify_detects_an_inserted_entry() -> None:
    """Appending to a sealed log changes the root."""
    original = entries(4)
    root = build(original).root
    assert verify([*original, b"injected"], root).is_valid is False


def test_verify_detects_a_removed_entry() -> None:
    """Truncating the log changes the root."""
    original = entries(4)
    root = build(original).root
    assert verify(original[:-1], root).is_valid is False


def test_verify_accepts_an_untampered_log() -> None:
    """The clean case still passes, and reports matching roots."""
    payloads = entries(7)
    root = build(payloads).root
    result = verify(payloads, root)
    assert result.is_valid is True
    assert result.computed_root == root
    assert result.expected_root == root
    assert result.leaf_count == 7


def test_verify_rejects_a_wrong_root_of_the_correct_shape() -> None:
    """A plausible but incorrect root is rejected, not accepted on shape."""
    payloads = entries(4)
    wrong_root = hashlib.sha256(b"not-the-root").hexdigest()
    result = verify(payloads, wrong_root)
    assert result.is_valid is False
    assert len(result.expected_root) == len(result.computed_root)


def test_verify_of_empty_log_against_empty_root_passes() -> None:
    """An empty log is verifiable, so "the log is empty" is a provable claim."""
    assert verify([], EMPTY_ROOT).is_valid is True


# --------------------------------------------------------------------------
# Design guarantees that must not silently regress
# --------------------------------------------------------------------------


def test_odd_leaf_is_not_duplicated_so_roots_stay_unambiguous() -> None:
    """Two distinct entry lists must never share a root.

    Regression test for the CVE-2012-2459 class of Merkle malleability. Under
    the common "duplicate the last node" construction, a three-entry log and a
    four-entry log whose last entry repeats produce an identical root, meaning
    an altered log could present a matching root. Promotion avoids that, and
    this test fails if anyone reintroduces duplication.
    """
    three = entries(3)
    four_with_repeat = [*three, three[-1]]
    assert build(three).root != build(four_with_repeat).root


def test_leaf_and_internal_hashes_are_domain_separated() -> None:
    """An internal node's hash cannot be passed off as a leaf's, or vice versa.

    Without the differing prefixes both would be a bare SHA-256 over the same
    bytes, which is a second-preimage weakness.
    """
    left = hash_leaf(b"left")
    right = hash_leaf(b"right")
    parent = hash_internal(left, right)

    concatenated = bytes.fromhex(left) + bytes.fromhex(right)
    assert parent != hash_leaf(concatenated)
    assert parent == hashlib.sha256(NODE_PREFIX + concatenated).hexdigest()
    assert hash_leaf(b"x") == hashlib.sha256(LEAF_PREFIX + b"x").hexdigest()
    assert LEAF_PREFIX != NODE_PREFIX


def test_hash_internal_rejects_non_hex_input() -> None:
    """Child hashes are real digests; malformed input fails loudly."""
    with pytest.raises(ValueError):
        hash_internal("not-hex", hash_leaf(b"ok"))


def test_distinct_entries_produce_distinct_leaf_hashes() -> None:
    """Sanity check that leaf hashing is actually content-dependent."""
    assert hash_leaf(b"a") != hash_leaf(b"b")


# --------------------------------------------------------------------------
# canonicalize()
# --------------------------------------------------------------------------


def test_canonicalize_is_key_order_independent() -> None:
    """Equal mappings hash equal regardless of how they were built.

    Without this, a clean log could fail verification purely because a dict was
    constructed in a different order on the verifying machine.
    """
    first = canonicalize({"action": "classify", "document_id": 7, "actor": "abhinav"})
    second = canonicalize({"actor": "abhinav", "document_id": 7, "action": "classify"})
    assert first == second


def test_canonicalize_distinguishes_different_values() -> None:
    """Different content must not canonicalize to the same bytes."""
    assert canonicalize({"decision": "allow"}) != canonicalize({"decision": "deny"})


def test_canonicalize_distinguishes_types() -> None:
    """A string "7" and an integer 7 are different facts and must hash apart."""
    assert canonicalize({"count": 7}) != canonicalize({"count": "7"})


def test_canonicalize_omits_incidental_whitespace() -> None:
    """Compact separators, so formatting cannot change a hash."""
    assert canonicalize({"a": 1, "b": 2}) == b'{"a":1,"b":2}'


def test_canonicalize_preserves_non_ascii_as_utf8() -> None:
    """Non-ASCII is encoded, not escaped, so entries round-trip readably."""
    assert canonicalize({"name": "Sukhmani Kaur"}) == b'{"name":"Sukhmani Kaur"}'
    assert "\\u" not in canonicalize({"note": "reviewed"}).decode("utf-8")


def test_canonicalize_rejects_unserializable_values() -> None:
    """An unexpected type fails loudly rather than being coerced to a string."""
    with pytest.raises(TypeError):
        canonicalize({"when": object()})


def test_canonicalized_entries_build_and_verify_end_to_end() -> None:
    """The intended usage: canonicalize mappings, then build and verify."""
    log = [
        {"seq": 1, "event": "document.uploaded", "document_id": "doc-1"},
        {"seq": 2, "event": "classification.recorded", "label": "RESTRICTED"},
        {"seq": 3, "event": "policy.evaluated", "rule_id": None},
    ]
    payloads = [canonicalize(entry) for entry in log]
    root = build(payloads).root

    assert verify(payloads, root).is_valid is True

    log[1]["label"] = "PUBLIC"
    tampered = [canonicalize(entry) for entry in log]
    assert verify(tampered, root).is_valid is False


# --------------------------------------------------------------------------
# The incremental frontier
#
# Design note 4 in the module docstring: the incremental path exists so appending
# is not quadratic, and it is only safe while it agrees with build() exactly. The
# first test below is the one that enforces that, and it is the reason the rest of
# this section can be read as describing an optimisation rather than a second,
# separately-trusted implementation.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("count", range(0, 35))
def test_frontier_root_matches_a_full_rebuild(count: int) -> None:
    """The two paths to a root must never disagree, at any length.

    Swept across every length in the range rather than sampled, because the tree's
    shape changes with the binary representation of the leaf count: powers of two,
    one past a power of two, and one short of one all merge differently.
    """
    assert root_of(frontier_over(count)) == build(entries(count)).root


@pytest.mark.parametrize("count", [1, 2, 3, 8, 11, 16, 100])
def test_frontier_leaf_count_tracks_the_entries_added(count: int) -> None:
    """The frontier knows how many entries it covers, without a separate counter."""
    assert frontier_over(count).leaf_count == count


def test_frontier_holds_one_subtree_per_set_bit() -> None:
    """11 entries decompose into subtrees of 8, 2, and 1.

    This is what keeps the carried state O(log n) rather than O(n), so it is
    asserted directly instead of being left as a comment.
    """
    assert [subtree.size for subtree in frontier_over(11).subtrees] == [8, 2, 1]


def test_frontier_of_a_power_of_two_collapses_to_one_subtree() -> None:
    """A full tree needs exactly one hash carried forward."""
    subtrees = frontier_over(16).subtrees
    assert len(subtrees) == 1
    assert subtrees[0].size == 16


def test_empty_frontier_root_is_the_empty_root() -> None:
    """An empty chain agrees with build([]) too, not just non-empty ones."""
    assert root_of(EMPTY_FRONTIER) == EMPTY_ROOT
    assert EMPTY_FRONTIER.leaf_count == 0


def test_extend_frontier_does_not_mutate_its_input() -> None:
    """Frozen and returned fresh, so a caller cannot advance a frontier it shares."""
    original = frontier_over(5)
    before = original.subtrees

    extend_frontier(original, b"another-entry")

    assert original.subtrees == before


# --------------------------------------------------------------------------
# Storing and reloading a frontier
# --------------------------------------------------------------------------


@pytest.mark.parametrize("count", [0, 1, 3, 11, 32])
def test_frontier_survives_a_json_round_trip(count: int) -> None:
    """It is stored as jsonb, so it has to come back as what went in."""
    frontier = frontier_over(count)
    assert frontier_from_json(frontier_to_json(frontier)) == frontier


def test_stored_frontier_is_self_describing() -> None:
    """Sizes travel with the hashes, so the value needs no external leaf count."""
    assert frontier_to_json(frontier_over(3)) == [
        [2, frontier_over(3).subtrees[0].hash],
        [1, frontier_over(3).subtrees[1].hash],
    ]


@pytest.mark.parametrize(
    "raw",
    [
        {"not": "a list"},
        [[2]],
        [[2, "aa" * 32, "extra"]],
        [["2", "aa" * 32]],
        [[True, "aa" * 32]],
        [[0, "aa" * 32]],
        [[-2, "aa" * 32]],
        [[3, "aa" * 32]],
        [[2, "short"]],
        [[2, "zz" * 32]],
        [[2, 12345]],
        [[1, "aa" * 32], [2, "bb" * 32]],
        [[2, "aa" * 32], [2, "bb" * 32]],
    ],
    ids=[
        "not-a-list",
        "missing-hash",
        "too-many-fields",
        "size-as-string",
        "size-as-bool",
        "size-zero",
        "size-negative",
        "size-not-a-power-of-two",
        "hash-too-short",
        "hash-not-hex",
        "hash-not-a-string",
        "sizes-ascending",
        "sizes-equal",
    ],
)
def test_a_malformed_stored_frontier_is_rejected(raw: object) -> None:
    """Validated on the way in, not trusted.

    This value comes back out of the database, and a wrong one would silently
    produce a plausible root for every entry appended after it. Sizes must be
    strictly decreasing powers of two because no other shape can have come from
    ``extend_frontier``, so anything else means the value did not come from here.
    """
    with pytest.raises(ValueError):
        frontier_from_json(raw)


# --------------------------------------------------------------------------
# Inclusion proofs (RFC 6962 audit path)
#
# The point of an inclusion proof is that an auditor holding one entry and a
# trusted root can confirm membership without the rest of the log. So these
# tests verify against build().root but pass verify_inclusion only the leaf hash
# and the O(log n) path, never the other entries.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("count", range(1, 34))
def test_inclusion_proof_verifies_for_every_leaf(count: int) -> None:
    """Every entry, at every tree size, proves inclusion under the real root.

    Swept across all sizes in the range because promotion of an odd node sends
    the last leaf up a different path than a paired one, and a bug there would
    hide only at specific counts.
    """
    payloads = entries(count)
    root = build(payloads).root
    for index in range(count):
        proof = inclusion_proof(payloads, index)
        assert proof.tree_size == count
        assert proof.leaf_index == index
        assert verify_inclusion(proof, hash_leaf(payloads[index]), root) is True


def test_inclusion_path_is_logarithmic() -> None:
    """The proof carries O(log n) hashes, not the whole log."""
    payloads = entries(1000)
    proof = inclusion_proof(payloads, 500)
    assert len(proof.audit_path) <= 10  # ceil(log2(1000)) == 10


def test_single_entry_inclusion_proof_is_empty() -> None:
    """A one-entry tree's root is the leaf itself, so the path is empty."""
    payloads = entries(1)
    proof = inclusion_proof(payloads, 0)
    assert proof.audit_path == ()
    assert verify_inclusion(proof, hash_leaf(payloads[0]), build(payloads).root)


def test_inclusion_proof_rejects_wrong_leaf() -> None:
    """A valid path for position i does not verify a different entry's hash."""
    payloads = entries(8)
    root = build(payloads).root
    proof = inclusion_proof(payloads, 3)
    forged = hash_leaf(b"not-the-entry-at-3")
    assert verify_inclusion(proof, forged, root) is False


def test_inclusion_proof_rejects_wrong_root() -> None:
    """A correct entry and path do not verify against an unrelated root."""
    payloads = entries(8)
    proof = inclusion_proof(payloads, 3)
    wrong_root = hashlib.sha256(b"not-the-root").hexdigest()
    assert verify_inclusion(proof, hash_leaf(payloads[3]), wrong_root) is False


def test_inclusion_proof_rejects_wrong_position_claim() -> None:
    """The path for leaf i must not verify that leaf as if it sat at leaf j.

    leaf_index is not decorative: verification derives each sibling's left/right
    orientation from it, so a proof replayed under a different claimed index
    reconstructs a different, non-matching root.
    """
    payloads = entries(8)
    root = build(payloads).root
    genuine = inclusion_proof(payloads, 2)
    moved = replace(genuine, leaf_index=5)
    assert verify_inclusion(moved, hash_leaf(payloads[2]), root) is False


def test_inclusion_proof_rejects_tampered_sibling() -> None:
    """Corrupting any hash in the path breaks verification."""
    payloads = entries(9)
    root = build(payloads).root
    proof = inclusion_proof(payloads, 4)
    corrupted = list(proof.audit_path)
    corrupted[0] = hashlib.sha256(b"tampered-sibling").hexdigest()
    broken = replace(proof, audit_path=tuple(corrupted))
    assert verify_inclusion(broken, hash_leaf(payloads[4]), root) is False


def test_inclusion_proof_index_out_of_range_raises() -> None:
    """A position that does not exist cannot be proved."""
    payloads = entries(4)
    with pytest.raises(ValueError):
        inclusion_proof(payloads, 4)
    with pytest.raises(ValueError):
        inclusion_proof(payloads, -1)
    with pytest.raises(ValueError):
        inclusion_proof([], 0)


# --------------------------------------------------------------------------
# Consistency proofs (RFC 6962)
#
# A consistency proof is the append-only guarantee made checkable: it proves the
# new root contains the old one as an unaltered prefix. These verify against the
# two real roots but hand verify_consistency only the proof nodes, never the log.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("new_size", range(1, 25))
def test_consistency_proof_verifies_for_every_prefix(new_size: int) -> None:
    """Every prefix of every tree proves consistent with the whole.

    The doubly-swept (old_size, new_size) space exercises the boundary logic
    that decides when the old subtree's own root is implied versus carried.
    """
    payloads = entries(new_size)
    new_root = build(payloads).root
    for old_size in range(new_size + 1):
        old_root = build(payloads[:old_size]).root
        proof = consistency_proof(payloads, old_size)
        assert verify_consistency(proof, old_root, new_root) is True


def test_consistency_proof_of_equal_sizes_is_trivial() -> None:
    """Old and new of the same size carry no nodes and must share a root."""
    payloads = entries(6)
    root = build(payloads).root
    proof = consistency_proof(payloads, 6)
    assert proof.nodes == ()
    assert verify_consistency(proof, root, root) is True


def test_consistency_proof_from_empty_old_tree() -> None:
    """The empty tree is a prefix of every tree."""
    payloads = entries(5)
    proof = consistency_proof(payloads, 0)
    assert verify_consistency(proof, EMPTY_ROOT, build(payloads).root) is True


def test_consistency_proof_rejects_a_rewritten_prefix() -> None:
    """If a past entry was altered, no consistency proof to the new root holds.

    This is the tamper case that matters: the operator keeps the entry count but
    edits history. The old (anchored) root no longer reconstructs from the new
    tree's proof nodes, so verification fails.
    """
    original = entries(8)
    old_root = build(original[:5]).root

    rewritten = list(original)
    rewritten[2] = b"audit-entry-2-REWRITTEN"
    new_root = build(rewritten).root
    proof = consistency_proof(rewritten, 5)

    assert verify_consistency(proof, old_root, new_root) is False


def test_consistency_proof_rejects_reordered_history() -> None:
    """Reordering past entries breaks consistency even at the same size."""
    original = entries(7)
    old_root = build(original[:4]).root

    reordered = [original[1], original[0], *original[2:]]
    proof = consistency_proof(reordered, 4)
    assert verify_consistency(proof, old_root, build(reordered).root) is False


def test_consistency_proof_rejects_wrong_new_root() -> None:
    """A genuine proof does not verify against an unrelated later root."""
    payloads = entries(10)
    old_root = build(payloads[:6]).root
    proof = consistency_proof(payloads, 6)
    wrong_new = hashlib.sha256(b"not-the-new-root").hexdigest()
    assert verify_consistency(proof, old_root, wrong_new) is False


def test_consistency_proof_rejects_wrong_old_root() -> None:
    """A genuine proof does not verify against an unrelated earlier root."""
    payloads = entries(10)
    new_root = build(payloads).root
    proof = consistency_proof(payloads, 6)
    wrong_old = hashlib.sha256(b"not-the-old-root").hexdigest()
    assert verify_consistency(proof, wrong_old, new_root) is False


def test_consistency_proof_rejects_tampered_node() -> None:
    """Corrupting a proof node breaks reconstruction of the new root."""
    payloads = entries(13)
    old_root = build(payloads[:5]).root
    new_root = build(payloads).root
    proof = consistency_proof(payloads, 5)
    corrupted = list(proof.nodes)
    corrupted[0] = hashlib.sha256(b"tampered-node").hexdigest()
    broken = replace(proof, nodes=tuple(corrupted))
    assert verify_consistency(broken, old_root, new_root) is False


def test_consistency_proof_out_of_range_raises() -> None:
    """An old size larger than the tree, or negative, cannot be proved."""
    payloads = entries(4)
    with pytest.raises(ValueError):
        consistency_proof(payloads, 5)
    with pytest.raises(ValueError):
        consistency_proof(payloads, -1)
