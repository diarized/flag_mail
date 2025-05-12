#!/usr/bin/env python

import unittest
from unittest.mock import patch, MagicMock
import imaplib

from imap_connector import IMAPConnector


class TestIMAPConnector(unittest.TestCase):
    """Test cases for the IMAPConnector class."""

    @patch('imap_connector.load_dotenv')
    @patch.dict('os.environ', {
        'IMAP_SERVER': 'test.example.com',
        'IMAP_PORT': '993',
        'IMAP_USERNAME': 'test@example.com',
        'IMAP_PASSWORD': 'password123'
    })
    def setUp(self, mock_load_dotenv):
        """Set up test environment."""
        self.connector = IMAPConnector()
        self.connector.conn = MagicMock(spec=imaplib.IMAP4_SSL)
        self.connector.logged_in = True

    def test_initialization(self):
        """Test that the connector initializes correctly."""
        self.assertEqual(self.connector.server, 'test.example.com')
        self.assertEqual(self.connector.port, 993)
        self.assertEqual(self.connector.username, 'test@example.com')
        self.assertEqual(self.connector.password, 'password123')

    @patch('imaplib.IMAP4_SSL')
    def test_connect_success(self, mock_imap):
        """Test successful connection to IMAP server."""
        mock_instance = mock_imap.return_value
        mock_instance.login.return_value = ('OK', [b'LOGIN completed'])
        
        connector = IMAPConnector()
        connector.conn = None  # Reset from setUp
        connector.logged_in = False
        
        result = connector.connect()
        
        self.assertTrue(result)
        self.assertTrue(connector.logged_in)
        mock_instance.login.assert_called_once_with(
            connector.username, connector.password
        )

    @patch('imaplib.IMAP4_SSL')
    def test_connect_failure(self, mock_imap):
        """Test failed connection to IMAP server."""
        mock_instance = mock_imap.return_value
        mock_instance.login.side_effect = imaplib.IMAP4.error('Login failed')
        
        connector = IMAPConnector()
        connector.conn = None  # Reset from setUp
        connector.logged_in = False
        
        result = connector.connect()
        
        self.assertFalse(result)
        self.assertFalse(connector.logged_in)

    def test_disconnect(self):
        """Test disconnection from IMAP server."""
        self.connector.disconnect()
        
        self.connector.conn.logout.assert_called_once()
        self.assertFalse(self.connector.logged_in)
        self.assertIsNone(self.connector.conn)

    def test_list_folders(self):
        """Test listing folders."""
        self.connector.conn.list.return_value = ('OK', [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Archives"',
            b'(\\HasNoChildren) "/" "Newsletters"'
        ])
        
        folders = self.connector.list_folders()
        
        self.assertEqual(len(folders), 3)
        self.assertIn('INBOX', folders)
        self.assertIn('Archives', folders)
        self.assertIn('Newsletters', folders)
        self.connector.conn.list.assert_called_once()

    def test_select_folder(self):
        """Test selecting a folder."""
        self.connector.conn.select.return_value = ('OK', [b'1'])
        
        result = self.connector.select_folder('INBOX')
        
        self.assertTrue(result)
        self.connector.conn.select.assert_called_once_with('INBOX')

    def test_search_emails(self):
        """Test searching for emails."""
        self.connector.conn.search.return_value = ('OK', [b'1 2 3'])
        
        email_ids = self.connector.search_emails('SUBJECT "Test"')
        
        self.assertEqual(len(email_ids), 3)
        self.assertEqual(email_ids, ['1', '2', '3'])
        self.connector.conn.search.assert_called_once_with(
            None, 'SUBJECT "Test"'
        )

    def test_get_email(self):
        """Test fetching an email."""
        # Mock email data
        email_data = b'''From: sender@example.com
Subject: Test Subject
Date: Wed, 12 May 2025 08:00:00 +0200

This is a test email.'''
        
        self.connector.conn.fetch.return_value = ('OK', [(b'1', email_data)])
        
        email_msg = self.connector.get_email('1')
        
        self.assertIsNotNone(email_msg)
        self.assertEqual(email_msg['Subject'], 'Test Subject')
        self.assertEqual(email_msg['From'], 'sender@example.com')
        self.connector.conn.fetch.assert_called_once_with('1', '(RFC822)')

    def test_move_email(self):
        """Test moving an email to another folder."""
        self.connector.conn.copy.return_value = ('OK', None)
        self.connector.conn.store.return_value = ('OK', None)
        self.connector.conn.expunge.return_value = ('OK', None)
        
        result = self.connector.move_email('1', 'Archives')
        
        self.assertTrue(result)
        self.connector.conn.copy.assert_called_once_with('1', 'Archives')
        self.connector.conn.store.assert_called_once_with(
            '1', '+FLAGS', '(\Deleted)'
        )
        self.connector.conn.expunge.assert_called_once()

    def test_move_email_copy_failure(self):
        """Test failure when copying an email."""
        self.connector.conn.copy.return_value = ('NO', 'Copy failed')
        
        result = self.connector.move_email('1', 'Archives')
        
        self.assertFalse(result)
        self.connector.conn.copy.assert_called_once()
        self.connector.conn.store.assert_not_called()
        self.connector.conn.expunge.assert_not_called()

    def test_move_email_delete_failure(self):
        """Test failure when deleting an email after copying."""
        self.connector.conn.copy.return_value = ('OK', None)
        self.connector.conn.store.return_value = ('NO', 'Delete failed')
        
        result = self.connector.move_email('1', 'Archives')
        
        self.assertFalse(result)
        self.connector.conn.copy.assert_called_once()
        self.connector.conn.store.assert_called_once()
        self.connector.conn.expunge.assert_not_called()

    def test_context_manager(self):
        """Test using the connector as a context manager."""
        with patch.object(IMAPConnector, 'connect') as mock_connect:
            with patch.object(IMAPConnector, 'disconnect') as mock_disconnect:
                mock_connect.return_value = True
                
                with IMAPConnector():
                    pass
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()


if __name__ == '__main__':
    unittest.main()