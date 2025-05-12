#!/usr/bin/env python

import imaplib
import email
import os
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IMAPConnector:
    """
    A class to connect to an IMAP server and perform email operations.
    Credentials are loaded from a .env file.
    """
    
    def __init__(self, env_path='.env'):
        """
        Initialize the IMAP connector.
        
        Args:
            env_path: Path to the .env file containing IMAP credentials
        """
        # Load environment variables from .env file
        load_dotenv(env_path)
        
        # Get IMAP server settings from environment variables
        self.server = os.getenv('IMAP_SERVER')
        self.port = int(os.getenv('IMAP_PORT', 993))
        self.username = os.getenv('IMAP_USERNAME')
        self.password = os.getenv('IMAP_PASSWORD')
        
        if not all([self.server, self.username, self.password]):
            raise ValueError("Missing IMAP credentials in .env file")
        
        self.conn = None
        self.logged_in = False
        
    def connect(self):
        """
        Connect to the IMAP server and login.
        
        Returns:
            bool: True if connection and login are successful, False otherwise
        """
        try:
            # Connect to the IMAP server
            self.conn = imaplib.IMAP4_SSL(self.server, self.port)
            
            # Login to the server
            self.conn.login(self.username, self.password)
            self.logged_in = True
            logger.info(
                f"Successfully connected to {self.server} as {self.username}"
            )
            return True
            
        except imaplib.IMAP4.error as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            self.logged_in = False
            return False
    
    def disconnect(self):
        """
        Logout and disconnect from the IMAP server.
        """
        if self.conn and self.logged_in:
            try:
                self.conn.logout()
                logger.info("Successfully logged out from IMAP server")
            except imaplib.IMAP4.error as e:
                logger.error(f"Error during logout: {e}")
            finally:
                self.logged_in = False
                self.conn = None
    
    def list_folders(self):
        """
        List all available folders on the IMAP server.
        
        Returns:
            list: A list of folder names
        """
        if not self.logged_in:
            logger.warning("Not connected to IMAP server")
            return []
        
        try:
            status, folders = self.conn.list()
            if status == 'OK':
                # Parse the folder names
                folder_list = []
                for folder in folders:
                    if isinstance(folder, bytes):
                        folder_str = folder.decode('utf-8')
                        # Extract the folder name from the response
                        split_char = ' "/' if '"/' in folder_str else ' "'
                        parts = folder_str.split(split_char)
                        if len(parts) > 1:
                            name = parts[-1].strip('"')
                            folder_list.append(name)
                
                return folder_list
            else:
                logger.error(f"Failed to list folders: {status}")
                return []
        except imaplib.IMAP4.error as e:
            logger.error(f"Error listing folders: {e}")
            return []
    
    def select_folder(self, folder="INBOX"):
        """
        Select a specific folder on the IMAP server.
        
        Args:
            folder: The name of the folder to select
            
        Returns:
            bool: True if the folder was selected successfully, False otherwise
        """
        if not self.logged_in:
            logger.warning("Not connected to IMAP server")
            return False
        
        try:
            status, data = self.conn.select(folder)
            if status == 'OK':
                logger.info(f"Selected folder: {folder}")
                return True
            else:
                logger.error(f"Failed to select folder {folder}: {status}")
                return False
        except imaplib.IMAP4.error as e:
            logger.error(f"Error selecting folder {folder}: {e}")
            return False
    
    def search_emails(self, criteria="ALL"):
        """
        Search for emails in the currently selected folder.
        
        Args:
            criteria: The search criteria (default is "ALL")
            
        Returns:
            list: A list of email IDs that match the criteria
        """
        if not self.logged_in:
            logger.warning("Not connected to IMAP server")
            return []
        
        try:
            status, data = self.conn.search(None, criteria)
            if status == 'OK':
                # Convert byte strings to integers
                email_ids = data[0].split()
                return [email_id.decode() for email_id in email_ids]
            else:
                logger.error(f"Failed to search emails: {status}")
                return []
        except imaplib.IMAP4.error as e:
            logger.error(f"Error searching emails: {e}")
            return []
    
    def get_email(self, email_id):
        """
        Fetch an email by its ID.
        
        Args:
            email_id: The ID of the email to fetch
            
        Returns:
            email.message.Message: The email message object, or None if failed
        """
        if not self.logged_in:
            logger.warning("Not connected to IMAP server")
            return None
        
        try:
            status, data = self.conn.fetch(email_id, '(RFC822)')
            if status == 'OK':
                raw_email = data[0][1]
                email_message = email.message_from_bytes(raw_email)
                return email_message
            else:
                logger.error(f"Failed to fetch email {email_id}: {status}")
                return None
        except imaplib.IMAP4.error as e:
            logger.error(f"Error fetching email {email_id}: {e}")
            return None
    
    def move_email(self, email_id, destination_folder):
        """
        Move an email to another folder.
        
        Args:
            email_id: The ID of the email to move
            destination_folder: The folder to move the email to
            
        Returns:
            bool: True if the email was moved successfully, False otherwise
        """
        if not self.logged_in:
            logger.warning("Not connected to IMAP server")
            return False
        
        try:
            # Copy the email to the destination folder
            status, data = self.conn.copy(email_id, destination_folder)
            if status != 'OK':
                logger.error(
                    f"Failed to copy email {email_id} to "
                    f"{destination_folder}: {status}"
                )
                return False
            
            # Mark the original email as deleted
            status, data = self.conn.store(email_id, '+FLAGS', '(\Deleted)')
            if status != 'OK':
                logger.error(
                    f"Failed to mark email {email_id} as deleted: {status}"
                )
                return False
            
            # Expunge to actually remove the email
            status, data = self.conn.expunge()
            if status != 'OK':
                logger.error(f"Failed to expunge mailbox: {status}")
                return False
            
            logger.info(
                f"Successfully moved email {email_id} to {destination_folder}"
            )
            return True
        except imaplib.IMAP4.error as e:
            logger.error(
                f"Error moving email {email_id} to {destination_folder}: {e}"
            )
            return False

    def __enter__(self):
        """
        Context manager entry point.
        """
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.
        """
        self.disconnect()


if __name__ == "__main__":
    # Example usage
    with IMAPConnector() as imap:
        if imap.logged_in:
            # List available folders
            folders = imap.list_folders()
            print("Available folders:", folders)
            
            # Select inbox
            imap.select_folder("INBOX")
            
            # Search for all emails in inbox
            email_ids = imap.search_emails()
            print(f"Found {len(email_ids)} emails in INBOX")
            
            # Move the first email to another folder (if any emails exist)
            if email_ids:
                imap.move_email(email_ids[0], "Archives")