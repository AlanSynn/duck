"""Tests for scripts in the scripts/ directory."""

import datetime
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add scripts directory to sys.path to allow direct import of generate_email
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.append(str(SCRIPTS_DIR))

# Check if generate_email is available for import, otherwise mock it
# This is to prevent ImportError if generate_email.py is not found during testing in some environments
# However, for these tests, we usually want the actual script to be present.
try:
    from generate_email import generate_email_html  # type: ignore
    from generate_email import main as generate_email_main
except ImportError:
    generate_email_html = MagicMock()  # type: ignore
    generate_email_main = MagicMock()  # type: ignore


CHECK_AND_NOTIFY_SCRIPT = SCRIPTS_DIR / "check_and_notify.sh"


@pytest.fixture
def sample_template_content() -> str:
    """Return a sample HTML template content with placeholders."""
    return """<html>
<body>
    <h1>Hello {{username}}!</h1>
    <p>Today is {{date}}.</p>
    <footer>Copyright {{year}}</footer>
</body>
</html>"""


@pytest.fixture
def mock_template_file(tmp_path: Path, sample_template_content: str) -> Path:
    """Create a temporary mock HTML template file."""
    template_file = tmp_path / "mock_template.html"
    template_file.write_text(sample_template_content)
    return template_file


# --- Tests for generate_email.py ---


def test_generate_email_html_success(tmp_path: Path, mock_template_file: Path):
    """Test successful generation of HTML email content."""
    username = "testuser"
    output_html_path = tmp_path / "output" / "email.html"

    generate_email_html(username, str(mock_template_file), str(output_html_path))

    assert output_html_path.exists()
    content = output_html_path.read_text()

    now = datetime.datetime.now()
    expected_date = now.strftime("%Y-%m-%d")
    expected_year = now.strftime("%Y")

    assert f"<h1>Hello {username}!</h1>" in content
    assert f"<p>Today is {expected_date}.</p>" in content
    assert f"<footer>Copyright {expected_year}</footer>" in content


def test_generate_email_html_template_not_found(tmp_path: Path):
    """Test generate_email_html when the template file is not found."""
    username = "testuser"
    non_existent_template = tmp_path / "non_existent_template.html"
    output_html_path = tmp_path / "output" / "email.html"

    with pytest.raises(SystemExit) as excinfo:
        generate_email_html(username, str(non_existent_template), str(output_html_path))
    assert excinfo.value.code == 1
    assert not output_html_path.exists()


@patch(f"{generate_email_html.__module__ if hasattr(generate_email_html, '__module__') else 'generate_email'}.open", new_callable=mock_open)
@patch("os.makedirs")
def test_generate_email_html_cannot_write_output(mock_makedirs: MagicMock, mock_file_open: MagicMock, mock_template_file: Path):
    """Test generate_email_html when the output file cannot be written."""
    username = "testuser"
    unwritable_output_path = "/unwritable/path/email.html"

    # Mock reading the template successfully
    with open(str(mock_template_file), "r") as f:
        template_content_for_mock = f.read()

    # Configure the mock for open specifically for template reading and failing for writing
    def open_side_effect(path, mode="r", *args, **kwargs):
        if path == str(mock_template_file) and mode == "r":
            # Return a mock that has a read method
            m = mock_open(read_data=template_content_for_mock)()
            return m
        elif path == unwritable_output_path and mode == "w":
            raise IOError("Cannot write to output")
        else:
            # Fallback for any other open calls, though not expected in this specific test path
            return mock_open(read_data=template_content_for_mock)()  # Or raise an error if unexpected

    mock_file_open.side_effect = open_side_effect

    with pytest.raises(SystemExit) as excinfo:
        generate_email_html(username, str(mock_template_file), unwritable_output_path)
    assert excinfo.value.code == 1
    mock_makedirs.assert_called_once_with(os.path.dirname(unwritable_output_path), exist_ok=True)


@patch.object(sys, "argv", ["generate_email.py", "--username", "test_cli_user"])
@patch(
    f"{generate_email_main.__module__ if hasattr(generate_email_main, '__module__') else 'generate_email'}.generate_email_html"
)  # Patching the function called by main
def test_generate_email_main_default_paths(mock_generate_email_html: MagicMock):
    """Test the main function with default template and output paths."""
    generate_email_main()
    args_called, _ = mock_generate_email_html.call_args
    assert args_called[0] == "test_cli_user"  # username

    expected_template_path = SCRIPTS_DIR.parent / "templates" / "commit-reminder.html"
    expected_output_path = SCRIPTS_DIR.parent / "tmp" / "commit-reminder-output.html"

    assert Path(args_called[1]).resolve() == expected_template_path.resolve()
    assert Path(args_called[2]).resolve() == expected_output_path.resolve()


