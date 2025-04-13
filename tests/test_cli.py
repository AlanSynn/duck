"""Tests for the simplified duck.cli module."""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

from duck import cli
from duck.core import DEFAULT_MAX_EVENT_PAGES, DEFAULT_MAX_PR_PAGES


# Helper to run cli.main with specific argv and capture SystemExit
def run_cli_main_with_exit_code(argv):
    with patch.object(sys, "argv", argv):
        try:
            return cli.main()
        except SystemExit as e:
            return e.code

@pytest.fixture(autouse=True)
def mock_load_config():
    """Auto-applied fixture to mock config loading."""
    with patch("duck.cli.load_config", return_value={}) as mock_config:
        yield mock_config

@pytest.fixture
def mock_async_core_functions():
    """Fixture to mock the core async functions find_todays_commits and find_todays_prs."""
    # We need to mock the functions within the asyncio.run call in handle_check
    # So we patch them where they are imported in cli.py
    with patch("duck.cli.find_todays_commits", new_callable=MagicMock) as mock_commits, \
         patch("duck.cli.find_todays_prs", new_callable=MagicMock) as mock_prs:
        # Configure the mocks to be awaitable and return a default value
        mock_commits.return_value = asyncio.Future()
        mock_commits.return_value.set_result(False) # Default to no commits
        mock_prs.return_value = asyncio.Future()
        mock_prs.return_value.set_result(False) # Default to no PRs
        yield {"commits": mock_commits, "prs": mock_prs}


# Basic command invocation tests

def test_main_command_no_user(mock_async_core_functions, caplog):
    """Test CLI exits with error if no username is provided (env or --user)."""
    # Ensure GITHUB_USERNAME is not in env for this test
    with patch.dict(cli.os.environ, {}, clear=True):
        exit_code = run_cli_main_with_exit_code(["duck"])
    assert exit_code == 2
    assert "GitHub username required" in caplog.text
    mock_async_core_functions["commits"].assert_not_called()
    mock_async_core_functions["prs"].assert_not_called()

def test_main_command_with_env_user_no_activity(mock_async_core_functions, caplog):
    """Test CLI with username from env, no activity found."""
    mock_async_core_functions["commits"].return_value.set_result(False)
    mock_async_core_functions["prs"].return_value.set_result(False)

    with patch.dict(cli.os.environ, {"GITHUB_USERNAME": "envuser"}):
        exit_code = run_cli_main_with_exit_code(["duck"])

    assert exit_code == 1 # Exit code 1 for no activity
    assert "No commits or PRs found for 'envuser' today." in caplog.text
    mock_async_core_functions["commits"].assert_called_once_with(
        "envuser", None, DEFAULT_MAX_EVENT_PAGES
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "envuser", None, DEFAULT_MAX_PR_PAGES
    )

def test_main_command_with_cli_user_commits_found(mock_async_core_functions, caplog):
    """Test CLI with --user and --token, commits found."""
    mock_async_core_functions["commits"].return_value.set_result(True)
    mock_async_core_functions["prs"].return_value.set_result(False)

    exit_code = run_cli_main_with_exit_code([
        "duck", "--user", "cliuser", "--token", "clitoken"
    ])

    assert exit_code == 0 # Exit code 0 for activity found
    assert "QUACK! Activity found for 'cliuser' today." in caplog.text
    mock_async_core_functions["commits"].assert_called_once_with(
        "cliuser", "clitoken", DEFAULT_MAX_EVENT_PAGES
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "cliuser", "clitoken", DEFAULT_MAX_PR_PAGES
    )

def test_main_command_with_cli_user_prs_found(mock_async_core_functions, caplog):
    """Test CLI with --user, PRs found."""
    mock_async_core_functions["commits"].return_value.set_result(False)
    mock_async_core_functions["prs"].return_value.set_result(True)

    with patch.dict(cli.os.environ, {"GITHUB_TOKEN": "envtoken"}): # Token from env
        exit_code = run_cli_main_with_exit_code([
            "duck", "--user", "cliuser2"
        ])

    assert exit_code == 0
    assert "QUACK! Activity found for 'cliuser2' today." in caplog.text
    mock_async_core_functions["commits"].assert_called_once_with(
        "cliuser2", "envtoken", DEFAULT_MAX_EVENT_PAGES
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "cliuser2", "envtoken", DEFAULT_MAX_PR_PAGES
    )

def test_main_command_both_commits_and_prs_found(mock_async_core_functions, caplog):
    """Test CLI, both commits and PRs found."""
    mock_async_core_functions["commits"].return_value.set_result(True)
    mock_async_core_functions["prs"].return_value.set_result(True)

    with patch.dict(cli.os.environ, {"GITHUB_USERNAME": "testuser3"}):
        exit_code = run_cli_main_with_exit_code(["duck"])

    assert exit_code == 0
    assert "QUACK! Activity found for 'testuser3' today." in caplog.text

# Test argument parsing
def test_max_event_pages_arg(mock_async_core_functions):
    """Test --max-event-pages argument is passed correctly."""
    with patch.dict(cli.os.environ, {"GITHUB_USERNAME": "testuser"}):
        run_cli_main_with_exit_code(["duck", "--max-event-pages", "3"])
    mock_async_core_functions["commits"].assert_called_once_with(
        "testuser", None, 3
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "testuser", None, DEFAULT_MAX_PR_PAGES # PR pages should use default
    )

