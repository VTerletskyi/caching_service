import hashlib
import json

from collections.abc import Mapping
from itertools import chain


OUTPUT_SEPARATOR = ", "


def interleave(first: list[str], second: list[str]) -> str:
    """Join two equal-length lists as ``first[0], second[0], first[1], second[1], ...``."""
    return OUTPUT_SEPARATOR.join(chain.from_iterable(zip(first, second, strict=True)))


def distinct_values(list_1: list[str], list_2: list[str]) -> list[str]:
    """Every string of both lists exactly once, in first-seen order.

    This is what keeps a string repeated within a request (or present in both lists) from being
    looked up or transformed more than once.
    """
    return list(dict.fromkeys(chain(list_1, list_2)))


def missing_values(values: list[str], cached: Mapping[str, str]) -> list[str]:
    """Values without a cached transformation, i.e. the only ones the transformer is called for."""
    return [value for value in values if value not in cached]


def build_output(list_1: list[str], list_2: list[str], transformed: Mapping[str, str]) -> str:
    """Interleave the transformed forms of both lists."""
    return interleave(
        [transformed[value] for value in list_1],
        [transformed[value] for value in list_2],
    )


def hash_text(value: str) -> str:
    """SHA-256 of a single string.

    Cache lookups go through the hash rather than the raw text: strings are unbounded and a
    B-tree index on long text values hits Postgres' index row size limit.
    """
    return hashlib.sha256(value.encode()).hexdigest()


def build_payload_hash(list_1: list[str], list_2: list[str]) -> str:
    """Deterministic identity of a payload request, used to reuse previously generated payloads.

    The lists are serialized as JSON (not joined with a separator) so that inputs like
    ``["a, b"]`` and ``["a", "b"]`` can never collide. Order is significant on purpose: swapping
    the lists or their items produces a different output.
    """
    canonical = json.dumps([list_1, list_2], ensure_ascii=False, separators=(",", ":"))
    return hash_text(canonical)
