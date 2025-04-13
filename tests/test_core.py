"""Tests for the duck.core module."""

from datetime import date as DateObject
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from duck.core import (
    fetch_github_user_public_events,
    fetch_user_pull_requests,
    find_todays_commits,
    find_todays_prs,
    find_todays_push_events,
)
from duck.models import GitHubEvent, PullRequestSimple, PullRequestUser


# Test fixtures for GitHub events
@pytest.fixture
def push_event_today():
    """Return a GitHubEvent object for a PushEvent from today."""
    today = datetime.now(timezone.utc)
    return GitHubEvent(
        id="12345",
        type="PushEvent",
        created_at=today,
        actor={"id": 1, "login": "test-user"},
        payload={"ref": "refs/heads/main", "size": 1},
    )


@pytest.fixture
def non_push_event_today():
    """Return a GitHubEvent object for a non-PushEvent from today."""
    today = datetime.now(timezone.utc)
    return GitHubEvent(
        id="67890",
        type="WatchEvent",
        created_at=today,
        actor={"id": 1, "login": "test-user"},
    )


@pytest.fixture
def push_event_yesterday():
    """Return a GitHubEvent object for a PushEvent from yesterday."""
    now = datetime.now(timezone.utc)
    yesterday_dt = now - timedelta(days=1)
    return GitHubEvent(
        id="54321",
        type="PushEvent",
        created_at=yesterday_dt,
        actor={"id": 1, "login": "test-user"},
        payload={"ref": "refs/heads/main", "size": 1},
    )


# Mock API response for fetch_github_user_public_events
@pytest.fixture
def mock_events_api_response_data():
    return [
        {
            "id": "12345",
            "type": "PushEvent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "actor": {"id": 1, "login": "test-user"},
            "payload": {"ref": "refs/heads/main", "size": 1},
        }
    ]

@pytest.fixture
def mock_requests_get_for_events(mock_events_api_response_data):
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = mock_events_api_response_data
    mock.links = {}
    return mock


# Tests for find_todays_push_events
def test_find_todays_push_events_with_push_today(push_event_today, non_push_event_today, push_event_yesterday):
    events = [push_event_today, non_push_event_today, push_event_yesterday]
    today_utc = datetime.now(timezone.utc).date()
    assert find_todays_push_events(events, today_utc) is True

def test_find_todays_push_events_without_push_today(non_push_event_today, push_event_yesterday):
    events = [non_push_event_today, push_event_yesterday]
    today_utc = datetime.now(timezone.utc).date()
    assert find_todays_push_events(events, today_utc) is False

def test_find_todays_push_events_with_empty_events():
    assert find_todays_push_events([], datetime.now(timezone.utc).date()) is False

def test_find_todays_push_events_with_none_events():
    assert find_todays_push_events(None, datetime.now(timezone.utc).date()) is False


# Tests for fetch_github_user_public_events
@patch("requests.get")
def test_fetch_github_user_public_events_success(mock_get, mock_requests_get_for_events, mock_events_api_response_data):
    mock_get.return_value = mock_requests_get_for_events
    events = fetch_github_user_public_events("test-user")
    assert events is not None
    assert len(events) == 1
    assert events[0].id == mock_events_api_response_data[0]["id"]

@patch("requests.get")
def test_fetch_github_user_public_events_http_error(mock_get):
    mock_resp = MagicMock()
    error_response = requests.Response() # Create a real Response object for the side_effect
    error_response.status_code = 403
    error_response.reason = "Forbidden"
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=error_response)
    mock_resp.status_code = 403 # Match the error_response status
    mock_resp.reason = "Forbidden" # Match the error_response reason
    mock_get.return_value = mock_resp
    # Patch _handle_github_api_http_error to prevent it from logging during tests and check call
    with patch("duck.core._handle_github_api_http_error") as mock_handle_error:
        assert fetch_github_user_public_events("test-user") is None
        mock_handle_error.assert_called_once()

@patch("requests.get")
def test_fetch_github_user_public_events_timeout(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout
    assert fetch_github_user_public_events("test-user") is None

@patch("requests.get")
def test_fetch_github_user_public_events_request_exception(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException
    assert fetch_github_user_public_events("test-user") is None

@patch("requests.get")
def test_fetch_github_user_public_events_json_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError
    mock_get.return_value = mock_resp
    assert fetch_github_user_public_events("test-user") is None

def test_fetch_github_user_public_events_empty_username():
    assert fetch_github_user_public_events("") is None

# Fixtures for PR Data
@pytest.fixture
def sample_pr_user_data_dict(): # as dict
    return {"login": "test-user", "id": 1, "html_url": "https://github.com/test-user"}

@pytest.fixture
def sample_pr_today_model(sample_pr_user_data_dict):
    now_iso = datetime.now(timezone.utc).isoformat()
    return PullRequestSimple(
        id=101,
        html_url="https://github.com/owner/repo/pull/101",
        number=101,
        title="PR Today",
        state="open",
        locked=False,
        user=PullRequestUser(**sample_pr_user_data_dict),
        created_at=now_iso,
        updated_at=now_iso,
        repository_url="https://api.github.com/repos/owner/repo"
    )

@pytest.fixture
def sample_pr_yesterday_model(sample_pr_user_data_dict):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return PullRequestSimple(
        id=102,
        html_url="https://github.com/owner/repo/pull/102",
        number=102,
        title="PR Yesterday",
        state="open",
        locked=False,
        user=PullRequestUser(**sample_pr_user_data_dict),
        created_at=yesterday.isoformat(),
        updated_at=yesterday.isoformat(),
        repository_url="https://api.github.com/repos/owner/repo"
    )

@pytest.fixture
def sample_pr_search_api_item_dict():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "id": 1,
        "number": 1347,
        "state": "open",
        "title": "Amazing new feature",
        "user": {"login": "octocat", "id": 1, "html_url": "https://github.com/octocat"},
        "created_at": now_iso,
        "updated_at": now_iso,
        "html_url": "https://github.com/octocat/Hello-World/pull/1347",
        "repository_url": "https://api.github.com/repos/octocat/Hello-World",
    }

# Tests for fetch_user_pull_requests
@patch("requests.get")
def test_fetch_user_pull_requests_success(mock_get, sample_pr_search_api_item_dict):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"items": [sample_pr_search_api_item_dict], "total_count": 1}
    mock_resp.links = {}
    mock_get.return_value = mock_resp
    prs = fetch_user_pull_requests("test-user")
    assert prs is not None
    assert len(prs) == 1
    assert prs[0].id == sample_pr_search_api_item_dict["id"]

