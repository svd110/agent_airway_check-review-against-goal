"""check_review_against_goal -- team3person

Read-only pre-confirmation check. It reads the visible review screen and
compares it with a trusted goal supplied by Python (context["goal"]).

It never clicks, types, ticks a checkbox, or confirms anything.
The model passes {} only, so it cannot change the expected reservation.

Sections:
  1. Settings and the validate() function
  2. Safety checks (URL, review stage, goal)
  3. Reading the visible review (read-only)
  4. Comparison logic and final results
  5. evaluate_review() and run(page, argument, context)
"""

import re

# Same fixed practice site as browser_tools.py. Kept here so this module can
# be tested on its own, without importing other teams' files.
SITE_URL = "https://onyourmark.github.io/browser-agent-form/travel/"

# Keys the trusted goal must contain.
GOAL_KEYS = [
    "from", "to", "date", "flight_id", "seat",
    "passenger", "email", "checked_bag", "priority_boarding",
]

# Fields reported in data["checks"], in this order.
REQUIRED_FIELDS = [
    "route", "date", "flight_id", "seat",
    "passenger", "email", "checked_bag", "priority_boarding",
]

# Review label shown on the page -> key we store it under.
LABEL_TO_KEY = {
    "route": "route",
    "date": "date",
    "flight": "flight_id",
    "seat": "seat",
    "passenger": "passenger",
    "email": "email",
    "checked bag": "checked_bag",
    "priority boarding": "priority_boarding",
    "mock total": "mock_total",
}

MSG_MATCH = "The review matches the requested reservation."
MSG_MISMATCH = "The review does not match the requested reservation."


# ---------------------------------------------------------------------------
# 1. validate
# ---------------------------------------------------------------------------

def validate(argument):
    """Accept only an empty dictionary.

    The model must not be able to supply an expected reservation.
    Returns (True/False, a short plain-English explanation).
    """
    if not isinstance(argument, dict):
        return False, "The argument must be an empty dictionary {}."
    if argument:
        return False, "This tool takes no arguments; the expected goal comes only from trusted Python."
    return True, "OK"


# ---------------------------------------------------------------------------
# 2. Safety checks (work on plain data, so they are easy to test offline)
# ---------------------------------------------------------------------------

def failure_result(reason):
    """Result for when a comparison could not be made at all."""
    return {"ok": False, "message": reason, "data": {"checks": {}, "mismatches": []}}


def check_site_and_stage(facts):
    """Return None if fine, or a reason string if we cannot compare yet."""
    if not str(facts.get("url", "")).startswith(SITE_URL):
        return "The browser is not on the approved practice site."
    if not facts.get("stage_visible"):
        return "The review screen (#reviewStage) is not visible yet."
    return None


def check_trusted_goal(context):
    """Return None if the trusted goal is complete, or a reason string."""
    if not isinstance(context, dict) or not isinstance(context.get("goal"), dict):
        return "The trusted context has no goal, so no comparison was made."
    goal = context["goal"]
    missing = []
    for key in GOAL_KEYS:
        if key not in goal:
            missing.append(key)
    if missing:
        return "The trusted goal is incomplete (missing: " + ", ".join(missing) + ")."
    for key in ("checked_bag", "priority_boarding"):
        if not isinstance(goal[key], bool):
            return "Goal field '" + key + "' must be True or False."
    return None


# ---------------------------------------------------------------------------
# 3. Read the visible review (read-only)
# ---------------------------------------------------------------------------

def read_page_facts(page):
    """Read what the browser shows. Only reads; changes nothing."""
    facts = {
        "url": page.url,
        "stage_visible": page.locator("#reviewStage").is_visible(),
        "labels": [],
        "values": [],
    }
    if facts["stage_visible"]:
        facts["labels"] = page.locator("#reviewCard dt").all_inner_texts()
        facts["values"] = page.locator("#reviewCard dd").all_inner_texts()
    return facts


def pair_review_values(labels, values):
    """Match each dt label with its dd value.

    Returns a dict like {"route": "DCA → BOS", "seat": "1A", ...}.
    """
    found = {}
    for label, value in zip(labels, values):
        name = " ".join(label.split()).rstrip(":").casefold()
        if name in LABEL_TO_KEY:
            found[LABEL_TO_KEY[name]] = " ".join(value.split())
    return found


# ---------------------------------------------------------------------------
# 4. Comparison logic and final results (Person 3)
# ---------------------------------------------------------------------------