def test_max_pr_pages_arg(mock_async_core_functions):
    """Test --max-pr-pages argument is passed correctly."""
    with patch.dict(cli.os.environ, {"GITHUB_USERNAME": "testuser"}):
        run_cli_main_with_exit_code(["duck", "--max-pr-pages", "4"])
    mock_async_core_functions["commits"].assert_called_once_with(
        "testuser", None, DEFAULT_MAX_EVENT_PAGES # Event pages should use default
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "testuser", None, 4
    )

def test_both_max_pages_args(mock_async_core_functions):
    """Test both --max-event-pages and --max-pr-pages arguments."""
    with patch.dict(cli.os.environ, {"GITHUB_USERNAME": "testuser"}):
        run_cli_main_with_exit_code([
            "duck",
            "--max-event-pages", "2",
            "--max-pr-pages", "1"
        ])
    mock_async_core_functions["commits"].assert_called_once_with(
        "testuser", None, 2
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "testuser", None, 1
    )

# Test config file integration (mocked for now, but shows intent)
def test_config_file_token_used(mock_load_config, mock_async_core_functions, caplog):
    """Test token from mocked config file is used if CLI/env token not set."""
    mock_load_config.return_value = {
        "github_token": "configtoken",
        "max_event_pages": 7,
        "max_pr_pages": 6
    }
    mock_async_core_functions["commits"].return_value.set_result(True) # Activity found

    with patch.dict(cli.os.environ, {"GITHUB_USERNAME": "configuser"}, clear=True):
        exit_code = run_cli_main_with_exit_code(["duck"])

    assert exit_code == 0
    assert "QUACK! Activity found for 'configuser' today." in caplog.text
    mock_async_core_functions["commits"].assert_called_once_with(
        "configuser", "configtoken", 7
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "configuser", "configtoken", 6
    )

def test_cli_args_override_config_and_env(mock_load_config, mock_async_core_functions, caplog):
    """Test CLI arguments override config file and environment variables."""
    mock_load_config.return_value = {"github_token": "configtoken", "max_event_pages": 10}
    env_vars = {"GITHUB_USERNAME": "envuser", "GITHUB_TOKEN": "envtoken"}
    mock_async_core_functions["prs"].return_value.set_result(True) # Activity found

    with patch.dict(cli.os.environ, env_vars):
        exit_code = run_cli_main_with_exit_code([
            "duck",
            "--user", "cliuser",
            "--token", "clitoken",
            "--max-event-pages", "3",
            "--max-pr-pages", "2"
        ])

    assert exit_code == 0
    assert "QUACK! Activity found for 'cliuser' today." in caplog.text
    mock_async_core_functions["commits"].assert_called_once_with(
        "cliuser", "clitoken", 3
    )
    mock_async_core_functions["prs"].assert_called_once_with(
        "cliuser", "clitoken", 2
    )

# Test error handling for core function failures
@patch("duck.cli.asyncio.run") # Patch asyncio.run itself to simulate exception during its execution
def test_core_function_exception(mock_asyncio_run, caplog):
    """Test CLI handles exceptions from core async functions gracefully."""
    mock_asyncio_run.side_effect = Exception("Core function exploded!")

    with patch.dict(cli.os.environ, {"GITHUB_USERNAME": "erroruser"}):
        exit_code = run_cli_main_with_exit_code(["duck"])

    assert exit_code == 3
    assert "An unexpected error occurred: Core function exploded!" in caplog.text
    # Ensure asyncio.run was called (which means parse_args and setup happened)
    mock_asyncio_run.assert_called_once()


@pytest.mark.parametrize("verbose_args", [
    ([]),
    (["-v"]),
    (["-vv"]),
    (["-vvv"])
])
def test_verbosity_settings(verbose_args, caplog):
    """Test different verbosity levels correctly configure logging."""
    # We just need to call the main function and check if setup_logging was called correctly.
    # The actual log output check is complex. Here we focus on setup_logging call.
    # For this test, we expect it to fail due to missing username, but after logging is set up.
    expected_log_level = "INFO"
    if "-v" in verbose_args: expected_log_level = "DEBUG"
    if "-vv" in verbose_args: expected_log_level = "DEBUG" # Assuming -vv is also DEBUG
    # if "-vvv" in verbose_args: expected_log_level = "TRACE" or similar if we had it

    with patch.dict(cli.os.environ, {}, clear=True), \
         patch("duck.cli.setup_logging") as mock_setup_logging, \
         patch("duck.cli.handle_check", side_effect=SystemExit(2)): # Mock to prevent actual run
        run_cli_main_with_exit_code(["duck"] + verbose_args)
        mock_setup_logging.assert_called_once()
        # Check the log level argument passed to setup_logging
        # The actual argparse Namespace object is passed, so we check its 'verbose' attribute
        args_namespace = mock_setup_logging.call_args[0][0]
        if not verbose_args: # No -v flags
            assert args_namespace.verbose == 0
        elif verbose_args == ["-v"]:
            assert args_namespace.verbose == 1
        elif verbose_args == ["-vv"]:
            assert args_namespace.verbose == 2
        elif verbose_args == ["-vvv"]:
            assert args_namespace.verbose == 3
