#!/bin/bash
# Script to check for GitHub activity (commits or PRs) and send an email notification if none are found
# Requires the environment variables:
# - USERNAME
# - GITHUB_TOKEN (optional, for fetching private activity if applicable by duck)
# - EMAIL_RECIPIENT
# - SMTP_USER (for email)
# - SMTP_PASSWORD (for email)

set -e # Re-enable set -e
# set -x # Removed for normal operation

# Determine script directory robustly
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT=$(dirname "$SCRIPT_DIR")

# Create tmp directory if it doesn't exist
mkdir -p "$REPO_ROOT/tmp"

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
  echo "Warning: EMAIL_RECIPIENT not set. Email notifications will not be sent."
fi

# Construct duck command arguments
DUCK_ARGS="--user $USERNAME --days 3"
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
  EMAIL_SUBJECT_DEFAULT="DUCK: No GitHub Activity in 3 Days!"
  ACTIVITY_MESSAGE_DEFAULT="It looks like you haven't had any GitHub activity (commits or PRs) in the last 3 days. Don't be a DUCK! Time to make some contributions."

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

  OUTPUT_PATH="$REPO_ROOT/tmp/activity-reminder-output.html"

  # Execute generate_email.py directly without eval
  echo "Executing Python email script..."
  # Mask password for logging
  LOG_CMD="python3 \"$SCRIPT_DIR/generate_email.py\" --send --username \"$USERNAME\" --message \"$ACTIVITY_MESSAGE_DEFAULT\" --recipient \"$EMAIL_RECIPIENT\" --sender \"${SMTP_SENDER:-$SMTP_SENDER_DEFAULT}\" --subject \"${EMAIL_SUBJECT:-$EMAIL_SUBJECT_DEFAULT}\" --smtp-host \"$SMTP_HOST_TO_USE\" --smtp-port \"$SMTP_PORT_TO_USE\" $SMTP_USER_ARG --smtp-password ****** $SSL_FLAG $STARTTLS_FLAG --output \"$OUTPUT_PATH\""
  echo "$LOG_CMD"

  # Use the GitHub Actions environment variable to signal success
  python3 "$SCRIPT_DIR/generate_email.py" \
    --send \
    --username "$USERNAME" \
    --message "$ACTIVITY_MESSAGE_DEFAULT" \
    --recipient "$EMAIL_RECIPIENT" \
    --sender "${SMTP_SENDER:-$SMTP_SENDER_DEFAULT}" \
    --subject "${EMAIL_SUBJECT:-$EMAIL_SUBJECT_DEFAULT}" \
    --smtp-host "$SMTP_HOST_TO_USE" \
    --smtp-port "$SMTP_PORT_TO_USE" \
    ${SMTP_USER_ARG} \
    ${SMTP_PASSWORD_ARG} \
    ${SSL_FLAG} \
    ${STARTTLS_FLAG} \
    --output "$OUTPUT_PATH"

  # If we reach here, the email was sent successfully
  if [ "${GITHUB_ENV:-}" != "" ]; then
    echo "EMAIL_SENT=true" >> $GITHUB_ENV
  fi

elif [ $CHECK_RESULT -eq 0 ]; then
  echo "Activity found for $USERNAME. No notification needed."
else # Should not happen if duck exits 0 or 1, but as a safeguard
  echo "DUCK command resulted in an unexpected exit code: $CHECK_RESULT."
fi

# Return the original exit code from the duck check
exit $CHECK_RESULT
