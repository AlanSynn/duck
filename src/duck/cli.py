"""Command-line interface for DUCK (Did U Commit mr.Kim?).

This module provides the entry point for the `duck` command-line tool.
It checks for daily GitHub activity (commits and PRs) for a specified user.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone  # Keep for date operations
from pathlib import Path
from typing import Any, Dict, Optional

import toml

from duck.core import (
    DEFAULT_MAX_EVENT_PAGES,
    DEFAULT_MAX_PR_PAGES,
    find_todays_commits,
    find_todays_prs,
)

logger = logging.getLogger(__name__)
CONFIG_FILE_NAME = "config.toml"

# Default exit codes
EXIT_CODE_SUCCESS = 0
EXIT_CODE_NO_ACTIVITY = 1
EXIT_CODE_USER_MISSING = 2
EXIT_CODE_ERROR = 3


def setup_logging(verbose: int = 0) -> None:
    """Configure logging based on verbosity level."""
    log_level = logging.INFO
    if verbose == 1 or verbose >= 2:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if verbose >= 2:
        logger.info(f"Logging level set to DEBUG (verbosity: {verbose}).")
    else:
        logger.info(f"Logging level set to {logging.getLevelName(log_level)}.")


def load_config() -> Dict[str, Any]:
    """Load configuration from config.toml in the project root."""
    config_path = Path(CONFIG_FILE_NAME)
    if config_path.exists() and config_path.is_file():
        try:
            logger.info(f"Loading configuration from {config_path.resolve()}")
            with open(config_path, "r", encoding="utf-8") as f:
                return toml.load(f)
        except Exception as e:
            logger.warning(f"Could not load or parse {config_path}: {e}")
    else:
        logger.info(f"Configuration file {config_path} not found. Using defaults and environment variables.")
    return {}


def handle_check(args: argparse.Namespace, github_user: str, github_token: Optional[str]) -> int:
    """Handles the main logic for checking commits and PRs."""
    logger.info(f"Executing DUCK check for {github_user}")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info(f"Checking for commits and PRs made by '{github_user}' on {today_str} (UTC).")

    max_event_pages = args.max_event_pages
    max_pr_pages = args.max_pr_pages

    try:
        commits_found_today = find_todays_commits(github_user, github_token, max_event_pages=max_event_pages)
        prs_found_today = find_todays_prs(github_user, github_token, max_pr_pages=max_pr_pages)

        if commits_found_today or prs_found_today:
            logger.info(f"QUACK! Activity found for '{github_user}' today ({today_str} UTC).")
            return EXIT_CODE_SUCCESS
        else:
            logger.warning(f"No commits or PRs found for '{github_user}' today. Don't be a DUCK! Time to make some contributions. (Exit code {EXIT_CODE_NO_ACTIVITY})")
            return EXIT_CODE_NO_ACTIVITY

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return EXIT_CODE_ERROR


def main() -> int:
    """Main entry point for the DUCK CLI."""
    parser = argparse.ArgumentParser(description="DUCK (Did U Commit mr.Kim?) - Checks for daily GitHub activity.")
    parser.add_argument("--user", type=str, help="GitHub username to check.")
    parser.add_argument("--token", type=str, help="GitHub Personal Access Token.")
    parser.add_argument("--max-event-pages", type=int, help="Maximum number of commit event pages to fetch.")
    parser.add_argument("--max-pr-pages", type=int, help="Maximum number of pull request pages to fetch.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v, -vv).")

    args = parser.parse_args()
    setup_logging(args.verbose)

    config = load_config()
    github_config = config.get("github", {})

    # Determine configuration with precedence: CLI > Env > Config > Default
    github_user = args.user or os.getenv("GITHUB_USERNAME") or github_config.get("username")
    github_token = args.token or os.getenv("GITHUB_TOKEN") or github_config.get("token")

    # Default values for max pages if not provided by CLI, Env, or Config
    # Env var names for max pages
    env_max_event_pages = os.getenv("DUCK_MAX_EVENT_PAGES")
    env_max_pr_pages = os.getenv("DUCK_MAX_PR_PAGES")

    args.max_event_pages = (
        args.max_event_pages
        if args.max_event_pages is not None
        else int(env_max_event_pages)
        if env_max_event_pages is not None
        else github_config.get("max_event_pages", DEFAULT_MAX_EVENT_PAGES)
    )
    args.max_pr_pages = (
        args.max_pr_pages
        if args.max_pr_pages is not None
        else int(env_max_pr_pages)
        if env_max_pr_pages is not None
        else github_config.get("max_pr_pages", DEFAULT_MAX_PR_PAGES)
    )

    if not github_user:
        logger.error("GitHub username required. Please provide it via --user argument, GITHUB_USERNAME environment variable, or in config.toml.")
        return EXIT_CODE_USER_MISSING

    # Call the synchronous handler directly
    return handle_check(args, github_user, github_token)


if __name__ == "__main__":
    sys.exit(main())
