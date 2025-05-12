#!/usr/bin/env python3
"""
Tests for the generate_email.py script
"""

import os
import sys
import unittest
from pathlib import Path

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import the functions from generate_email.py
from generate_email import generate_html_email, send_email


class TestGenerateEmail(unittest.TestCase):
    """Test cases for email generation functionality."""

    def test_generate_html_email(self):
        """Test generation of HTML email content."""
        username = "test-user"
        message = "Test message for email generation"

        html_content = generate_html_email(username, message)

        # Verify basic content
        self.assertIn(username, html_content)
        self.assertIn(message, html_content)
        self.assertIn("<!DOCTYPE html>", html_content)
        self.assertIn("<div class=\"logo\">DUCK</div>", html_content)
        self.assertIn("GitHub Activity Reminder", html_content)

    def test_send_email_missing_credentials(self):
        """Test that email sending fails gracefully with missing credentials."""
        smtp_config = {
            "host": "smtp.example.com",
            "port": 587,
            "use_starttls": True,
            # Missing user and password
        }

        # This should return False but not crash
        result = send_email(
            recipient="test@example.com",
            sender="sender@example.com",
            subject="Test Email",
            html_content="<p>Test content</p>",
            smtp_config=smtp_config
        )

        self.assertFalse(result)

    def test_file_output(self):
        """Test writing HTML email to a file."""
        # Use the script directly to generate an output file
        test_output = Path("tmp/test_output.html")

        # Remove the file if it already exists
        if test_output.exists():
            test_output.unlink()

        # Generate content
        html_content = generate_html_email("test-user", "Test message")

        # Ensure directory exists
        test_output.parent.mkdir(parents=True, exist_ok=True)

        # Write content to file
        with open(test_output, "w") as f:
            f.write(html_content)

        # Verify file was created and contains content
        self.assertTrue(test_output.exists())

        with open(test_output, "r") as f:
            content = f.read()

        self.assertEqual(content, html_content)

        # Clean up
        test_output.unlink()


if __name__ == "__main__":
    unittest.main()
