"""Live test of check_review_against_goal in a real Playwright browser.
Nothing is ever confirmed or submitted.

Run from the project folder:  py team_tests/live_test_review.py

1. Edit GOAL below so it matches what you will enter on the site
   (use a future date and pretend details only).
2. A browser window opens. Search, pick a flight, pick a seat, enter the
   passenger details and click "Continue to review".
3. Stop when you see "5. Review the reservation".
   Do NOT tick the box and do NOT click Confirm reservation.
4. Keep the browser window OPEN, go back to PowerShell, and press Enter.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import browser_tools
from team_tools.check_review_against_goal import run

GOAL = {
    "from": "DCA", "to": "BOS", "date": "2026-11-04",
    "flight_id": "AA101", "seat": "1A",
    "passenger": "Alex Student", "email": "alex@example.com",
    "checked_bag": False, "priority_boarding": False,
}


def show(title, result):
    print("\n==", title, "==")
    print("ok:", result["ok"], "|", result["message"])
    print("checks:", result["data"].get("checks"))
    print("mismatches:", result["data"].get("mismatches"))
    if "actual" in result["data"]:
        print("actual values read from the page:", result["data"]["actual"])
        print("mock total observed:", result["data"].get("mock_total_observed"))


browser_tools.start_browser()
try:
    browser_tools.open_site()

    # extra failure case: before the review stage
    show("Before review stage (should be ok=False)",
         run(browser_tools.page, {}, {"goal": GOAL}))

    input("\nFill the form until '5. Review the reservation' is showing.\n"
          "Keep the browser open. Then press Enter here...")
    before = browser_tools.page.locator("#reviewCard").inner_text()

    show("Normal (should be ok=True if GOAL matches what you entered)",
         run(browser_tools.page, {}, {"goal": GOAL}))

    bad_seat = copy.deepcopy(GOAL)
    bad_seat["seat"] = "9F"
    show("Wrong seat in the goal (seat should be False)",
         run(browser_tools.page, {}, {"goal": bad_seat}))

    bad_email = copy.deepcopy(GOAL)
    bad_email["email"] = "wrong@example.com"
    show("Wrong email in the goal (email should be False)",
         run(browser_tools.page, {}, {"goal": bad_email}))

    incomplete = copy.deepcopy(GOAL)
    del incomplete["seat"]
    show("Incomplete goal (should explain why)",
         run(browser_tools.page, {}, {"goal": incomplete}))

    show("Model tries to pass an argument (should be rejected)",
         run(browser_tools.page, {"goal": GOAL}, {"goal": GOAL}))

    after = browser_tools.page.locator("#reviewCard").inner_text()
    print("\nPage unchanged by the tool:", before == after)
    input("\nPress Enter to close the browser (nothing was confirmed)...")
finally:
    browser_tools.close_browser()
