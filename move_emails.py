#!/usr/bin/env python

import argparse
import logging
import re
import sys
from imap_connector import IMAPConnector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Available folders
AVAILABLE_FOLDERS = [
    "INBOX/Important",
    "Archives",
    "Newsletters",
    "Spam",
    "Trash"
]


def setup_argparser():
    """Setup the argument parser for command-line options."""
    parser = argparse.ArgumentParser(
        description="Move emails between folders on an IMAP server."
    )
    
    parser.add_argument(
        "--search", 
        type=str, 
        default="ALL",
        help="IMAP search criteria (default: ALL)"
    )
    
    parser.add_argument(
        "--source", 
        type=str, 
        default="INBOX",
        help="Source folder to search in (default: INBOX)"
    )
    
    parser.add_argument(
        "--destination", 
        type=str, 
        required=True,
        choices=AVAILABLE_FOLDERS,
        help="Destination folder to move emails to"
    )
    
    parser.add_argument(
        "--subject-match", 
        type=str,
        help="Only move emails with subjects matching this regex pattern"
    )
    
    parser.add_argument(
        "--sender-match", 
        type=str,
        help="Only move emails from senders matching this regex pattern"
    )
    
    parser.add_argument(
        "--limit", 
        type=int, 
        default=10,
        help="Maximum number of emails to move (default: 10)"
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Don't actually move emails, just show what would be moved"
    )
    
    parser.add_argument(
        "--env-file", 
        type=str, 
        default=".env",
        help="Path to .env file with IMAP credentials (default: .env)"
    )
    
    return parser


def filter_emails_by_content(imap, email_ids, subject_pattern=None,
                             sender_pattern=None, limit=10):
    """
    Filter emails by content (subject and/or sender) using regex patterns.
    
    Args:
        imap: The IMAPConnector instance
        email_ids: List of email IDs to filter
        subject_pattern: Regex pattern to match against email subjects
        sender_pattern: Regex pattern to match against email senders
        limit: Maximum number of emails to return
        
    Returns:
        list: Filtered list of email IDs
    """
    if not subject_pattern and not sender_pattern:
        return email_ids[:limit]
    
    subject_regex = re.compile(subject_pattern) if subject_pattern else None
    sender_regex = re.compile(sender_pattern) if sender_pattern else None
    
    filtered_ids = []
    
    for email_id in email_ids:
        if len(filtered_ids) >= limit:
            break
            
        msg = imap.get_email(email_id)
        if not msg:
            continue
            
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        
        subject_match = True
        sender_match = True
        
        if subject_regex:
            subject_match = bool(subject_regex.search(subject))
            
        if sender_regex:
            sender_match = bool(sender_regex.search(sender))
            
        if subject_match and sender_match:
            filtered_ids.append(email_id)
            
    return filtered_ids


def main():
    """Main function to run the email mover."""
    parser = setup_argparser()
    args = parser.parse_args()
    
    try:
        with IMAPConnector(env_path=args.env_file) as imap:
            if not imap.logged_in:
                logger.error("Failed to connect to IMAP server")
                return 1
                
            # Select the source folder
            if not imap.select_folder(args.source):
                logger.error(f"Failed to select folder: {args.source}")
                return 1
                
            # Search for emails matching the criteria
            email_ids = imap.search_emails(args.search)
            logger.info(
                f"Found {len(email_ids)} emails matching search criteria"
            )
            
            if not email_ids:
                logger.info("No emails to move")
                return 0
                
            # Filter emails by content if needed
            filtered_ids = filter_emails_by_content(
                imap, 
                email_ids, 
                args.subject_match, 
                args.sender_match, 
                args.limit
            )
            
            logger.info(
                f"Selected {len(filtered_ids)} emails to move to "
                f"{args.destination}"
            )
            
            if args.dry_run:
                logger.info("DRY RUN - No emails will be moved")
                for email_id in filtered_ids:
                    msg = imap.get_email(email_id)
                    if msg:
                        subject = msg.get("Subject", "(no subject)")
                        sender = msg.get("From", "(unknown)")
                        logger.info(
                            f"Would move email {email_id}: "
                            f"From: {sender}, Subject: {subject}"
                        )
                return 0
                
            # Move the filtered emails
            success_count = 0
            for email_id in filtered_ids:
                msg = imap.get_email(email_id)
                if not msg:
                    continue
                    
                subject = msg.get("Subject", "(no subject)")
                sender = msg.get("From", "(unknown)")
                
                logger.info(
                    f"Moving email {email_id}: "
                    f"From: {sender}, Subject: {subject}"
                )
                
                if imap.move_email(email_id, args.destination):
                    success_count += 1
                    
            logger.info(
                f"Successfully moved {success_count} out of "
                f"{len(filtered_ids)} emails"
            )
            
            return 0
            
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())