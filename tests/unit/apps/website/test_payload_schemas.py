import pytest

from pydantic import ValidationError

from caching_svc.apps.website.schemas import PayloadCreateSchema
from caching_svc.apps.website.schemas.payload import MAX_LIST_LENGTH


pytestmark = pytest.mark.unit


def test_accepts_lists_of_same_length():
    schema = PayloadCreateSchema(list_1=["a", "b"], list_2=["c", "d"])

    assert schema.list_1 == ["a", "b"]


@pytest.mark.parametrize(
    "data",
    [
        {"list_1": ["a", "b"], "list_2": ["c"]},
        {"list_1": [], "list_2": []},
        {"list_1": ["a"]},
        {"list_1": ["a"] * (MAX_LIST_LENGTH + 1), "list_2": ["b"] * (MAX_LIST_LENGTH + 1)},
        {"list_1": [1], "list_2": ["b"]},
    ],
    ids=["different-length", "empty", "missing-list", "too-long", "non-string"],
)
def test_rejects_invalid_input(data):
    with pytest.raises(ValidationError):
        PayloadCreateSchema.model_validate(data)
