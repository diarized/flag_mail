#!/usr/bin/env python

import argparse
import logging
import sys
import re
from imap_connector import IMAPConnector
from flag import query_ollama, parse_email

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_argparser():
    """Setup the argument parser for command-line options."""
    parser = argparse.ArgumentParser(
        description="Process emails from IMAP server using AI and move them."
    )
    
    parser.add_argument(
        "--folder", 
        type=str, 
        default="INBOX",
        help="IMAP folder to process emails from (default: INBOX)"
    )
    
    parser.add_argument(
        "--limit", 
        type=int, 
        default=10,
        help="Maximum number of emails to process (default: 10)"
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Don't actually move emails, just show decisions"
    )
    
    parser.add_argument(
        "--env-file", 
        type=str, 
        default=".env",
        help="Path to .env file with IMAP credentials (default: .env)"
    )
    
    return parser


def process_email_action(decision, email_id, imap_connector, dry_run=False):
    """
    Process the decision from AI and take appropriate action.
    
    Args:
        decision: Decision text from the AI
        email_id: Email ID to act upon
        imap_connector: IMAPConnector instance
        dry_run: If True, don't actually move emails
        
    Returns:
        str: The folder the email was moved to, or None if not moved
    """
    action_match = re.search(r"Action:\s*(\w+)", decision)
    if not action_match:
        logger.warning(f"Could not parse action from decision: {decision}")
        return None
        
    action = action_match.group(1).lower()
    
    # Determine target folder based on action
    target_folder = None
    
    if action == "archive":
        target_folder = "Archives"
    elif action == "flag":
        if "newsletter" in decision.lower():
            target_folder = "Newsletters"
        else:
            target_folder = "INBOX/Important"
    elif action == "spam" or "spam" in decision.lower():
        target_folder = "Spam"
    elif action == "trash" or "trash" in decision.lower():
        target_folder = "Trash"
        
    if not target_folder:
        logger.info(f"No folder change needed for action: {action}")
        return None
        
    if dry_run:
        logger.info(f"Would move email {email_id} to {target_folder}")
        return target_folder
        
    # Actually move the email
    if imap_connector.move_email(email_id, target_folder):
        logger.info(f"Moved email {email_id} to {target_folder}")
        return target_folder
    else:
        logger.error(f"Failed to move email {email_id} to {target_folder}")
        return None


def main():
    """Main function to process emails from IMAP server."""
    parser = setup_argparser()
    args = parser.parse_args()
    
    try:
        with IMAPConnector(env_path=args.env_file) as imap:
            if not imap.logged_in:
                logger.error("Failed to connect to IMAP server")
                return 1
                
            # Select the source folder
            if not imap.select_folder(args.folder):
                logger.error(f"Failed to select folder: {args.folder}")
                return 1
                
            # Search for unread emails (you can change this criteria)
            email_ids = imap.search_emails('UNSEEN')
            logger.info(
                f"Found {len(email_ids)} unread emails in {args.folder}"
            )
            
            # Limit the number of emails to process
            email_ids = email_ids[:args.limit]
            
            if not email_ids:
                logger.info("No emails to process")
                return 0
                
            results = {
                "processed": 0,
                "moved": 0,
                "errors": 0,
                "by_folder": {}
            }
            
            # Process each email
            for email_id in email_ids:
                try:
                    # Get the email
                    msg = imap.get_email(email_id)
                    if not msg:
                        logger.error(f"Failed to fetch email {email_id}")
                        results["errors"] += 1
                        continue
                        
                    # Parse the email
                    email_text = parse_email(msg)
                    
                    # Get decision from AI
                    logger.info(f"Processing email {email_id}")
                    decision = query_ollama(email_text)
                    logger.info(f"AI Decision: {decision}")
                    
                    # Process the decision
                    target_folder = process_email_action(
                        decision, email_id, imap, args.dry_run
                    )
                    
                    results["processed"] += 1
                    if target_folder:
                        results["moved"] += 1
                        results["by_folder"][target_folder] = (
                            results["by_folder"].get(target_folder, 0) + 1
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    results["errors"] += 1
            
            # Print summary
            logger.info("Processing complete!")
            logger.info(f"Processed: {results['processed']} emails")
            logger.info(f"Moved: {results['moved']} emails")
            logger.info(f"Errors: {results['errors']} emails")
            
            if results["by_folder"]:
                logger.info("Emails moved by folder:")
                for folder, count in results["by_folder"].items():
                    logger.info(f"  - {folder}: {count} emails")
            
            return 0
            
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())