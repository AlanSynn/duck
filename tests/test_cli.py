"""Tests for the simplified duck.cli module."""

import logging # Added for caplog.set_level
import sys
from unittest.mock import MagicMock, patch

import pytest

from duck import cli
from duck.core import DEFAULT_MAX_EVENT_PAGES, DEFAULT_MAX_PR_PAGES

# EXIT_CODE constants from cli module for clarity in tests
EXIT_CODE_SUCCESS = cli.EXIT_CODE_SUCCESS
EXIT_CODE_NO_ACTIVITY = cli.EXIT_CODE_NO_ACTIVITY
EXIT_CODE_USER_MISSING = cli.EXIT_CODE_USER_MISSING
EXIT_CODE_ERROR = cli.EXIT_CODE_ERROR


# Helper to run cli.main with specific argv and get its direct integer return
def run_cli_main_and_get_code(argv):
    with patch.object(sys, "argv", argv):
        return cli.main()

@pytest.fixture(autouse=True)
def mock_load_config():
    """Auto-applied fixture to mock config loading."""
    with patch("duck.cli.load_config", return_value={}) as mock_config:
        yield mock_config

@pytest.fixture
def mock_core_functions():
    """Fixture to mock the core synchronous functions find_todays_commits and find_todays_prs."""
    with patch("duck.cli.find_todays_commits", return_value=False) as mock_commits, \
         patch("duck.cli.find_todays_prs", return_value=False) as mock_prs:
        yield {"commits": mock_commits, "prs": mock_prs}


# Basic command invocation tests

def test_main_command_no_user(mock_core_functions, caplog):
    """Test CLI exits with error if no username is provided (env or --user)."""
    with patch.dict(cli.os.environ, {}, clear=True):
        exit_code = run_cli_main_and_get_code(["duck"])
    assert exit_code == EXIT_CODE_USER_MISSING
    assert "GitHub username required" in caplog.text
    mock_core_functions["commits"].assert_not_called()
    mock_core_functions["prs"].assert_not_called()

def test_main_command_with_env_user_no_activity(mock_core_functions, caplog):
    """Test CLI with username from env, no activity found."""
    caplog.set_level(logging.WARNING) # Ensure WARNING level logs are captured
    mock_core_functions["commits"].return_value = False
    mock_core_functions["prs"].return_value = False

    # Explicitly set environment for this test, ensuring GITHUB_TOKEN is absent
    test_env = {"GITHUB_USERNAME": "envuser"}
    with patch.dict(cli.os.environ, test_env, clear=True):
        exit_code = run_cli_main_and_get_code(["duck"])

    assert exit_code == EXIT_CODE_NO_ACTIVITY
    assert "No commits or PRs found for 'envuser' today." in caplog.text
    mock_core_functions["commits"].assert_called_once_with(
        "envuser", None, max_event_pages=DEFAULT_MAX_EVENT_PAGES
    )
    mock_core_functions["prs"].assert_called_once_with(
        "envuser", None, max_pr_pages=DEFAULT_MAX_PR_PAGES
    )

def test_main_command_with_cli_user_commits_found(mock_core_functions, caplog):
    """Test CLI with --user and --token, commits found."""
    caplog.set_level(logging.INFO) # Ensure INFO level logs are captured
    mock_core_functions["commits"].return_value = True
    mock_core_functions["prs"].return_value = False

    # Clear GITHUB_TOKEN from env to ensure --token clitoken is used
    with patch.dict(cli.os.environ, {}, clear=True):
        exit_code = run_cli_main_and_get_code([
            "duck", "--user", "cliuser", "--token", "clitoken"
        ])

    assert exit_code == EXIT_CODE_SUCCESS
    assert "QUACK! Activity found for 'cliuser' today" in caplog.text
    mock_core_functions["commits"].assert_called_once_with(
        "cliuser", "clitoken", max_event_pages=DEFAULT_MAX_EVENT_PAGES
    )
    mock_core_functions["prs"].assert_called_once_with(
        "cliuser", "clitoken", max_pr_pages=DEFAULT_MAX_PR_PAGES
    )

