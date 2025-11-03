# GitHub Token Setup Guide

This guide explains how to securely configure your GitHub Personal Access Token (PAT) to enable DUCK to check commits in private repositories.

## Is it Safe to Use a GitHub Token?

**Yes, it is safe when done correctly.** Here's why:

1. **Tokens are designed for this purpose** - GitHub Personal Access Tokens are the recommended way to authenticate applications
2. **You control the permissions** - You can limit what the token can access
3. **They can be revoked** - If compromised, you can delete the token instantly
4. **Better than passwords** - Tokens are more secure than using your GitHub password

## Security Best Practices

### ✅ DO:
- Store tokens in GitHub Secrets (for Actions) or environment variables (local)
- Use tokens with minimal required permissions (`repo` and `read:user`)
- Set expiration dates on your tokens
- Revoke tokens you no longer need
- Use different tokens for different applications

### ❌ DON'T:
- Commit tokens to your repository
- Share tokens with others
- Use tokens with excessive permissions
- Store tokens in plain text files in your repo

## Where to Add Your GitHub Token

### Option 1: For GitHub Actions (Recommended for automated checks)

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add a secret named `GITHUB_TOKEN` with your Personal Access Token value
5. The workflow in `.github/workflows/commit-check.yml` will automatically use it

**Note:** GitHub Actions already provides a `GITHUB_TOKEN` by default, but it may not have access to all your private repos. Using a Personal Access Token with `repo` scope ensures full access to your private repositories.

### Option 2: For Local Usage (Development/Testing)

#### Using Environment Variables (Recommended)

1. Create or edit your `.env` file in the project root:
   ```bash
   # GitHub Configuration
   USERNAME="YourGitHubUsername"
   GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Your PAT here
   
   # Email Configuration
   EMAIL_RECIPIENT="youremail@example.com"
   # ... other settings
   ```

2. Ensure `.env` is in your `.gitignore`:
   ```bash
   echo ".env" >> .gitignore
   ```

3. Run DUCK:
   ```bash
   ./scripts/check_and_notify.sh
   ```

#### Using Command Line Arguments

You can also pass the token directly via CLI (not recommended for automation):
```bash
duck --user YourUsername --token ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## How to Create a GitHub Personal Access Token

1. Go to GitHub → **Settings** (your profile)
2. Scroll down to **Developer settings** (left sidebar)
3. Click **Personal access tokens** → **Tokens (classic)**
4. Click **Generate new token** → **Generate new token (classic)**
5. Configure your token:
   - **Note**: Give it a descriptive name (e.g., "DUCK - Private Repo Checker")
   - **Expiration**: Choose an appropriate expiration (90 days recommended)
   - **Select scopes**:
     - ✅ **repo** (Full control of private repositories)
     - ✅ **read:user** (Read user profile data)
6. Click **Generate token**
7. **IMPORTANT**: Copy the token immediately - you won't be able to see it again!

## Token Permissions Explained

### `repo` scope (Required)
Grants access to:
- Read commits in public and private repositories
- Read repository metadata
- This is the main permission needed for DUCK to check private repos

### `read:user` scope (Required)
Grants access to:
- Read user profile information
- Required for the GitHub Events API

## Troubleshooting

### "Still getting emails even with commits in private repos"

1. **Verify token is set correctly**:
   ```bash
   # For local testing
   duck --user YourUsername --token $GITHUB_TOKEN -v
   ```
   Look for log message: "Fetching all events (including private) for user: ..."

2. **Check token permissions**:
   - Go to GitHub → Settings → Developer settings → Personal access tokens
   - Click on your token and verify it has `repo` scope (not just `public_repo`)

3. **Verify token is not expired**:
   - Check the expiration date in your token settings

### "Test failed in GitHub Actions"

The test might be failing due to linting issues. Make sure to:
1. Run `ruff check .` locally before pushing
2. Run `ruff format .` to auto-format code
3. Ensure all tests pass with `pytest tests/`

## Example Configuration Files

### `.env` file (Local Development)
```env
# GitHub Configuration
USERNAME="YourGitHubUsername"
GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Email Configuration
EMAIL_RECIPIENT="youremail@example.com"

# SMTP Configuration
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="your_email@gmail.com"
SMTP_PASSWORD="your_app_password"
SMTP_USE_STARTTLS="true"
SMTP_USE_SSL="false"
```

### `config.toml` file (Alternative)
```toml
[github]
username = "YourGitHubUsername"
token = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Not recommended - use env vars instead

[email]
recipient = "youremail@example.com"
subject = "DUCK: No GitHub Activity Today!"

[smtp]
host = "smtp.gmail.com"
port = 587
user = "your_email@gmail.com"
password = "your_app_password"
use_starttls = true
use_ssl = false
```

**Important**: If using `config.toml`, add it to `.gitignore` to avoid committing your token!

## What Changed in This PR?

Previously, DUCK always used the `/users/{username}/events/public` API endpoint, which only returns public events even when authenticated. 

Now:
- **Without token**: Uses `/users/{username}/events/public` (public events only)
- **With token**: Uses `/users/{username}/events` (all events including private)

This means your private repository commits are now properly detected when you provide a GitHub token with `repo` scope.

## Summary

1. ✅ **It is safe** to use a GitHub token when stored securely
2. 📍 **Where to add it**:
   - GitHub Actions: Add as repository secret named `GITHUB_TOKEN`
   - Local: Add to `.env` file (ensure it's in `.gitignore`)
3. 🔑 **Token needs**: `repo` and `read:user` scopes
4. 🔒 **Security**: Never commit tokens, use GitHub Secrets or environment variables

For more information, see the [main README](../README.md).