@patch.object(sys, "argv", ["generate_email.py", "--username", "custom_user", "--template", "custom_template.html", "--output", "custom_output.html"])
@patch(f"{generate_email_main.__module__ if hasattr(generate_email_main, '__module__') else 'generate_email'}.generate_email_html")
def test_generate_email_main_custom_paths(mock_generate_email_html: MagicMock):
    """Test the main function with custom template and output paths provided as arguments."""
    generate_email_main()
    args_called, _ = mock_generate_email_html.call_args
    assert args_called[0] == "custom_user"
    assert args_called[1] == "custom_template.html"
    assert args_called[2] == "custom_output.html"


@patch.object(sys, "argv", ["generate_email.py"])  # Missing --username
def test_generate_email_main_missing_username():
    """Test main function exits when --username is not provided."""
    with pytest.raises(SystemExit) as excinfo:
        generate_email_main()
    assert excinfo.value.code != 0  # argparse exits with 2 for errors


# --- Tests for check_and_notify.sh ---


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Set up mock environment variables for check_and_notify.sh tests."""
    monkeypatch.setenv("GITHUB_USERNAME", "test_user")
    monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
    monkeypatch.setenv("SMTP_USER", "smtp_user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp_password")
    # Create a dummy generate_email.py in a temporary scripts dir to be found by the shell script
    # This is because the shell script calls `python $SCRIPT_DIR/generate_email.py`
    # The SCRIPT_DIR is derived from the shell script's path.
    # We need to make sure it can find our test-controlled generate_email.py
    # However, a simpler approach is to mock the python call itself within the subprocess.run mock

    # For the shell script to find generate_email.py relative to itself, we need to ensure that the
    # SCRIPT_DIR it calculates points to a place where our (potentially mocked) generate_email.py exists.
    # This is tricky with shell script testing. The most robust way is to mock the subprocess calls.
    return tmp_path


@patch("subprocess.run")
def test_check_and_notify_commits_found(mock_subprocess_run: MagicMock, mock_env_vars: Path):
    """Test check_and_notify.sh when commits are found (github-check-commits exits 0)."""
    # Mock github-check-commits to return 0 (success)
    mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    # Run the shell script
    result = subprocess.run([str(CHECK_AND_NOTIFY_SCRIPT)], capture_output=True, text=True, check=False, env=os.environ.copy())

    assert result.returncode == 0
    assert "Checking for GitHub commits" in result.stdout
    # Ensure python generate_email.py and mailx were NOT called
    # This requires inspecting mock_subprocess_run.call_args_list
    generate_email_call_found = False
    mailx_call_found = False
    for call in mock_subprocess_run.call_args_list:
        if "generate_email.py" in " ".join(call.args[0]):
            generate_email_call_found = True
        if "mailx" in " ".join(call.args[0]):
            mailx_call_found = True

    assert not generate_email_call_found
    assert not mailx_call_found
    # First call should be to github-check-commits
    mock_subprocess_run.assert_any_call(["github-check-commits"], capture_output=True, text=True, check=False, env=os.environ.copy())


@patch("subprocess.run")
@patch("os.path.exists", return_value=True)  # Mock os.path.exists for `command -v mailx`
@patch("shutil.which", return_value="/usr/bin/mailx")  # Mock `command -v mailx` check
def test_check_and_notify_no_commits_email_sent(mock_shutil_which: MagicMock, mock_os_path_exists: MagicMock, mock_subprocess_run: MagicMock, mock_env_vars: Path):
    """Test check_and_notify.sh when no commits are found and email is sent."""

    # Mock github-check-commits to return 1 (failure)
    # Mock python generate_email.py to return 0 (success)
    # Mock mailx to return 0 (success)
    def side_effect_run(*args, **kwargs):
        cmd = args[0]
        if "github-check-commits" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="No commits.", stderr="")
        elif "generate_email.py" in " ".join(cmd):
            # Create the dummy output file that mailx might look for (or that generate_email.py creates)
            tmp_output_dir = mock_env_vars / "tmp"
            tmp_output_dir.mkdir(exist_ok=True)
            (tmp_output_dir / "commit-reminder-output.html").touch()
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Generated email.", stderr="")
        elif "mailx" in " ".join(cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Email sent.", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=127, stdout="", stderr="Command not found")  # Default for unexpected calls

    mock_subprocess_run.side_effect = side_effect_run

    # Prepare environment for the script (it uses SCRIPT_DIR, REPO_ROOT derived from its own path)
    # We need to ensure generate_email.py is found by the shell script.
    # Create a dummy generate_email.py in the SCRIPT_DIR that the shell script will calculate.
    # This is complex. A more direct way is to adjust PATH or ensure the test structure mirrors it.
    # For now, the mock of subprocess.run for the python call bypasses this.

    result = subprocess.run([str(CHECK_AND_NOTIFY_SCRIPT)], capture_output=True, text=True, check=False, env=os.environ.copy())

    assert result.returncode == 1  # Should return original failure code from github-check-commits
    assert "No commits found or error occurred. Sending notification..." in result.stdout
    assert "Email notification sent!" in result.stdout

    # Check that all commands were called
    cmds_called = [" ".join(call.args[0]) for call in mock_subprocess_run.call_args_list]
    assert any("github-check-commits" in cmd for cmd in cmds_called)
    assert any("generate_email.py" in cmd for cmd in cmds_called)
    assert any("mailx -s" in cmd for cmd in cmds_called)


@patch("subprocess.run")
@patch("shutil.which", return_value=None)  # Mock `command -v mailx` to simulate mailx not found
def test_check_and_notify_no_commits_mailx_not_found(mock_shutil_which: MagicMock, mock_subprocess_run: MagicMock, mock_env_vars: Path):
    """Test check_and_notify.sh when no commits and mailx is not found."""

    def side_effect_run(*args, **kwargs):
        cmd = args[0]
        if "github-check-commits" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="No commits.", stderr="")
        elif "generate_email.py" in " ".join(cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Generated email.", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=127, stdout="", stderr="Command not found")

    mock_subprocess_run.side_effect = side_effect_run

    result = subprocess.run([str(CHECK_AND_NOTIFY_SCRIPT)], capture_output=True, text=True, check=False, env=os.environ.copy())

    assert result.returncode == 1
    assert "Warning: mailx command not found." in result.stdout
    cmds_called = [" ".join(call.args[0]) for call in mock_subprocess_run.call_args_list]
    assert not any("mailx -s" in cmd for cmd in cmds_called)


def test_check_and_notify_missing_github_username(tmp_path: Path):
    """Test check_and_notify.sh when GITHUB_USERNAME is not set."""
    env = os.environ.copy()
    if "GITHUB_USERNAME" in env:  # Ensure it's not set
        del env["GITHUB_USERNAME"]

    result = subprocess.run([str(CHECK_AND_NOTIFY_SCRIPT)], capture_output=True, text=True, check=False, env=env)
    assert result.returncode == 1
    assert "Error: GITHUB_USERNAME environment variable is required" in result.stdout


@patch("subprocess.run")
def test_check_and_notify_email_vars_missing(mock_subprocess_run: MagicMock, mock_env_vars: Path, monkeypatch: pytest.MonkeyPatch):
    """Test check_and_notify.sh when no commits but email env vars are missing."""

    # Mock github-check-commits to return 1 (failure)
    # Mock python generate_email.py to return 0 (success)
    def side_effect_run(*args, **kwargs):
        cmd = args[0]
        if "github-check-commits" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="No commits.", stderr="")
        elif "generate_email.py" in " ".join(cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Generated email.", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=127, stdout="", stderr="Command not found")

    mock_subprocess_run.side_effect = side_effect_run

    # Unset one of the required email env vars
    current_env = os.environ.copy()
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    # Need to mock shutil.which for command -v mailx to pass
    with patch("shutil.which", return_value="/usr/bin/mailx"):
        result = subprocess.run([str(CHECK_AND_NOTIFY_SCRIPT)], capture_output=True, text=True, check=False, env=current_env)

    assert result.returncode == 1
    assert "Warning: SMTP_USER and SMTP_PASSWORD required for email notifications" in result.stdout
    cmds_called = [" ".join(call.args[0]) for call in mock_subprocess_run.call_args_list]
    assert not any("mailx -s" in cmd for cmd in cmds_called)
