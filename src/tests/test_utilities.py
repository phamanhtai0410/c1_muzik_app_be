import pytest

from src.utilities import PaginateMixin


@pytest.mark.django_db
def test_paginate_mixin():
    """
    Usualy default ITEMS_PER_PAGE value in config equal 50
    """

    class Request:
        def __init__(self, _query_params):
            self.params = _query_params

        @property
        def query_params(self):
            return self.params

    ITEMS = [f"item_{i}" for i in range(58)]

    response = PaginateMixin().paginate(Request({"page": 1}), ITEMS)
    assert response["results_per_page"] == 50
    assert response["total_pages"] == 2
    assert response["total"] == 58

    response = PaginateMixin().paginate(
        Request({"page": 1, "items_per_page": 10}), ITEMS
    )
    assert response["results_per_page"] == 10
    assert response["total_pages"] == 6
    assert response["total"] == 58

    # test negative value and page not equal 1
    response = PaginateMixin().paginate(
        Request({"page": 6, "items_per_page": -10}), ITEMS
    )
    assert response["results_per_page"] == 10
    assert response["results"][0] == "item_50"
    assert response["results"][-1] == "item_57"

    # test zero values
    response = PaginateMixin().paginate(
        Request({"page": 0, "items_per_page": 0}), ITEMS
    )
    assert response["results_per_page"] == 50
    assert response["results"][0] == "item_0"
    assert response["results"][-1] == "item_49"

    # test incorrect values type
    response = PaginateMixin().paginate(
        Request({"page": [1], "items_per_page": [10]}), ITEMS
    )
    assert response["results_per_page"] == 50
    assert response["results"][0] == "item_0"
    assert response["results"][-1] == "item_49"
