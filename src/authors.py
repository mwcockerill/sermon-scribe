"""
Fetch sermon authors from a published Google Sheet CSV.

The sheet must have two columns: Date (YYYY-MM-DD) and Author.
Set AUTHORS_SHEET_URL in .env to the published CSV URL.
"""

import csv
import io
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv()

AUTHORS_SHEET_URL = os.environ.get(
    "AUTHORS_SHEET_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpHuhH2gLpQQYBm0cXt83NCI_A1UMwFd86gWdq6DaOOqU1hAdZHTXQW9cgYHBL9sOTUZqs6X7sP9Rj/pub?output=csv",
)


def fetch_authors() -> dict[str, str]:
    """
    Fetch the authors sheet and return a dict of {date: author}.
    Returns an empty dict on any error so the pipeline continues unaffected.
    """
    try:
        req = urllib.request.Request(
            AUTHORS_SHEET_URL,
            headers={"User-Agent": "sermon-scribe/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode("utf-8")

        authors = {}
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            date = (row.get("Date") or "").strip()
            author = (row.get("Author") or "").strip()
            if date and author:
                authors[date] = author

        return authors
    except Exception as e:
        print(f"  WARNING: Could not fetch authors sheet: {e}")
        return {}


def lookup_author(date: str, authors: dict[str, str] | None = None) -> str | None:
    """
    Look up the author for a given date (YYYY-MM-DD).
    Fetches the sheet if authors dict not provided.
    Returns None if not found.
    """
    if authors is None:
        authors = fetch_authors()
    return authors.get(date)
