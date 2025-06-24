"""Core functionality for DUCK: fetching and processing GitHub data.

This module provides functions to interact with the GitHub API,
fetch various types of user activity data, and perform initial processing.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import requests
from pydantic import ValidationError

from duck.models import (
    GitHubEvent,
    PullRequestSimple,
)

logger = logging.getLogger(__name__)

# Default pagination values, also used by CLI as ultimate fallback
DEFAULT_MAX_EVENT_PAGES: int = 5
DEFAULT_MAX_PR_PAGES: int = 2


def _handle_github_api_http_error(response: requests.Response, context: Optional[str] = None) -> None:
    """Handle specific HTTP errors from the GitHub API response.

    Args:
        response: The requests.Response object.
        context: A string providing context for the error, e.g., username or operation.
    """
    status_code = response.status_code
    error_context = f" for {context}" if context else ""
    logger.error(f"HTTP error occurred: {response.reason} - Status: {status_code}{error_context}")

    if status_code == 404:
        logger.error(f"Resource not found (404){error_context}.")
    elif status_code == 401:
        logger.error(f"Unauthorized (401){error_context}. Ensure your GITHUB_TOKEN is valid and has appropriate scopes.")
    elif status_code == 403:
        logger.error(f"Forbidden (403){error_context}. This might be due to rate limiting or insufficient token scopes. Using a GITHUB_TOKEN can help.")
        rate_limit_info = (
            f"Rate limit info: Limit: {response.headers.get('X-RateLimit-Limit')}, "
            f"Remaining: {response.headers.get('X-RateLimit-Remaining')}, "
            f"Reset: {response.headers.get('X-RateLimit-Reset')}"
        )
        logger.info(rate_limit_info)
    # Add more specific handlers if needed


def _parse_events_from_response(events_data: list, page_num: int) -> List[GitHubEvent]:
    """Parses a list of event data into GitHubEvent objects."""
    parsed_events: List[GitHubEvent] = []
    for event_item in events_data:
        try:
            parsed_events.append(GitHubEvent(**event_item))
        except ValidationError as e:
            logger.warning(f"Skipping an event due to Pydantic validation error on page {page_num}: {e}. Event data: {event_item}")
        except TypeError as e:
            logger.warning(f"Skipping an event due to TypeError (likely Pydantic model init) on page {page_num}: {e}. Event data: {event_item}")
    return parsed_events


def _fetch_single_events_page(url: str, headers: dict, page_num: int, username_for_context: str) -> tuple[Optional[List[GitHubEvent]], Optional[str]]:
    """Fetches a single page of events and returns events and next page URL."""
    logger.info(f"Fetching events page {page_num} from {url} for user {username_for_context}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        events_data = response.json()

        if not isinstance(events_data, list):
            logger.error(f"Expected a list of events from API page {page_num}, got {type(events_data)}.")
            return None, None

        parsed_page_events = _parse_events_from_response(events_data, page_num)
        next_page_url = response.links.get("next", {}).get("url")
        return parsed_page_events, next_page_url

    except requests.exceptions.HTTPError as http_err:
        if http_err.response is not None:
            _handle_github_api_http_error(http_err.response, context=f"public events for {username_for_context}, page {page_num}")
        else:
            logger.error(f"HTTP error for {username_for_context}, page {page_num}: {http_err}")
        return None, None
    except requests.exceptions.Timeout:
        logger.error(f"Request to GitHub API for {username_for_context} timed out on page {page_num}.")
        return None, None
    except requests.exceptions.RequestException as req_err:  # Catches other network issues
        logger.error(f"Error requesting GitHub API for {username_for_context}, page {page_num}: {req_err}")
        return None, None
    except ValueError as json_err:  # Includes JSONDecodeError
        logger.error(f"Error decoding JSON for {username_for_context}, page {page_num}: {json_err}")
        return None, None


def fetch_github_user_public_events(username: str, token: Optional[str] = None, max_pages: int = 10) -> Optional[List[GitHubEvent]]:
    """Fetch public events for a given GitHub user, handling pagination.

    Args:
        username: The GitHub username.
        token: An optional GitHub Personal Access Token for authentication.
        max_pages: Maximum number of pages to fetch.

    Returns:
        A list of GitHubEvent objects if successful, None otherwise.
    """
    if not username:
        logger.error("GitHub username cannot be empty.")
        return None

    next_url: Optional[str] = f"https://api.github.com/users/{username}/events/public?per_page=100"
    headers = {"Accept": "application/vnd.github.v3+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    all_events: List[GitHubEvent] = []
    pages_fetched = 0
    logger.info(f"Fetching public events for user: {username}. Max pages: {max_pages}")

    while next_url and pages_fetched < max_pages:
        page_events, next_url_from_page = _fetch_single_events_page(url=next_url, headers=headers, page_num=pages_fetched + 1, username_for_context=username)

        if page_events is None:  # An error occurred in _fetch_single_events_page
            logger.error(f"Halting event fetch for {username} due to error on page {pages_fetched + 1}.")
            # Return None if a page fetch fails critically, or all_events if partial results are acceptable.
            # For this function, returning None on critical page error seems appropriate.
            return None

        all_events.extend(page_events)
        logger.info(f"Fetched {len(page_events)} events from page {pages_fetched + 1}. Total so far: {len(all_events)}.")
        pages_fetched += 1
        next_url = next_url_from_page  # Update next_url for the loop

    logger.info(f"Finished fetching events for {username}. Total: {len(all_events)} from {pages_fetched} pages.")
    return all_events


def find_push_events_in_date_range(events: Optional[List[GitHubEvent]], start_date: date, end_date: date) -> bool:
    """Check if any PushEvents occurred within the given date range (inclusive).

    Args:
        events: A list of GitHub event objects, or None.
        start_date: The start date of the range (inclusive).
        end_date: The end date of the range (inclusive).

    Returns:
        True if a PushEvent from the date range is found, False otherwise.
    """
    if not events:
        logger.info("No events provided for push event check.")
        return False

    logger.info(f"Processing {len(events)} events for commits between {start_date} and {end_date}.")
    for event in events:
        event_date = event.created_at.date()
        if event.type == "PushEvent" and start_date <= event_date <= end_date:
            logger.info(f"Found a PushEvent in date range: ID {event.id} at {event.created_at}")
            return True
    logger.info(f"No PushEvents found between {start_date} and {end_date}.")
    return False


def find_todays_push_events(events: Optional[List[GitHubEvent]], today_utc_date: date) -> bool:
    """Check if any PushEvents occurred on the given UTC date.

    Args:
        events: A list of GitHub event objects, or None.
        today_utc_date: The current date in UTC to check against.

    Returns:
        True if a PushEvent from today is found, False otherwise.
    """
    return find_push_events_in_date_range(events, today_utc_date, today_utc_date)


def _parse_prs_from_items(pr_items_data: list, page_num: int) -> List[PullRequestSimple]:
    """Parses a list of PR item data into PullRequestSimple objects."""
    parsed_prs: List[PullRequestSimple] = []
    for pr_item_data in pr_items_data:
        try:
            parsed_prs.append(PullRequestSimple(**pr_item_data))
        except ValidationError as e:
            logger.warning(f"Skipping PR item due to Pydantic error on page {page_num}: {e}. Data: {pr_item_data}")
        except TypeError as e:
            logger.warning(f"Skipping PR item due to TypeError on page {page_num}: {e}. Data: {pr_item_data}")
    return parsed_prs


def _fetch_single_prs_page(
    search_url: str, headers: dict, params: dict, page_num: int, username_for_context: str
) -> tuple[Optional[List[PullRequestSimple]], bool, int]:  # pr_list, has_more_pages_ind, total_count_from_page
    """Fetches a single page of PRs and returns PRs, an indicator for more pages, and total count."""
    logger.info(f"Fetching PRs page {page_num} from {search_url} with params: {params}")
    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        search_results = response.json()

        if not isinstance(search_results, dict) or "items" not in search_results:
            logger.error(f"Expected dict with 'items' from search API page {page_num}, got {type(search_results)}.")
            return None, False, 0

        items = search_results.get("items", [])
        if not isinstance(items, list):
            logger.error(f"Expected 'items' to be a list, got {type(items)} on page {page_num}.")
            return None, False, 0

        parsed_page_prs = _parse_prs_from_items(items, page_num)
        total_count_from_page = search_results.get("total_count", 0)

        # Determine if there are more pages
        # The Search API doesn't always provide a 'next' link header reliably for the last page.
        # We check if the number of items fetched so far is less than total_count.
        # And ensure there were items on the current page, as an empty last page is possible.
        has_more_github_side = bool(response.links.get("next", {}).get("url"))
        # If Link header says no more, or if items is empty (even if total_count > fetched_count due to eventual consistency)
        if not items:  # No items on this page, definitely no more from this path
            has_more_github_side = False

        return parsed_page_prs, has_more_github_side, total_count_from_page

    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            _handle_github_api_http_error(e.response, context=f"PR search for {username_for_context}, page {page_num}")
        else:
            logger.error(f"HTTP error for PR search page {page_num} (user: {username_for_context}): {e}")
        return None, False, 0
    except requests.exceptions.RequestException as e:  # Includes Timeout, ConnectionError etc.
        logger.error(f"Request error fetching PRs for {username_for_context} page {page_num}: {e}")
        return None, False, 0
    except ValueError as e:  # Includes JSONDecodeError
        logger.error(f"JSON decode error fetching PRs for {username_for_context} page {page_num}: {e}")
        return None, False, 0


def fetch_user_pull_requests(
    username: str, search_query_type: str = "author", token: Optional[str] = None, max_pages: int = 5, sort: str = "updated", order: str = "desc"
) -> Optional[List[PullRequestSimple]]:
    """Fetch pull requests associated with a user via the GitHub Search API.

    Args:
        username: The GitHub username.
        search_query_type: The role of the user in the PRs to search for (e.g., author, assignee, mentions, involves).
        token: An optional GitHub Personal Access Token.
        max_pages: Maximum number of pages to fetch.
        sort: The field to sort results by (e.g., created, updated, comments).
        order: The direction of the sort (asc, desc).

    Returns:
        A list of PullRequestSimple objects if successful, None otherwise.
    """
    if not username:
        logger.error("GitHub username cannot be empty for fetching pull requests.")
        return None

    query = f"{search_query_type}:{username} is:pr"
    search_url = "https://api.github.com/search/issues"
    headers = {"Accept": "application/vnd.github.v3+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    all_pull_requests: List[PullRequestSimple] = []
    pages_fetched = 0
    current_page_num_for_api = 1  # Search API uses 1-based indexing for 'page' param
    has_more_pages = True  # Assume there are pages to fetch initially

    logger.info(f"Fetching PRs for {username} ({search_query_type}). Query: '{query}'. Max pages: {max_pages}")

    while has_more_pages and pages_fetched < max_pages:
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": "100",  # Max allowed by GitHub Search API
            "page": str(current_page_num_for_api),
        }

        page_prs, has_more_from_page, total_count = _fetch_single_prs_page(
            search_url=search_url, headers=headers, params=params, page_num=current_page_num_for_api, username_for_context=username
        )

        if page_prs is None:  # Critical error fetching page
            logger.error(f"Halting PR fetch for {username} due to error on page {current_page_num_for_api}.")
            return None

        all_pull_requests.extend(page_prs)
        logger.info(f"Fetched {len(page_prs)} PRs from page {current_page_num_for_api}. Total so far: {len(all_pull_requests)}.")

        pages_fetched += 1
        current_page_num_for_api += 1
        has_more_pages = has_more_from_page

        # Additional check: if we've fetched all reported items, stop.
        if total_count > 0 and len(all_pull_requests) >= total_count:
            has_more_pages = False

        if not page_prs and pages_fetched == 1 and total_count == 0:  # No items on first page itself
            logger.info(f"No PRs found for query: {query} on the first page.")
            # has_more_pages will be False, loop will terminate

    logger.info(f"Finished fetching PRs for {username} ({search_query_type}). Total: {len(all_pull_requests)} from {pages_fetched} pages.")
    return all_pull_requests


def find_commits_last_days(username: str, days: int = 3, token: Optional[str] = None, max_event_pages: int = 5) -> bool:
    """Checks for any public commit events (PushEvents) by the user in the last N days.

    Args:
        username: The GitHub username.
        days: Number of days to check back from today (default: 3).
        token: An optional GitHub Personal Access Token.
        max_event_pages: Maximum number of event pages to fetch.

    Returns:
        True if commit activity is found in the last N days, False otherwise.
    """
    logger.info(f"Checking for commits in the last {days} days for user '{username}'")
    today_utc = datetime.now(timezone.utc).date()
    start_date = today_utc - timedelta(days=days - 1)  # Include today in the range

    user_events = fetch_github_user_public_events(username, token, max_pages=max_event_pages)

    if not user_events:
        logger.info(f"No public events found for '{username}' or failed to fetch.")
        return False

    return find_push_events_in_date_range(user_events, start_date, today_utc)


def find_todays_commits(username: str, token: Optional[str] = None, max_event_pages: int = 5) -> bool:
    """Checks for any public commit events (PushEvents) by the user for the current UTC date.

    Args:
        username: The GitHub username.
        token: An optional GitHub Personal Access Token.
        max_event_pages: Maximum number of event pages to fetch.

    Returns:
        True if commit activity is found for today, False otherwise.
    """
    logger.info(f"Checking for today's commits for user '{username}'")
    today_utc = datetime.now(timezone.utc).date()
    user_events = fetch_github_user_public_events(username, token, max_pages=max_event_pages)

    if not user_events:
        logger.info(f"No public events found for '{username}' or failed to fetch.")
        return False

    return find_todays_push_events(user_events, today_utc)  # Reuse existing logic


def find_prs_last_days(
    username: str,
    days: int = 3,
    token: Optional[str] = None,
    max_pr_pages: int = 2,  # PR search can be extensive; limit default pages
) -> bool:
    """Checks for PRs created or updated in the last N days by/involving the user.

    Args:
        username: The GitHub username.
        days: Number of days to check back from today (default: 3).
        token: Optional GitHub Personal Access Token.
        max_pr_pages: Maximum number of PR pages to search.

    Returns:
        True if relevant PR activity is found in the last N days, False otherwise.
    """
    logger.info(f"Checking for PRs in the last {days} days involving user '{username}'")
    today_utc_date = datetime.now(timezone.utc).date()
    start_date = today_utc_date - timedelta(days=days - 1)  # Include today in the range

    # Search for PRs involving the user, updated recently.
    # The `fetch_user_pull_requests` already sorts by updated desc by default.
    prs = fetch_user_pull_requests(
        username=username,
        search_query_type="involves",  # Broad search for user involvement
        token=token,
        max_pages=max_pr_pages,
        sort="updated",
        order="desc",
    )

    if not prs:
        logger.info(f"No PRs found involving '{username}' (within page limits) or failed to fetch.")
        return False

    for pr in prs:
        # Check if PR was created in date range OR updated in date range.
        # PullRequestSimple model has created_at and updated_at as datetime objects.
        pr_created_date = pr.created_at.date()
        pr_updated_date = pr.updated_at.date()

        if start_date <= pr_created_date <= today_utc_date or start_date <= pr_updated_date <= today_utc_date:
            logger.info(f"Found PR #{pr.number} ('{pr.title}') active in date range (created: {pr_created_date}, updated: {pr_updated_date}).")
            return True

    logger.info(f"No PRs involving '{username}' found to be active in the last {days} days.")
    return False


def find_todays_prs(
    username: str,
    token: Optional[str] = None,
    max_pr_pages: int = 2,  # PR search can be extensive; limit default pages
) -> bool:
    """Checks for PRs created or updated today by/involving the user.

    Args:
        username: The GitHub username.
        token: Optional GitHub Personal Access Token.
        max_pr_pages: Maximum number of PR pages to search.

    Returns:
        True if relevant PR activity is found for today, False otherwise.
    """
    return find_prs_last_days(username, days=1, token=token, max_pr_pages=max_pr_pages)
