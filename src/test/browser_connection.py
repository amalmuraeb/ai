"""
Phase 1 - Browser Connection Test
Verifies Playwright attachment to Microsoft Edge over CDP.
"""

import argparse

from playwright.sync_api import sync_playwright

from src.config.browser import BROWSER


parser = argparse.ArgumentParser()
parser.add_argument(
    "--landing_url",
    required=True,
    help="HigherEdJobs saved-alert results URL.",
)
arguments = parser.parse_args()

with sync_playwright() as playwright:
    browser = playwright.chromium.connect_over_cdp(BROWSER["cdp_url"])
    context = browser.contexts[0]

    page = context.new_page()
    page.goto(arguments.landing_url, wait_until="domcontentloaded")

    print(f"Current URL: {page.url}")
    print(f"Title: {page.title()}")
    print(f"HTML characters: {len(page.content())}")
