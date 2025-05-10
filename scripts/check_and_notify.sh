#!/bin/bash
# Script to check for GitHub activity (commits or PRs) and send an email notification if none are found
# Requires the environment variables:
# - USERNAME
# - GITHUB_TOKEN (optional, for fetching private activity if applicable by duck)
# - EMAIL_RECIPIENT
# - SMTP_USER (for mailx)
# - SMTP_PASSWORD (for mailx)

set -e # Re-enable set -e
# set -x # Removed for normal operation

# Determine script directory robustly
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT=$(dirname "$SCRIPT_DIR")

# Source .env file from REPO_ROOT if it exists
ENV_FILE="$REPO_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
  echo "Loading environment variables from $ENV_FILE"
  set -o allexport # Export all variables sourced from the .env file
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +o allexport
else
  echo "Info: .env file not found at $ENV_FILE. Relying on pre-set environment variables."
fi

# Check for required environment variables
if [ -z "$USERNAME" ]; then
  echo "Error: USERNAME environment variable is required"
  exit 1
fi

if [ -z "$EMAIL_RECIPIENT" ]; then
  echo "Warning: EMAIL_RECIPIENT not set. Local email notifications via mailx will not be sent."
fi

# Construct duck command arguments
DUCK_ARGS="--user $USERNAME"
if [ -n "$GITHUB_TOKEN" ]; then
  DUCK_ARGS="$DUCK_ARGS --token $GITHUB_TOKEN"
fi

# Run the activity check
echo "Checking for GitHub activity by $USERNAME using DUCK..."

# Capture the exit code but still run even if the check fails
# Ensure duck is in PATH or provide full path if necessary
if ! command -v duck &> /dev/null; then
    echo "Error: duck command not found. Please ensure it is installed and in your PATH."
    # Attempt to run from a common virtual environment location as a fallback for local dev
    if [ -f "$REPO_ROOT/.venv/bin/duck" ]; then
        echo "Attempting to run duck from $REPO_ROOT/.venv/bin/duck"
        DUCK_CMD="$REPO_ROOT/.venv/bin/duck"
    elif [ -f "$(pwd)/.venv/bin/duck" ]; then # If script is run from repo root
        echo "Attempting to run duck from $(pwd)/.venv/bin/duck"
        DUCK_CMD="$(pwd)/.venv/bin/duck"
    else
        exit 1
    fi
else
    DUCK_CMD="duck"
fi

# Run the duck command and capture its specific exit code
if $DUCK_CMD $DUCK_ARGS; then
  CHECK_RESULT=0
  echo "Debug: duck command succeeded (activity found)."
else
  CHECK_RESULT=$? # Capture the actual non-zero exit code from duck
  echo "Debug: duck command failed (no activity or error), exit code: $CHECK_RESULT"
fi

echo "Debug (immediately after DUCK_CMD and CHECK_RESULT): CHECK_RESULT is $CHECK_RESULT"
echo "Debug (immediately after DUCK_CMD and CHECK_RESULT): EMAIL_RECIPIENT is '$EMAIL_RECIPIENT'"

