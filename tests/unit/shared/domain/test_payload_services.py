import pytest

from caching_svc.shared.domain.services import (
    build_output,
    build_payload_hash,
    distinct_values,
    hash_text,
    interleave,
    missing_values,
)


pytestmark = pytest.mark.unit


def test_interleave_matches_spec_example():
    first = ["FIRST STRING", "SECOND STRING", "THIRD STRING"]
    second = ["OTHER STRING", "ANOTHER STRING", "LAST STRING"]

    assert interleave(first, second) == (
        "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
    )


def test_interleave_rejects_lists_of_different_length():
    with pytest.raises(ValueError):
        interleave(["a", "b"], ["c"])


def test_hash_text_is_stable_hex_sha256():
    assert hash_text("abc") == hash_text("abc")
    assert len(hash_text("abc")) == 64
    assert hash_text("abc") != hash_text("ABC")


def test_payload_hash_is_deterministic():
    assert build_payload_hash(["a"], ["b"]) == build_payload_hash(["a"], ["b"])


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ((["a"], ["b"]), (["b"], ["a"])),  # lists swapped
        ((["a", "b"], ["c", "d"]), (["b", "a"], ["d", "c"])),  # items reordered
        ((["a, b"], ["c"]), (["a", "b"], ["c"])),  # separator inside an item
    ],
)
def test_payload_hash_distinguishes_inputs_producing_different_outputs(left, right):
    assert build_payload_hash(*left) != build_payload_hash(*right)


def test_distinct_values_deduplicates_within_and_across_lists_keeping_order():
    assert distinct_values(["b", "a", "b"], ["c", "a", "b"]) == ["b", "a", "c"]


def test_missing_values_returns_only_uncached_values():
    assert missing_values(["a", "b", "c"], {"b": "B"}) == ["a", "c"]


def test_missing_values_is_empty_when_everything_is_cached():
    assert missing_values(["a"], {"a": "A"}) == []


def test_build_output_uses_transformed_form_of_every_occurrence():
    transformed = {"a": "A", "b": "B"}

    assert build_output(["a", "b"], ["b", "a"], transformed) == "A, B, B, A"