def test_main_command_with_cli_user_prs_found(mock_core_functions, caplog):
    """Test CLI with --user, PRs found."""
    caplog.set_level(logging.INFO)
    mock_core_functions["commits"].return_value = False
    mock_core_functions["prs"].return_value = True

    # GITHUB_TOKEN is set from env, GITHUB_USERNAME is from CLI
    test_env = {"GITHUB_TOKEN": "envtoken"}
    # Ensure GITHUB_USERNAME is not in test_env if we are testing CLI override for user
    # but this test is about CLI user and env token, so GITHUB_USERNAME should not be in env.
    with patch.dict(cli.os.environ, test_env, clear=True):
        exit_code = run_cli_main_and_get_code([
            "duck", "--user", "cliuser2"
        ])

    assert exit_code == EXIT_CODE_SUCCESS
    assert "QUACK! Activity found for 'cliuser2' today" in caplog.text
    mock_core_functions["commits"].assert_called_once_with(
        "cliuser2", "envtoken", max_event_pages=DEFAULT_MAX_EVENT_PAGES
    )
    mock_core_functions["prs"].assert_called_once_with(
        "cliuser2", "envtoken", max_pr_pages=DEFAULT_MAX_PR_PAGES
    )

def test_main_command_both_commits_and_prs_found(mock_core_functions, caplog):
    """Test CLI, both commits and PRs found."""
    caplog.set_level(logging.INFO)
    mock_core_functions["commits"].return_value = True
    mock_core_functions["prs"].return_value = True

    # GITHUB_USERNAME from env, token should be None
    test_env = {"GITHUB_USERNAME": "testuser3"}
    with patch.dict(cli.os.environ, test_env, clear=True):
        exit_code = run_cli_main_and_get_code(["duck"])

    assert exit_code == EXIT_CODE_SUCCESS
    assert "QUACK! Activity found for 'testuser3' today" in caplog.text
    mock_core_functions["commits"].assert_called_once_with("testuser3", None, max_event_pages=DEFAULT_MAX_EVENT_PAGES)
    mock_core_functions["prs"].assert_called_once_with("testuser3", None, max_pr_pages=DEFAULT_MAX_PR_PAGES)


# Test argument parsing
def test_max_event_pages_arg(mock_core_functions, caplog):
    """Test --max-event-pages argument is passed correctly."""
    caplog.set_level(logging.WARNING) # Expecting no activity warning
    test_env = {"GITHUB_USERNAME": "testuser"} # No GITHUB_TOKEN
    with patch.dict(cli.os.environ, test_env, clear=True):
        run_cli_main_and_get_code(["duck", "--max-event-pages", "3"])
    mock_core_functions["commits"].assert_called_once_with(
        "testuser", None, max_event_pages=3
    )
    mock_core_functions["prs"].assert_called_once_with(
        "testuser", None, max_pr_pages=DEFAULT_MAX_PR_PAGES
    )

def test_max_pr_pages_arg(mock_core_functions, caplog):
    """Test --max-pr-pages argument is passed correctly."""
    caplog.set_level(logging.WARNING)
    test_env = {"GITHUB_USERNAME": "testuser"}
    with patch.dict(cli.os.environ, test_env, clear=True):
        run_cli_main_and_get_code(["duck", "--max-pr-pages", "4"])
    mock_core_functions["commits"].assert_called_once_with(
        "testuser", None, max_event_pages=DEFAULT_MAX_EVENT_PAGES
    )
    mock_core_functions["prs"].assert_called_once_with(
        "testuser", None, max_pr_pages=4
    )

def test_both_max_pages_args(mock_core_functions, caplog):
    """Test both --max-event-pages and --max-pr-pages arguments."""
    caplog.set_level(logging.WARNING)
    test_env = {"GITHUB_USERNAME": "testuser"}
    with patch.dict(cli.os.environ, test_env, clear=True):
        run_cli_main_and_get_code([
            "duck",
            "--max-event-pages", "2",
            "--max-pr-pages", "1"
        ])
    mock_core_functions["commits"].assert_called_once_with(
        "testuser", None, max_event_pages=2
    )
    mock_core_functions["prs"].assert_called_once_with(
        "testuser", None, max_pr_pages=1
    )

