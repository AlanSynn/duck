# (D)id (U) (C)ommit mr.(K)im?

<p align="center">
  <img src="assets/img/lazy_duck.png" alt="Lazy Duck Logo" height="200">
</p>

DUCK is a simple Python tool designed to help you maintain your GitHub activity streak. It checks daily for public commits and pull requests associated with your GitHub username. If no activity is found for the current day (UTC), it can send you a reminder email.

## Features

*   Checks for public commits made by the user on the current day.
*   Checks for public pull requests involving the user (created, commented on, merged, etc.) that were active on the current day.
*   Sends a beautifully formatted HTML email notification if no activity is detected.
*   Configurable via environment variables or TOML configuration file.
*   Includes a GitHub Actions workflow for automated daily checks.

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/AlanSynn/workbot.git # Replace with your repo URL if different
    cd workbot
    ```

2.  **Set up a Python Virtual Environment:**
    It's recommended to use a virtual environment.
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies:**
    This project uses `uv` for fast package management.
    ```bash
    # Install uv if you haven't already (example for Linux/macOS)
    # curl -LsSf https://astral.sh/uv/install.sh | sh
    # source $HOME/.cargo/env # Or add uv to your PATH manually

    uv pip install --system .
    ```
    This command installs the `duck` tool and its dependencies into your environment.

4.  **Create and Configure `.env` File (for Local Use):**
    For running the notification script locally (e.g., via `scripts/check_and_notify.sh`), create a `.env` file in the root of the project:
    ```bash
    touch .env
    ```
    Add the following content to your `.env` file, replacing placeholder values with your actual details:

    ```env
    # GitHub Configuration
    USERNAME="YourGitHubUsername"
    # GITHUB_TOKEN="your_github_personal_access_token" # Optional: For checking private activity if DUCK supports it and if needed.

    # Email Recipient
    EMAIL_RECIPIENT="youremail@example.com"

    # SMTP Configuration for Email Notifications (using Gmail as an example)
    SMTP_HOST="smtp.gmail.com"
    SMTP_PORT="587" # 587 for STARTTLS, 465 for SSL
    SMTP_USER="your_sending_email@gmail.com"
    # IMPORTANT for Gmail: If using 2-Step Verification, generate an App Password for SMTP_PASSWORD.
    # Do not use your regular Google account password here.
    SMTP_PASSWORD="your_gmail_app_password_or_smtp_password"

    # Specify ONE of the following as true, the other as false or omit it:
    SMTP_USE_STARTTLS="true" # For port 587 with Gmail
    SMTP_USE_SSL="false"    # For port 465 with Gmail

    # Optional: Override default sender email and subject
    # SMTP_SENDER="Custom Sender Name <your_sending_email@gmail.com>"
    # EMAIL_SUBJECT="Custom Subject for DUCK Reminder"
    ```
    **Note:** Add `.env` to your `.gitignore` file to avoid committing sensitive credentials.

## Usage

### Manual Check and Notification (Local)

The `scripts/check_and_notify.sh` script automates the process of checking for activity using `duck` and then sending an email if no activity is found. It loads its configuration from the `.env` file.

```bash
# Ensure your .env file is configured
./scripts/check_and_notify.sh
```

### Direct CLI Usage

You can also use the `duck` CLI tool directly to check for activity. This is useful for quick checks without sending notifications.

```bash
# Check activity for a user (token is optional)
duck --user YourGitHubUsername
# duck --user YourGitHubUsername --token your_github_personal_access_token
```
The `duck` command will exit with code `0` if activity is found, and `1` if no activity is found for the current day (UTC).

## Automated Daily Checks (GitHub Actions)

This repository includes a GitHub Actions workflow defined in `.github/workflows/commit-check.yml`. This workflow runs daily at a scheduled time (configurable in the cron expression within the file).

**Workflow Steps:**
1.  Checks out the repository.
2.  Sets up Python and installs dependencies.
3.  Runs the `duck` command to check for activity.
4.  If no activity is found, sends a notification email using the built-in email generator.

### Email Notifications

DUCK includes a robust email notification system that sends beautifully styled HTML emails when no commits are detected. The email system:

- Generates modern, responsive HTML emails with clear calls to action
- Works with most SMTP providers, including Gmail
- Can be used both in GitHub Actions and for local notifications
- Includes tests to ensure reliable operation

The email content is generated dynamically using the `scripts/generate_email.py` script, which can be used directly if needed:

```bash
python scripts/generate_email.py --username "YourUsername" --message "Your message" --output "output.html"
```

For sending emails, you can use the `--send` flag along with SMTP configuration parameters:

```bash
python scripts/generate_email.py --send --username "YourUsername" --message "Your message" \
  --recipient "recipient@example.com" --sender "sender@example.com" \
  --smtp-host "smtp.example.com" --smtp-port "587" --smtp-use-starttls \
  --smtp-user "yourusername" --smtp-password "yourpassword"
```

**Configuration for GitHub Actions:**
The GitHub Actions workflow requires several secrets to be configured in your repository settings. Follow these steps to add them:

1.  Navigate to your GitHub repository.
2.  Click on the **Settings** tab (usually located near the top of the repository page).
3.  In the left sidebar, scroll down and click on **Secrets and variables**.
4.  From the dropdown, select **Actions**.
5.  You will see a section for "Repository secrets". Click the **New repository secret** button for each secret you need to add.

The following secrets are required:

*   `USERNAME`: Your GitHub username.
*   `EMAIL_RECIPIENT`: The email address to send notifications to.
*   `SMTP_USER`: Your SMTP username (e.g., your Gmail address).
*   `SMTP_PASSWORD`: Your SMTP password (e.g., your Gmail App Password).
*   `GITHUB_TOKEN`: (Optional but recommended for Actions) A GitHub Personal Access Token.
    *   **Permissions needed**: `public_repo` (to access public repository data) and `read:user` (to read user profile data).
    *   **Why it's recommended**: Ensures reliable API access, especially for accounts with a lot of activity or to access event details that might require it. The default `GITHUB_TOKEN` provided by Actions might have limitations for `/users/.../events` for some users/cases.
    *   To create a Personal Access Token (PAT):
        1.  Go to your GitHub **Settings** (click your profile picture in the top-right corner).
        2.  In the left sidebar, scroll down to **Developer settings**.
        3.  Click on **Personal access tokens**, then **Tokens (classic)**.
        4.  Click **Generate new token** (or **Generate new token (classic)**).
        5.  Give your token a descriptive name, select the expiration, and check the `public_repo` and `read:user` scopes.
        6.  Click **Generate token** and copy the token value immediately. You won't be able to see it again.

## Configuration Options

DUCK supports multiple configuration methods:

1. **Environment Variables**: Set variables directly or through a `.env` file
2. **TOML Configuration**: Create a `config.toml` file in the project root with the following structure:

```toml
[github]
username = "YourGitHubUsername"
token = "optional_github_token"

[email]
recipient = "youremail@example.com"
subject = "DUCK: No GitHub Activity Today!"

[smtp]
host = "smtp.gmail.com"
port = 587
user = "your_sending_email@gmail.com"
password = "your_app_password"
use_starttls = true
use_ssl = false
```

Environment variables always take precedence over TOML settings.

## How Email Notifications Work

When no GitHub activity is detected:
1. The `check_and_notify.sh` script detects the absence of activity
2. It calls the `generate_email.py` script which:
   - Creates a responsive HTML email template
   - Sends the email via SMTP if sending is enabled
   - Saves the generated HTML to a file for backup purposes
3. If the built-in sender fails, a backup plain-text email is sent via GitHub Actions

---

Keep your streak alive with DUCK!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
