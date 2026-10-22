"""
this tool checks whether the reservation shown on the review screen
matches the reservation that was made in the goal screen. It is used
to verify that the correct reservation is being displayed to the user
after they have made a reservation.

this tool only reads the screen and takes in the information that is
displayed.

"""

#constants and field names
#pieces of information from from goal (from, to, date, time, flight_id, seat, name)
SITE_URL = "https://onyourmark.github.io/browser-agent-form/travel/"

GOAL_KEYS = [
    "from", "to", "date", "flight_id", "seat",
    "passenger", "email", "checked_bag", "priority_boarding",
]

# fields reported in data["checks"], in this order
REQUIRED_FIELDS = [
    "route", "date", "flight_id", "seat",
    "passenger", "email", "checked_bag", "priority_boarding",
]

#labels on the review card on the webpage
#dt/dt pairs (route, date, flight, seat, passenger, email, checked bag, priotity boarding, mock total)
# page label -> the field name used when comparing
LABEL_TO_FIELD = {
    "Route": "route",
    "Date": "date",
    "Flight": "flight_id",
    "Seat": "seat",
    "Passenger": "passenger",
    "Email": "email",
    "Checked bag": "checked_bag",
    "Priority boarding": "priority_boarding",
    "Mock total": "mock_total",
}

MSG_MATCH = "The review matches the requested reservation."
MSG_MISMATCH = "The review does not match the requested reservation."


#validate the reservation information on the review screen against the reservation information from the goal screen
#function
#returns true if the model supplied argument is valid or false if it is not valid
def validate(argument):
    if not isinstance(argument, dict):
        return False, "The argument must be an empty dictionary {}."
    if argument:
        return False, "This tool takes no arguments; the expected goal comes only from trusted Python."
    return True, "OK"


#build failure result
#builds a failure return dictionary so its all in the same format
def failure_result(reason):
    return {"ok": False, "message": reason, "data": {"checks": {}, "mismatches": []}}


#check context goal
#helps with checking the context goal and making sure that the informatiion is valid and that the context goal is
# valid. It will return a failure result if the context goal is not valid or if the information is not valid.
def check_context_goal(context):
    # returns (True, "OK") or (False, reason)
    if not isinstance(context, dict) or not isinstance(context.get("goal"), dict):
        return False, "The trusted context has no goal, so no comparison was made."

    goal = context["goal"]
    missing = []
    for key in GOAL_KEYS:
        if key not in goal:
            missing.append(key)
    if missing:
        return False, "The trusted goal is incomplete (missing: " + ", ".join(missing) + ")."

    for key in ("checked_bag", "priority_boarding"):
        if not isinstance(goal[key], bool):
            return False, "Goal field '" + key + "' must be True or False."

    return True, "OK"


#confirm review stage
#makes sure that the browser is on the review stage and and review card is visible. It will return a failure result
# if the browser is not on the review stage or if the review card is not visible.
def confirm_review_stage(page):
    if page is None:
        return False, "No browser page was provided."

    expected_url = "https://onyourmark.github.io/browser-agent-form/travel/"

    actual_url = page.url.split("#")[0].split("?")[0]

    if actual_url != expected_url:
        return False, f"Browser is not on the review stage. Expected URL: {expected_url}, but got: {actual_url}"

    review_stage = page.locator("#reviewStage")
    review_card = page.locator("#reviewCard")

    # (fixed: this first check used review_stage twice, so the card was never checked)
    if not review_card.is_visible():
        return False, "Review card is not visible on the page."

    if not review_stage.is_visible():
        return False, "Review stage is not visible on the page."

    return True, "Browser is on the review stage and review card is visible."



#read review card
#reads the review card and returns a dictionary of the information that is displayed on the review card. It will return
# a failure result if the review card is not visible.
def read_review_card(page):
    if page is None:
        return None, "No browser page was provided."

    card = page.locator("#reviewCard")

    if not card.is_visible():
        return None, "Review card is not visible on the page."

    labels = card.locator("dt")
    values = card.locator("dd")

    label_count = labels.count()
    value_count = values.count()

    if label_count == 0 or label_count != value_count:
        return None, "Mismatch in the number of labels and values on the review card."

    review_info = {}

    for i in range(label_count):
        label = labels.nth(i).inner_text().strip()
        value = values.nth(i).inner_text().strip()

        if label == "" or value == "":
            return None, f"Empty label or value found at index {i}."

        review_info[label] = value

    required_fields = [
        "Route",
        "Date",
        "Flight",
        "Seat",
        "Passenger",
        "Email",
        "Checked bag",
        "Priority boarding",
        "Mock total"
        ]

    for label in required_fields:
        if label not in review_info:
            return None, f"Missing required field '{label}' on the review card."

        if review_info[label] == "":
            return None, f"Required field '{label}' is empty on the review card."

    return review_info, "Successfully read the review card."



