#!/usr/bin/env python

import unittest
from flag import process_email_decision


class TestFlagFunctions(unittest.TestCase):
    """Test cases for flag.py functionality."""

    def test_process_email_decision(self):
        """Test that email decisions are correctly processed."""
        # Mock IMAP connector for testing
        class MockIMAPConnector:
            def __init__(self):
                self.moved_emails = {}
                
            def move_email(self, email_id, target_folder):
                self.moved_emails[email_id] = target_folder
                return True
        
        # Create test cases
        test_cases = [
            {
                "decision": "Action: archive. Reason: This is a notification.",
                "expected_folder": "Archives"
            },
            {
                "decision": "Action: important. "
                            "Reason: Contains direct questions.",
                "expected_folder": "INBOX/Important"
            },
            {
                "decision": "Action: flag. "
                            "Reason: This is an important message.",
                "expected_folder": "INBOX/Important"
            },
            {
                "decision": "Action: newsletter. "
                            "Reason: This is a newsletter.",
                "expected_folder": "Newsletters"
            },
            {
                "decision": "Action: flag. "
                            "Reason: This is a newsletter subscription.",
                "expected_folder": "Newsletters"
            },
            {
                "decision": "Action: spam. Reason: This is spam.",
                "expected_folder": "Spam"
            },
            {
                "decision": "Action: trash. Reason: This is trash.",
                "expected_folder": "Trash"
            },
            {
                "decision": "Invalid decision format",
                "expected_folder": None
            }
        ]
        
        # Test with dry run
        mock_imap = MockIMAPConnector()
        for i, test in enumerate(test_cases):
            email_id = str(i+1)
            target_folder = process_email_decision(
                test["decision"], email_id, mock_imap, dry_run=True
            )
            self.assertEqual(
                target_folder, 
                test["expected_folder"],
                f"Failed on test case {i+1}: {test['decision']}"
            )
            # Ensure no actual moves occurred in dry run
            self.assertEqual(len(mock_imap.moved_emails), 0)
            
        # Test without dry run
        mock_imap = MockIMAPConnector()
        for i, test in enumerate(test_cases):
            email_id = str(i+1)
            target_folder = process_email_decision(
                test["decision"], email_id, mock_imap, dry_run=False
            )
            self.assertEqual(
                target_folder, 
                test["expected_folder"],
                f"Failed on test case {i+1}: {test['decision']}"
            )
            
            # Check if the email was properly moved
            if test["expected_folder"]:
                self.assertEqual(
                    mock_imap.moved_emails.get(email_id), 
                    test["expected_folder"]
                )
            else:
                self.assertNotIn(email_id, mock_imap.moved_emails)


if __name__ == "__main__":
    unittest.main()