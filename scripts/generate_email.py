#!/usr/bin/env python3
"""Generate HTML email content for GitHub activity reminders and optionally send it.

This script takes the HTML template, replaces placeholders with actual values,
and can send the resulting HTML email using SMTP.
"""

import argparse
import datetime
import logging
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def send_email(
    subject: str,
    html_body: str,
    sender_email: str,
    recipient_email: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str | None,
    smtp_password: str | None,
    use_ssl: bool,
    use_starttls: bool,
) -> bool:
    """Send an email using SMTP.

    Args:
        subject: Email subject.
        html_body: HTML content of the email.
        sender_email: Email address of the sender.
        recipient_email: Email address of the recipient.
        smtp_host: SMTP server hostname or IP address.
        smtp_port: SMTP server port.
        smtp_user: Username for SMTP authentication (optional).
        smtp_password: Password for SMTP authentication (optional).
        use_ssl: Whether to use SSL from the beginning of the connection.
        use_starttls: Whether to upgrade the connection to TLS using STARTTLS.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    # Attach HTML part
    part = MIMEText(html_body, "html")
    msg.attach(part)

    try:
        logger.info(f"Attempting to send email to {recipient_email} via {smtp_host}:{smtp_port}")
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)

        if use_starttls:
            server.starttls()

        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        logger.info("Email sent successfully.")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication Error: {e}. Check credentials for {smtp_user}.")
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"SMTP Server Disconnected: {e}. Check server address and port.")
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP Connect Error: {e}. Could not connect to {smtp_host}:{smtp_port}.")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending email: {e}")
    return False


def generate_email_html(username: str, activity_message: str, template_path: str, output_path: str | None) -> str | None:
    """Generate the HTML email content.

    Args:
        username: The GitHub username to insert into the template.
        activity_message: The message describing the activity status (or lack thereof).
        template_path: Path to the HTML template file.
        output_path: Path where the generated HTML should be saved (optional).

    Returns:
        Generated HTML content or None if output_path is None (just for content).
    """
    # Read the template
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        logger.error(f"Template file not found at {template_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading template file: {e}")
        return None

    # Get current date and year
    now = datetime.datetime.now(datetime.timezone.utc)  # Use timezone-aware datetime
    date_str = now.strftime("%Y-%m-%d")
    year = now.strftime("%Y")

    # Replace placeholders
    html = template.replace("{{username}}", username)
    html = html.replace("{{date}}", date_str)
    html = html.replace("{{year}}", year)
    html = html.replace("{{ACTIVITY_MESSAGE}}", activity_message)

    # Write the output if output_path is provided
    if output_path:
        output_path_obj = Path(output_path)
        os.makedirs(output_path_obj.parent, exist_ok=True)
        try:
            with open(output_path_obj, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"Successfully generated email content and saved to {output_path_obj}")
        except Exception as e:
            logger.error(f"Error writing output file to {output_path_obj}: {e}")
            return None  # Return None on failure to write file
    else:
        logger.info("Successfully generated email content in memory.")

    return html  # Return the generated HTML content


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Generate GitHub activity reminder email")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument("--message", required=True, help="The main activity status message to include in the email (will replace {{ACTIVITY_MESSAGE}}).")
    parser.add_argument("--template", default=None, help="Path to HTML template")
    parser.add_argument("--output", default=None, help="Path for output HTML file (optional, if not sending directly)")

    # Arguments for sending email
    parser.add_argument("--send", action="store_true", help="Send the email after generating it.")
    parser.add_argument("--recipient", help="Recipient email address (required if --send).")
    parser.add_argument("--sender", help="Sender email address (required if --send).")
    parser.add_argument("--subject", help="Email subject (required if --send).")
    parser.add_argument("--smtp-host", help="SMTP server host (required if --send).")
    parser.add_argument("--smtp-port", type=int, help="SMTP server port (required if --send).")
    parser.add_argument("--smtp-user", help="SMTP username (optional).")
    parser.add_argument("--smtp-password", help="SMTP password (optional, use environment variables for security).")
    parser.add_argument("--smtp-use-ssl", action="store_true", help="Use SSL for SMTP connection (e.g., port 465).")
    parser.add_argument("--smtp-use-starttls", action="store_true", help="Use STARTTLS for SMTP connection (e.g., port 587).")

    args = parser.parse_args()

    if args.send:
        required_send_args = [args.recipient, args.sender, args.subject, args.smtp_host, args.smtp_port]
        if not all(required_send_args):
            parser.error("If --send is used, --recipient, --sender, --subject, --smtp-host, and --smtp-port are required.")
        if not (args.smtp_use_ssl or args.smtp_use_starttls):
            parser.error("If --send is used, either --smtp-use-ssl or --smtp-use-starttls must be specified.")
        if args.smtp_use_ssl and args.smtp_use_starttls:
            parser.error("Cannot use both --smtp-use-ssl and --smtp-use-starttls.")

    # Default paths if not specified
    template_file_path = Path(args.template) if args.template else Path(__file__).parent.parent / "templates" / "commit-reminder.html"
    output_file_path = Path(args.output) if args.output else Path(__file__).parent.parent / "tmp" / "activity-reminder-output.html"

    # If sending, output_path for generate_email_html can be optional if we don't want to force saving a file
    # However, the shell script currently passes it, so we keep it. For direct Python calls, it could be None.
    html_content_for_sending = generate_email_html(
        args.username,
        args.message,
        str(template_file_path),
        str(output_file_path) if args.output else None,  # Pass output_path only if specified
    )

    if html_content_for_sending and args.send:
        logger.info(f"Proceeding to send email to {args.recipient}")
        success = send_email(
            subject=args.subject,
            html_body=html_content_for_sending,  # Use the returned HTML content
            sender_email=args.sender,
            recipient_email=args.recipient,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            smtp_user=args.smtp_user,
            smtp_password=args.smtp_password,
            use_ssl=args.smtp_use_ssl,
            use_starttls=args.smtp_use_starttls,
        )
        if not success:
            logger.error("Email sending failed. The HTML content was saved to a file if --output was provided.")
    elif not html_content_for_sending:
        logger.error("HTML content generation failed or was not returned. Cannot send email.")
        sys.exit(1)
    elif args.send is False:
        logger.info(f"--send flag not provided. Email not sent. HTML content {'saved to ' + str(output_file_path) if args.output else 'generated but not saved.'}")
    else:  # Should not be reached if logic is correct
        logger.info(f"Email not sent. HTML content available {'at ' + str(output_file_path) if args.output else '(not saved)'}. Send flag: {args.send}")


if __name__ == "__main__":
    main()