# If the check fails (no activity found or error), send a notification
if [ $CHECK_RESULT -ne 0 ] && [ -n "$EMAIL_RECIPIENT" ]; then
  echo "Debug: Entering email sending block."
  echo "No activity found or error occurred. Preparing and sending notification..."

  # Default SMTP settings (adjust if needed, or ensure they are in .env)
  SMTP_HOST_DEFAULT="smtp.gmail.com"
  SMTP_PORT_DEFAULT_SSL="465"
  SMTP_PORT_DEFAULT_TLS="587"
  # Choose SSL or STARTTLS. For Gmail:
  # - Port 465 uses SSL from the start.
  # - Port 587 uses STARTTLS.
  USE_SSL_DEFAULT=false # Set to true if your primary SMTP uses SSL on connection (e.g. port 465)
  USE_STARTTLS_DEFAULT=true # Set to true if your primary SMTP uses STARTTLS (e.g. port 587)

  SMTP_SENDER_DEFAULT="${SMTP_USER:-DUCKNotifier@example.com}" # Fallback if SMTP_USER not set
  EMAIL_SUBJECT_DEFAULT="DUCK: No GitHub Activity Today!"
  ACTIVITY_MESSAGE_DEFAULT="It looks like you haven't had any GitHub activity (commits or PRs) today. Don't be a DUCK! Time to make some contributions."

  # Use environment variables if set, otherwise use defaults
  SMTP_HOST_TO_USE="${SMTP_HOST:-$SMTP_HOST_DEFAULT}"
  SMTP_PORT_TO_USE="${SMTP_PORT}" # Will be determined by SSL/TLS choice if not set
  SMTP_USE_SSL_TO_USE="${SMTP_USE_SSL:-$USE_SSL_DEFAULT}"
  SMTP_USE_STARTTLS_TO_USE="${SMTP_USE_STARTTLS:-$USE_STARTTLS_DEFAULT}"

  if [ -z "$SMTP_PORT_TO_USE" ]; then
    if [ "$SMTP_USE_SSL_TO_USE" = true ]; then
      SMTP_PORT_TO_USE="$SMTP_PORT_DEFAULT_SSL"
    elif [ "$SMTP_USE_STARTTLS_TO_USE" = true ]; then
      SMTP_PORT_TO_USE="$SMTP_PORT_DEFAULT_TLS"
    else
      echo "Error: SMTP_PORT not set and could not be determined from SSL/TLS settings." >&2
      exit 1 # Or default to one, e.g., 587 for STARTTLS
    fi
  fi

  # The Python script needs explicit true/false for the flags
  SSL_FLAG=""
  if [ "$SMTP_USE_SSL_TO_USE" = true ]; then SSL_FLAG="--smtp-use-ssl"; fi
  STARTTLS_FLAG=""
  if [ "$SMTP_USE_STARTTLS_TO_USE" = true ]; then STARTTLS_FLAG="--smtp-use-starttls"; fi

  # Check if SMTP_USER and SMTP_PASSWORD are set for authentication
  SMTP_USER_ARG=""
  if [ -n "$SMTP_USER" ]; then SMTP_USER_ARG="--smtp-user $SMTP_USER"; fi
  SMTP_PASSWORD_ARG=""
  if [ -n "$SMTP_PASSWORD" ]; then SMTP_PASSWORD_ARG="--smtp-password $SMTP_PASSWORD"; fi

  PYTHON_CMD="python3 \"$SCRIPT_DIR/generate_email.py\""
  PYTHON_CMD="$PYTHON_CMD --send"
  PYTHON_CMD="$PYTHON_CMD --username \"$USERNAME\""
  PYTHON_CMD="$PYTHON_CMD --message \"$ACTIVITY_MESSAGE_DEFAULT\""
  PYTHON_CMD="$PYTHON_CMD --recipient \"$EMAIL_RECIPIENT\""
  PYTHON_CMD="$PYTHON_CMD --sender \"${SMTP_SENDER:-$SMTP_SENDER_DEFAULT}\""
  PYTHON_CMD="$PYTHON_CMD --subject \"${EMAIL_SUBJECT:-$EMAIL_SUBJECT_DEFAULT}\""
  PYTHON_CMD="$PYTHON_CMD --smtp-host \"$SMTP_HOST_TO_USE\""
  PYTHON_CMD="$PYTHON_CMD --smtp-port \"$SMTP_PORT_TO_USE\""
  if [ -n "$SMTP_USER_ARG" ]; then PYTHON_CMD="$PYTHON_CMD $SMTP_USER_ARG"; fi
  if [ -n "$SMTP_PASSWORD_ARG" ]; then PYTHON_CMD="$PYTHON_CMD $SMTP_PASSWORD_ARG"; fi # Be careful with logging passwords
  if [ -n "$SSL_FLAG" ]; then PYTHON_CMD="$PYTHON_CMD $SSL_FLAG"; fi
  if [ -n "$STARTTLS_FLAG" ]; then PYTHON_CMD="$PYTHON_CMD $STARTTLS_FLAG"; fi
  PYTHON_CMD="$PYTHON_CMD --output \"$REPO_ROOT/tmp/activity-reminder-output.html\""

  echo "Executing Python email script with command:"
  # Mask password if present for logging to console
  LOG_CMD=$(echo "$PYTHON_CMD" | sed -E 's/--smtp-password [^ ]+/--smtp-password ******/g')
  echo "$LOG_CMD"

  eval "$PYTHON_CMD"

  # No need for mailx block anymore

elif [ $CHECK_RESULT -eq 0 ]; then
  echo "Activity found for $USERNAME. No notification needed."
else # Should not happen if duck exits 0 or 1, but as a safeguard
  echo "DUCK command resulted in an unexpected exit code: $CHECK_RESULT."
fi

# Return the original exit code from the duck check
exit $CHECK_RESULT
