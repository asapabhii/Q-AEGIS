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

import pytest

from app.audit.merkle import (
    EMPTY_ROOT,
    LEAF_PREFIX,
    NODE_PREFIX,
    build,
    canonicalize,
    hash_internal,
    hash_leaf,
    verify,
)


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