def _clean(text):
    """Collapse whitespace and strip. Non-strings become ''."""
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _norm_text(text):
    return _clean(text).casefold()


def _norm_code(text):
    return _clean(text).upper().replace(" ", "")


def _norm_route(text):
    """'DCA → BOS', 'DCA -> BOS', 'DCA to BOS' -> ('DCA', 'BOS')."""
    parts = re.split(r"\s*(?:→|->|-->|=>|\bto\b)\s*", _clean(text),
                     maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    return (parts[0].strip().upper(), parts[1].strip().upper())


def _norm_yes_no(value):
    """'Yes'/'No' (or a real bool) -> True/False. Anything else -> None."""
    if isinstance(value, bool):
        return value
    text = _norm_text(value)
    if text == "yes":
        return True
    if text == "no":
        return False
    return None


def compare_review_to_goal(actual, goal):
    """Compare values read from the page with the trusted goal.

    actual: dict from read_review_values() (keys: route, date, flight_id,
            seat, passenger, email, checked_bag, priority_boarding, mock_total).
    goal:   the trusted context["goal"].

    Returns {"checks": {...}, "mismatches": [...]}.
    A field the page did not show counts as a mismatch, never a guessed pass.
    """
    actual = actual or {}
    checks = {}

    shown_route = _norm_route(actual.get("route"))
    expected_route = (_norm_code(goal.get("from")), _norm_code(goal.get("to")))
    checks["route"] = shown_route is not None and shown_route == expected_route

    shown_date = _clean(actual.get("date"))
    checks["date"] = shown_date != "" and shown_date == _clean(goal.get("date"))

    shown_flight = _norm_code(actual.get("flight_id", actual.get("flight")))
    checks["flight_id"] = shown_flight != "" and shown_flight == _norm_code(goal.get("flight_id"))

    shown_seat = _norm_code(actual.get("seat"))
    checks["seat"] = shown_seat != "" and shown_seat == _norm_code(goal.get("seat"))

    shown_name = _norm_text(actual.get("passenger"))
    checks["passenger"] = shown_name != "" and shown_name == _norm_text(goal.get("passenger"))

    shown_email = _norm_text(actual.get("email"))
    checks["email"] = shown_email != "" and shown_email == _norm_text(goal.get("email"))

    for field in ("checked_bag", "priority_boarding"):
        shown = _norm_yes_no(actual.get(field))
        expected = _norm_yes_no(goal.get(field))
        checks[field] = shown is not None and expected is not None and shown == expected

    mismatches = []
    for name in REQUIRED_FIELDS:
        if not checks[name]:
            mismatches.append(name)
    return {"checks": checks, "mismatches": mismatches}


def build_result(actual, goal):
    """Package the comparison in the shared {"ok", "message", "data"} format.

    ok is True only when every required field matches. Actual values are
    included so mismatches are never hidden. The mock total is recorded as an
    observation only: the goal has no target price, so it is not compared.
    """
    comparison = compare_review_to_goal(actual, goal)
    ok = len(comparison["mismatches"]) == 0

    expected = {}
    for key in GOAL_KEYS:
        expected[key] = goal.get(key)

    return {
        "ok": ok,
        "message": MSG_MATCH if ok else MSG_MISMATCH,
        "data": {
            "checks": comparison["checks"],
            "mismatches": comparison["mismatches"],
            "actual": dict(actual or {}),
            "expected": expected,
            "mock_total_observed": (actual or {}).get("mock_total"),
        },
    }


# ---------------------------------------------------------------------------
# 5. Decide, then run
# ---------------------------------------------------------------------------

def evaluate_review(argument, context, facts):
    """Apply every required check in order, using facts read from the page."""
    ok, why = validate(argument)
    if not ok:
        return failure_result(why)

    problem = check_site_and_stage(facts)
    if problem:
        return failure_result(problem)

    problem = check_trusted_goal(context)
    if problem:
        return failure_result(problem)

    actual = pair_review_values(facts["labels"], facts["values"])
    if not actual:
        return failure_result("The review summary could not be read from #reviewCard.")

    return build_result(actual, context["goal"])


def run(page, argument, context):
    """Check the visible review against the trusted goal. Read-only."""
    ok, why = validate(argument)
    if not ok:
        return failure_result(why)
    if page is None:
        return failure_result("No browser page is open.")

    try:
        facts = read_page_facts(page)
    except Exception as error:  # for example a Playwright timeout
        return failure_result("The review could not be read: " + str(error))

    return evaluate_review(argument, context, facts)