#compare review to goal
#compares the information on the review card to the information from the goal screen and returns a boolean indicating whether
# they match. It will return a failure result if the review card is not visible or if the information on the review card does
# not match the information from the goal screen.

def review_labels_to_fields(review_info):
    # read_review_card returns page labels ("Flight", "Checked bag", ...).
    # Turn them into the field names used for comparing ("flight_id", "checked_bag", ...).
    fields = {}
    for label, value in review_info.items():
        if label in LABEL_TO_FIELD:
            fields[LABEL_TO_FIELD[label]] = value
    return fields


def clean_text(text):
    # collapse spaces so harmless formatting differences do not count as mismatches
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())


def split_route(text):
    # "DCA → BOS", "DCA -> BOS" or "DCA to BOS"  ->  ("DCA", "BOS"), or None if unreadable
    text = clean_text(text)
    for divider in ("→", "->", "=>", " to ", " TO ", " To "):
        if divider in text:
            parts = text.split(divider, 1)
            return (parts[0].strip().upper(), parts[1].strip().upper())
    return None


def yes_no_to_bool(value):
    # "Yes" -> True, "No" -> False, a real bool stays as is, anything else -> None (unreadable)
    if isinstance(value, bool):
        return value
    text = clean_text(value).lower()
    if text == "yes":
        return True
    if text == "no":
        return False
    return None


def compare_review_to_goal(actual, goal):
    # actual: dict with the field names above (route, date, flight_id, seat, passenger,
    #         email, checked_bag, priority_boarding, mock_total)
    # goal:   the trusted context["goal"]
    # returns {"checks": {field: True/False}, "mismatches": [field, ...]}
    # a field the page did not show counts as a mismatch, never a guessed pass
    actual = actual or {}
    checks = {}

    shown_route = split_route(actual.get("route"))
    expected_route = (clean_text(goal.get("from")).upper(), clean_text(goal.get("to")).upper())
    checks["route"] = shown_route is not None and shown_route == expected_route

    shown_date = clean_text(actual.get("date"))
    checks["date"] = shown_date != "" and shown_date == clean_text(goal.get("date"))

    shown_flight = clean_text(actual.get("flight_id")).upper().replace(" ", "")
    expected_flight = clean_text(goal.get("flight_id")).upper().replace(" ", "")
    checks["flight_id"] = shown_flight != "" and shown_flight == expected_flight

    shown_seat = clean_text(actual.get("seat")).upper().replace(" ", "")
    expected_seat = clean_text(goal.get("seat")).upper().replace(" ", "")
    checks["seat"] = shown_seat != "" and shown_seat == expected_seat

    shown_name = clean_text(actual.get("passenger")).lower()
    checks["passenger"] = shown_name != "" and shown_name == clean_text(goal.get("passenger")).lower()

    shown_email = clean_text(actual.get("email")).lower()
    checks["email"] = shown_email != "" and shown_email == clean_text(goal.get("email")).lower()

    for field in ("checked_bag", "priority_boarding"):
        shown = yes_no_to_bool(actual.get(field))
        expected = yes_no_to_bool(goal.get(field))
        checks[field] = shown is not None and expected is not None and shown == expected

    mismatches = []
    for name in REQUIRED_FIELDS:
        if not checks[name]:
            mismatches.append(name)

    return {"checks": checks, "mismatches": mismatches}


def build_result(actual, goal):
    # packages the comparison in the shared {"ok", "message", "data"} format
    # ok is True only when every required field matches
    # the actual values are included so mismatches are never hidden
    # the mock total is only recorded (the goal has no target price), it is never compared
    comparison = compare_review_to_goal(actual, goal)
    ok = len(comparison["mismatches"]) == 0

    expected = {}
    for key in GOAL_KEYS:
        expected[key] = goal.get(key)

    if ok:
        message = MSG_MATCH
    else:
        message = MSG_MISMATCH

    return {
        "ok": ok,
        "message": message,
        "data": {
            "checks": comparison["checks"],
            "mismatches": comparison["mismatches"],
            "actual": dict(actual or {}),
            "expected": expected,
            "mock_total_observed": (actual or {}).get("mock_total"),
        },
    }



#run function
#main tool to validate the model argument and check the trusted goal in context and confirm that the review screen is visible.
#must be able to read the values from the review card and compare the actual values to the goal and then return the dictionary result.
def run(page, argument, context):
    # 1. the model may only pass {}
    ok, note = validate(argument)
    if not ok:
        return failure_result(note)

    # 2. the browser must be on the approved site with the review screen visible
    ok, note = confirm_review_stage(page)
    if not ok:
        return failure_result(note)

    # 3. the trusted goal must exist and be complete
    ok, note = check_context_goal(context)
    if not ok:
        return failure_result(note)

    # 4. read what the review screen really shows (read-only)
    review_info, note = read_review_card(page)
    if review_info is None:
        return failure_result(note)

    # 5. compare with the goal and return the field-by-field result
    actual = review_labels_to_fields(review_info)
    return build_result(actual, context["goal"])