@patch("requests.get")
def test_fetch_user_pull_requests_http_error(mock_get):
    mock_resp = MagicMock()
    error_response = requests.Response()
    error_response.status_code = 403
    error_response.reason = "Forbidden"
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=error_response)
    mock_resp.status_code = 403
    mock_resp.reason = "Forbidden"
    mock_get.return_value = mock_resp
    with patch("duck.core._handle_github_api_http_error") as mock_handle_error:
        assert fetch_user_pull_requests("test-user") is None
        mock_handle_error.assert_called_once()

@patch("requests.get")
def test_fetch_user_pull_requests_empty_response(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"items": [], "total_count": 0}
    mock_resp.links = {}
    mock_get.return_value = mock_resp
    prs = fetch_user_pull_requests("test-user")
    assert prs == []

# --- Tests for new/adapted functions ---

# Tests for find_todays_commits
@patch("duck.core.fetch_github_user_public_events")
@patch("duck.core.find_todays_push_events")
def test_find_todays_commits_found(mock_find_pushes, mock_fetch_events, push_event_today):
    mock_fetch_events.return_value = [push_event_today]
    mock_find_pushes.return_value = True
    result = find_todays_commits("test-user", "fake-token")
    assert result is True
    mock_fetch_events.assert_called_once_with("test-user", "fake-token", max_pages=5)
    assert mock_find_pushes.call_args[0][0] == [push_event_today]
    assert isinstance(mock_find_pushes.call_args[0][1], DateObject)

@patch("duck.core.fetch_github_user_public_events")
@patch("duck.core.find_todays_push_events")
def test_find_todays_commits_not_found_due_to_no_push_event(mock_find_pushes, mock_fetch_events, non_push_event_today):
    mock_fetch_events.return_value = [non_push_event_today]
    mock_find_pushes.return_value = False
    result = find_todays_commits("test-user", "fake-token")
    assert result is False

@patch("duck.core.fetch_github_user_public_events")
def test_find_todays_commits_no_events_fetched(mock_fetch_events):
    mock_fetch_events.return_value = None
    result = find_todays_commits("test-user", "fake-token")
    assert result is False

@patch("duck.core.fetch_github_user_public_events")
def test_find_todays_commits_empty_events_list_fetched(mock_fetch_events):
    mock_fetch_events.return_value = []
    result = find_todays_commits("test-user", "fake-token")
    assert result is False

# Tests for find_todays_prs
@patch("duck.core.fetch_user_pull_requests")
def test_find_todays_prs_found_created_today(mock_fetch_prs, sample_pr_today_model):
    mock_fetch_prs.return_value = [sample_pr_today_model]
    result = find_todays_prs("test-user", "fake-token")
    assert result is True
    mock_fetch_prs.assert_called_once_with(
        username="test-user",
        search_query_type="involves",
        token="fake-token",
        max_pages=2,
        sort="updated",
        order="desc"
    )

@patch("duck.core.fetch_user_pull_requests")
def test_find_todays_prs_found_updated_today(mock_fetch_prs, sample_pr_user_data_dict):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    today = datetime.now(timezone.utc)
    pr_updated_today = PullRequestSimple(
        id=103, html_url="url3", number=103, title="Updated PR",
        state="open", locked=False, user=PullRequestUser(**sample_pr_user_data_dict),
        created_at=yesterday.isoformat(), updated_at=today.isoformat(),
        repository_url="api/owner/repo"
    )
    mock_fetch_prs.return_value = [pr_updated_today]
    result = find_todays_prs("test-user", "fake-token")
    assert result is True

@patch("duck.core.fetch_user_pull_requests")
def test_find_todays_prs_not_found_old_prs(mock_fetch_prs, sample_pr_yesterday_model):
    mock_fetch_prs.return_value = [sample_pr_yesterday_model]
    result = find_todays_prs("test-user", "fake-token")
    assert result is False

@patch("duck.core.fetch_user_pull_requests")
def test_find_todays_prs_no_prs_fetched(mock_fetch_prs):
    mock_fetch_prs.return_value = None
    result = find_todays_prs("test-user", "fake-token")
    assert result is False

@patch("duck.core.fetch_user_pull_requests")
def test_find_todays_prs_empty_pr_list_fetched(mock_fetch_prs):
    mock_fetch_prs.return_value = []
    result = find_todays_prs("test-user", "fake-token")
    assert result is False