# Test config file integration
def test_config_file_values_used(mock_load_config, mock_core_functions, caplog):
    """Test values from mocked config file are used if CLI/env not set."""
    caplog.set_level(logging.INFO)
    mock_load_config.return_value = {
        "github": {"username": "configuser", "token": "configtoken"},
        "max_event_pages": 7,
        "max_pr_pages": 6
    }
    mock_core_functions["commits"].return_value = True # Activity found

    # Clear relevant env vars to ensure config is used
    with patch.dict(cli.os.environ, {}, clear=True):
        exit_code = run_cli_main_and_get_code(["duck"])

    assert exit_code == EXIT_CODE_SUCCESS
    assert "QUACK! Activity found for 'configuser' today" in caplog.text
    mock_core_functions["commits"].assert_called_once_with(
        "configuser", "configtoken", max_event_pages=7
    )
    mock_core_functions["prs"].assert_called_once_with(
        "configuser", "configtoken", max_pr_pages=6
    )


def test_cli_args_override_config_and_env(mock_load_config, mock_core_functions, caplog):
    """Test CLI arguments override config file and environment variables."""
    caplog.set_level(logging.INFO)
    mock_load_config.return_value = {
        "github": {"username": "configuser", "token": "configtoken"},
        "max_event_pages": 10,
        "max_pr_pages": 9
    }
    env_vars = {
        "GITHUB_USERNAME": "envuser",
        "GITHUB_TOKEN": "envtoken",
        "DUCK_MAX_EVENT_PAGES": "8",
        "DUCK_MAX_PR_PAGES": "7"
    }
    mock_core_functions["prs"].return_value = True # Activity found

    with patch.dict(cli.os.environ, env_vars):
        exit_code = run_cli_main_and_get_code([
            "duck",
            "--user", "cliuser",
            "--token", "clitoken",
            "--max-event-pages", "3",
            "--max-pr-pages", "2"
        ])

    assert exit_code == EXIT_CODE_SUCCESS
    assert "QUACK! Activity found for 'cliuser' today" in caplog.text
    mock_core_functions["commits"].assert_called_once_with(
        "cliuser", "clitoken", max_event_pages=3
    )
    mock_core_functions["prs"].assert_called_once_with(
        "cliuser", "clitoken", max_pr_pages=2
    )

# Test error handling for core function failures
def test_core_function_exception(mock_core_functions, caplog):
    """Test CLI handles exceptions from core functions gracefully."""
    caplog.set_level(logging.ERROR) # Expecting ERROR level log for exception
    mock_core_functions["commits"].side_effect = Exception("Core function exploded!")

    # Ensure GITHUB_TOKEN is not present to simplify variable resolution path
    test_env = {"GITHUB_USERNAME": "erroruser"}
    with patch.dict(cli.os.environ, test_env, clear=True):
        exit_code = run_cli_main_and_get_code(["duck"])

    assert exit_code == EXIT_CODE_ERROR
    assert "An unexpected error occurred: Core function exploded!" in caplog.text
    mock_core_functions["commits"].assert_called_once()
    mock_core_functions["prs"].assert_not_called()


@pytest.mark.parametrize("verbose_args, expected_count", [
    ([], 0),
    (["-v"], 1),
    (["-vv"], 2),
    (["-vvv"], 3) # Max verbosity in current setup_logging implies DEBUG
])
def test_verbosity_settings(verbose_args, expected_count, caplog):
    """Test different verbosity levels correctly configure logging."""
    cli_args = ["duck", "--user", "testuser"] + verbose_args

    with patch("duck.cli.setup_logging") as mock_setup_logging, \
         patch("duck.cli.handle_check", return_value=EXIT_CODE_SUCCESS): # Mock handle_check
        run_cli_main_and_get_code(cli_args)

        mock_setup_logging.assert_called_once()
        # setup_logging is called with the integer value of args.verbose
        actual_verbose_value_passed = mock_setup_logging.call_args[0][0]
        assert actual_verbose_value_passed == expected_count

    # Test the case where username is missing (and no verbose flags from parametrize).
    # setup_logging should still be called with default verbosity (0).
    if not verbose_args: # This will only run for the ([], 0) case from parametrize
        with patch("duck.cli.setup_logging") as mock_setup_logging_no_user, \
             patch.dict(cli.os.environ, {}, clear=True), \
             patch("duck.cli.handle_check"): # Mock handle_check as it won't be called

            exit_code = run_cli_main_and_get_code(["duck"]) # No user, no cli verbose flags

            assert exit_code == EXIT_CODE_USER_MISSING
            mock_setup_logging_no_user.assert_called_once()
            actual_verbose_value_no_user = mock_setup_logging_no_user.call_args[0][0]
            assert actual_verbose_value_no_user == 0 # Default verbosity count is 0
