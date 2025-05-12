#!/usr/bin/env python3
"""DUCK Email Notification Generator.

Generates and optionally sends HTML email notifications when no GitHub activity is detected.
"""

import argparse
import logging
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate and send activity reminder email")

    # Email content options
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument("--message", required=True, help="Notification message")
    parser.add_argument("--recipient", help="Email recipient")
    parser.add_argument("--sender", help="Email sender address")
    parser.add_argument("--subject", default="DUCK: No GitHub Activity Today!", help="Email subject")

    # SMTP settings
    parser.add_argument("--smtp-host", default="smtp.gmail.com", help="SMTP server host")
    parser.add_argument("--smtp-port", default="587", help="SMTP server port")
    parser.add_argument("--smtp-user", help="SMTP username")
    parser.add_argument("--smtp-password", help="SMTP password")
    parser.add_argument("--smtp-use-ssl", action="store_true", help="Use SSL for SMTP connection")
    parser.add_argument("--smtp-use-starttls", action="store_true", help="Use STARTTLS for SMTP connection")

    # Output options
    parser.add_argument("--output", help="Output HTML file path")
    parser.add_argument("--send", action="store_true", help="Send email directly")

    return parser.parse_args()


def generate_html_email(username: str, message: str) -> str:
    """Generate HTML email content.

    Args:
        username: GitHub username
        message: Notification message

    Returns:
        HTML content as string
    """
    current_date = datetime.now().strftime("%Y-%m-%d")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DUCK: Activity Reminder</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .container {{
                background-color: #ffffff;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 20px;
            }}
            .logo {{
                font-size: 2.5em;
                font-weight: bold;
                color: #e74c3c;
                margin-bottom: 10px;
            }}
            h1 {{
                color: #2c3e50;
                margin-top: 0;
            }}
            .date {{
                color: #7f8c8d;
                font-style: italic;
                margin-bottom: 25px;
                text-align: center;
            }}
            .content {{
                margin-bottom: 30px;
            }}
            .message {{
                font-size: 1.1em;
                background-color: #f8f9fa;
                padding: 15px;
                border-left: 4px solid #e74c3c;
                margin-bottom: 20px;
            }}
            .cta {{
                text-align: center;
                margin: 30px 0;
            }}
            .button {{
                display: inline-block;
                background-color: #e74c3c;
                color: white;
                padding: 12px 25px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
                font-size: 0.9em;
            }}
            .footer {{
                text-align: center;
                font-size: 0.8em;
                color: #95a5a6;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ecf0f1;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">DUCK</div>
                <h1>GitHub Activity Reminder</h1>
            </div>
            <div class="date">
                {current_date}
            </div>
            <div class="content">
                <p>Hello @{username},</p>
                <div class="message">
                    {message}
                </div>
                <p>Maintaining a consistent GitHub contribution streak is important for:</p>
                <ul>
                    <li>Building your developer portfolio</li>
                    <li>Staying engaged with your projects</li>
                    <li>Demonstrating your coding consistency</li>
                    <li>Learning and growing your skills daily</li>
                </ul>
            </div>
            <div class="cta">
                <a href="https://github.com/{username}" class="button">View My GitHub Profile</a>
            </div>
            <div class="footer">
                <p>This is an automated message from DUCK (Daily User Commit Keeper).</p>
                <p>© {datetime.now().year} DUCK - Stay Committed</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_email(recipient: str, sender: str, subject: str, html_content: str, smtp_config: Dict[str, Any]) -> bool:
    """Send HTML email via SMTP.

    Args:
        recipient: Email recipient address
        sender: Email sender address
        subject: Email subject
        html_content: HTML email content
        smtp_config: Dictionary with SMTP configuration

    Returns:
        Success status as boolean
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        if smtp_config.get("use_ssl", False):
            server = smtplib.SMTP_SSL(smtp_config["host"], int(smtp_config["port"]))
        else:
            server = smtplib.SMTP(smtp_config["host"], int(smtp_config["port"]))

        if smtp_config.get("use_starttls", False):
            server.starttls()

        if smtp_config.get("user") and smtp_config.get("password"):
            server.login(smtp_config["user"], smtp_config["password"])

        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        logger.info(f"Successfully sent email to {recipient}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e!s}")
        return False


def main():
    """Main function to generate and optionally send the email."""
    args = parse_args()

    # Generate HTML email content
    html_content = generate_html_email(args.username, args.message)

    # Save to file if output path provided
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(html_content)
        logger.info(f"HTML email content saved to {args.output}")

    # Send email if requested
    if args.send and args.recipient:
        smtp_config = {
            "host": args.smtp_host,
            "port": args.smtp_port,
            "use_ssl": args.smtp_use_ssl,
            "use_starttls": args.smtp_use_starttls,
            "user": args.smtp_user,
            "password": args.smtp_password,
        }

        success = send_email(
            recipient=args.recipient,
            sender=args.sender or args.smtp_user or "DUCK@noreply.com",
            subject=args.subject,
            html_content=html_content,
            smtp_config=smtp_config,
        )

        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
