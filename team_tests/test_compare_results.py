"""Offline tests for the comparison and results part (Person 3).
No browser or internet needed.

Run from the project folder:  py team_tests\test_compare_results.py
"""

import copy
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from team_tools.check_review_against_goal import (
    SITE_URL, validate, check_context_goal, review_labels_to_fields,
    compare_review_to_goal, build_result, run,
)

GOAL = {
    "from": "DCA", "to": "BOS", "date": "2026-11-04",
    "flight_id": "AA101", "seat": "1A",
    "passenger": "Alex Student", "email": "alex@example.com",
    "checked_bag": False, "priority_boarding": False,
}

# what read_review_card() returns (page labels as keys)
REVIEW_INFO = {
    "Route": "DCA → BOS", "Date": "2026-11-04", "Flight": "AA101",
    "Seat": "1A", "Passenger": "Alex Student", "Email": "alex@example.com",
    "Checked bag": "No", "Priority boarding": "No", "Mock total": "$123.00",
}

CHECK_NAMES = ["route", "date", "flight_id", "seat", "passenger",
               "email", "checked_bag", "priority_boarding"]


def actual_fields():
    return review_labels_to_fields(REVIEW_INFO)


# a fake page that can only READ (it has no click or fill), built from plain functions
def make_fake_page(url=SITE_URL, stage_visible=True, card_visible=True, review=None):
    if review is None:
        review = REVIEW_INFO
    labels = list(review.keys())
    values = list(review.values())

    def card_locator(selector):
        def count():
            return len(labels)
        def nth(i):
            def label_text():
                return labels[i]
            def value_text():
                return values[i]
            if selector == "dt":
                return SimpleNamespace(inner_text=label_text)
            return SimpleNamespace(inner_text=value_text)
        return SimpleNamespace(count=count, nth=nth)

    def stage_visible_fn():
        return stage_visible

    def card_visible_fn():
        return card_visible

    def page_locator(selector):
        if selector == "#reviewStage":
            return SimpleNamespace(is_visible=stage_visible_fn)
        return SimpleNamespace(is_visible=card_visible_fn, locator=card_locator)

    return SimpleNamespace(url=url, locator=page_locator)


# --- labels -> fields -------------------------------------------------------
def test_labels_to_fields():
    f = actual_fields()
    assert f["route"] == "DCA → BOS"
    assert f["flight_id"] == "AA101"
    assert f["checked_bag"] == "No"
    assert f["mock_total"] == "$123.00"


# --- comparison -------------------------------------------------------------
def test_exact_match():
    r = build_result(actual_fields(), GOAL)
    assert r["ok"] is True, r
    for name in CHECK_NAMES:
        assert r["data"]["checks"][name] is True
    assert r["data"]["mismatches"] == []
    assert r["data"]["mock_total_observed"] == "$123.00"


def test_wrong_seat():
    goal = copy.deepcopy(GOAL)
    goal["seat"] = "9F"
    r = build_result(actual_fields(), goal)
    assert r["ok"] is False
    assert r["data"]["checks"]["seat"] is False
    assert r["data"]["mismatches"] == ["seat"]
    assert r["data"]["actual"]["seat"] == "1A"


def test_wrong_email():
    goal = copy.deepcopy(GOAL)
    goal["email"] = "other@example.com"
    r = build_result(actual_fields(), goal)
    assert r["ok"] is False
    assert r["data"]["mismatches"] == ["email"]


def test_bag_mismatch_and_unreadable_value():
    goal = copy.deepcopy(GOAL)
    goal["checked_bag"] = True
    assert build_result(actual_fields(), goal)["data"]["mismatches"] == ["checked_bag"]
    bad = actual_fields()
    bad["priority_boarding"] = "Maybe"
    assert build_result(bad, GOAL)["data"]["mismatches"] == ["priority_boarding"]


def test_missing_field_is_mismatch_not_guess():
    partial = actual_fields()
    del partial["seat"]
    r = build_result(partial, GOAL)
    assert r["ok"] is False
    assert r["data"]["mismatches"] == ["seat"]


def test_formatting_differences_tolerated():
    a = actual_fields()
    a["route"] = "dca -> bos"
    a["email"] = "Alex@Example.com "
    assert compare_review_to_goal(a, GOAL)["mismatches"] == []


# --- validate and goal check ------------------------------------------------
def test_validate():
    assert validate({})[0] is True
    assert validate({"seat": "1A"})[0] is False
    assert validate(None)[0] is False


def test_goal_check():
    assert check_context_goal({"goal": GOAL})[0] is True
    assert check_context_goal({})[0] is False
    assert check_context_goal(None)[0] is False
    goal = copy.deepcopy(GOAL)
    del goal["seat"]
    ok, note = check_context_goal({"goal": goal})
    assert ok is False and "seat" in note


# --- run() with a fake page -------------------------------------------------
def test_run_normal():
    r = run(make_fake_page(), {}, {"goal": GOAL})
    assert r["ok"] is True, r


def test_run_wrong_seat():
    goal = copy.deepcopy(GOAL)
    goal["seat"] = "9F"
    r = run(make_fake_page(), {}, {"goal": goal})
    assert r["ok"] is False
    assert r["data"]["mismatches"] == ["seat"]


def test_run_rejects_model_argument():
    r = run(make_fake_page(), {"goal": GOAL}, {"goal": GOAL})
    assert r["ok"] is False
    assert r["data"]["checks"] == {}


def test_run_incomplete_goal():
    goal = copy.deepcopy(GOAL)
    del goal["seat"]
    r = run(make_fake_page(), {}, {"goal": goal})
    assert r["ok"] is False and "seat" in r["message"]


def test_run_before_review_stage():
    r = run(make_fake_page(card_visible=False), {}, {"goal": GOAL})
    assert r["ok"] is False and "not visible" in r["message"]
    r = run(make_fake_page(stage_visible=False), {}, {"goal": GOAL})
    assert r["ok"] is False and "not visible" in r["message"]


def test_run_wrong_site():
    r = run(make_fake_page(url="https://example.com/"), {}, {"goal": GOAL})
    assert r["ok"] is False and "Expected URL" in r["message"]


def test_run_unreadable_summary():
    incomplete = {"Route": "DCA → BOS"}
    r = run(make_fake_page(review=incomplete), {}, {"goal": GOAL})
    assert r["ok"] is False


REVIEW_TESTS = [
    test_labels_to_fields, test_exact_match, test_wrong_seat, test_wrong_email,
    test_bag_mismatch_and_unreadable_value, test_missing_field_is_mismatch_not_guess,
    test_formatting_differences_tolerated, test_validate, test_goal_check,
    test_run_normal, test_run_wrong_seat, test_run_rejects_model_argument,
    test_run_incomplete_goal, test_run_before_review_stage, test_run_wrong_site,
    test_run_unreadable_summary,
]


def test_compare_results_all():
    for test_function in REVIEW_TESTS:
        test_function()


if __name__ == "__main__":
    for test_function in REVIEW_TESTS:
        test_function()
        print("PASS:", test_function.__name__)
    print("All", len(REVIEW_TESTS), "comparison/results checks passed.")
