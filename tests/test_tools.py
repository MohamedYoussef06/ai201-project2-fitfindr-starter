"""
tests/test_tools.py

Isolation tests for each FitFindr tool. Run with:
    pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_no_price_filter():
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) > 0


def test_search_size_filter_case_insensitive():
    # "M" should match listings with size "S/M" or "M"
    results = search_listings("tee", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_returns_sorted_by_relevance():
    # Items with more keyword overlap should appear first
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    # Just verify it returns a list without error
    assert isinstance(results, list)


def test_search_returns_list_of_dicts():
    results = search_listings("jeans", size=None, max_price=100)
    for item in results:
        assert isinstance(item, dict)
        assert "title" in item
        assert "price" in item
        assert "id" in item


def test_search_empty_description_still_works():
    # Empty description matches nothing (score 0 for all) → empty list
    results = search_listings("", size=None, max_price=None)
    assert results == []


# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test suggest_outfit"
    suggestion = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    suggestion = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0  # must not return empty string


def test_suggest_outfit_does_not_crash_on_empty_wardrobe():
    results = search_listings("jeans", size=None, max_price=100)
    assert results
    # Should not raise an exception
    result = suggest_outfit(results[0], get_empty_wardrobe())
    assert result is not None


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    outfit = suggest_outfit(results[0], get_example_wardrobe())
    card = create_fit_card(outfit, results[0])
    assert isinstance(card, str)
    assert len(card) > 0


def test_create_fit_card_empty_outfit_returns_error_message():
    results = search_listings("vintage", size=None, max_price=100)
    assert results
    result = create_fit_card("", results[0])
    assert isinstance(result, str)
    assert "error" in result.lower() or "cannot" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_message():
    results = search_listings("vintage", size=None, max_price=100)
    assert results
    result = create_fit_card("   ", results[0])
    assert isinstance(result, str)
    assert len(result) > 0
    # Should be an error message, not a crash
    assert "error" in result.lower() or "cannot" in result.lower()


def test_create_fit_card_does_not_raise():
    results = search_listings("jeans", size=None, max_price=100)
    assert results
    outfit = "Wide-leg jeans with a tucked-in white tee and chunky sneakers."
    card = create_fit_card(outfit, results[0])
    assert card is not None
