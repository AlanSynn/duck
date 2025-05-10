"""Data models for DUCK.

This module defines Pydantic models for GitHub API data and other internal data structures.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GitHubEvent(BaseModel):
    """Model for a GitHub event.

    Attributes:
        id: The unique identifier for this event.
        type: The type of event (e.g., "PushEvent").
        created_at: The UTC timestamp when this event was created.
        actor: Optional details about the user who performed the action.
        payload: Optional payload details of the event.
    """

    id: str
    type: str
    created_at: datetime = Field(alias="created_at")
    actor: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value: Any) -> datetime:
        """Parse and validate the created_at timestamp.

        Args:
            value: The timestamp to parse (string or datetime).

        Returns:
            A datetime object in UTC timezone.

        Raises:
            ValueError: If the value cannot be parsed as a datetime.
        """
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        raise ValueError(f"Invalid datetime format for created_at: {value}")

    model_config = ConfigDict(
        populate_by_name=True,  # Replaces allow_population_by_field_name
        extra="ignore",  # Ignore extra fields from API response
    )


# Placeholder for future models (e.g., CommitDetails, PRDetails, InsightReport)


class CommitAuthor(BaseModel):
    """Model for the author of a commit (simplified)."""

    name: Optional[str] = None
    email: Optional[str] = None
    date: Optional[datetime] = None  # Commit date by the author

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, value: Any) -> Optional[datetime]:
        """Parse and validate the date field.

        Args:
            value: The date to parse (string or datetime).

        Returns:
            A datetime object in UTC timezone.

        Raises:
            ValueError: If the value cannot be parsed as a datetime.
        """
        if value is None:
            return None
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        raise ValueError(f"Invalid datetime format for date: {value}")

    model_config = ConfigDict(
        extra="ignore"  # Assuming ignore if not specified, though not strictly needed if no Config class was there
    )


class CommitDetails(BaseModel):
    """Model for the details of a commit (the 'commit' object in API response)."""

    author: Optional[CommitAuthor] = None
    committer: Optional[CommitAuthor] = None  # Committer can be different from author
    message: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class Commit(BaseModel):
    """Model for a single commit from the GitHub API.

    Represents an item from /repos/{owner}/{repo}/commits endpoint.

    Attributes:
        sha: The SHA-1 hash of the commit.
        html_url: The URL to the commit on GitHub.
        commit: The details of the commit.
        author: The user object for the author, if available.
        committer: The user object for the committer, if available.
    """

    sha: str
    html_url: Optional[str] = Field(None, alias="html_url")
    commit: CommitDetails
    author: Optional[Dict[str, Any]] = None  # User object for the author, if available
    committer: Optional[Dict[str, Any]] = None  # User object for the committer, if available

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Repository(BaseModel):
    """Model for a GitHub repository (simplified)."""

    id: int
    name: str
    full_name: str = Field(alias="full_name")
    private: bool
    html_url: str = Field(alias="html_url")
    description: Optional[str] = None
    fork: bool

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# --- Pull Request Models ---


class PullRequestUser(BaseModel):
    """Simplified model for a user associated with a Pull Request (e.g., author, assignee)."""

    login: str
    id: int
    html_url: Optional[str] = Field(None, alias="html_url")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class PullRequestRepoInfo(BaseModel):
    """Simplified model for repository information within a Pull Request item from search."""

    id: int
    name: str
    full_name: str
    html_url: str

    model_config = ConfigDict(extra="ignore")


class PullRequestSimple(BaseModel):
    """Model for a Pull Request, typically from a search result.

    The GitHub search API returns PRs as "issues" with a "pull_request" field.
    """

    id: int
    html_url: str = Field(alias="html_url")
    number: int
    title: str
    state: str  # "open", "closed"
    locked: bool
    user: Optional[PullRequestUser] = None  # The author of the PR
    body: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None  # This might be part of a separate 'pull_request' object in search result

    # Fields often included directly in search results for PRs
    assignees: Optional[List[PullRequestUser]] = []
    requested_reviewers: Optional[List[PullRequestUser]] = Field(default_factory=list)

    repository_url: Optional[str] = None

    @field_validator("created_at", "updated_at", "closed_at", "merged_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Parse and validate datetime fields.

        Args:
            value: The datetime to parse (string or datetime).

        Returns:
            A datetime object in UTC timezone.

        Raises:
            ValueError: If the value cannot be parsed as a datetime.
        """
        if value is None:
            return None
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        raise ValueError(f"Invalid datetime format: {value}")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")
