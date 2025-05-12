#!/usr/bin/env python

import email.utils
import re
import logging
import argparse
import sys
from datetime import datetime
from imap_connector import IMAPConnector
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:14b"  # Replace with the model you've loaded

# Define your criteria as part of the system prompt
SYSTEM_PROMPT = """
You are an assistant that helps manage emails. Based on the content of the
email and the user's rules, decide whether to "archive", "flag", or "reply".
Return your decision in the format: Action: <archive|important|newsletter>.
Reason: <brief reason>.
User rules:
- Archive notifications in 'Archives' folder unless urgent
- If there's a direct question move the email to 'INBOX/Important'
- Move emails that seem personal or urgent to 'INBOX/Important'
- Flag newsletters by moving them to 'Newsletters' folder
"""


def query_ollama(email_text):
    """Query Ollama API to get a decision on email handling."""
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{SYSTEM_PROMPT}\n\nEmail:\n{email_text}",
        "stream": False
    }
    response = requests.post(OLLAMA_API_URL, json=payload)
    response.raise_for_status()
    return response.json()["response"]


def parse_email(msg):
    """Parse an email message into text format."""
    subject = msg.get("subject", "(no subject)")
    from_ = msg.get("from", "")
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body += part.get_payload(decode=True).decode(errors="ignore")
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        except Exception:
            body = msg.get_payload(decode=False)
            
    return f"From: {from_}\nSubject: {subject}\n\n{body}"


def process_email_decision(decision, email_id, imap_connector, dry_run=False):
    """
    Process the decision from Ollama and move the email to the appropriate
    folder.
    
    Args:
        decision: Decision text from Ollama
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
    elif (action == "important" or
          (action == "flag" and "important" in decision.lower())):
        target_folder = "INBOX/Important"
    elif (action == "newsletter" or
          (action == "flag" and "newsletter" in decision.lower())):
        target_folder = "Newsletters"
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


def setup_argparser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Process emails from IMAP using Ollama AI and move them "
                    "to appropriate folders."
    )
    
    parser.add_argument(
        "--folder",
        type=str,
        default="INBOX",
        help="Source folder to process emails from (default: INBOX)"
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
    
    parser.add_argument(
        "--today-only",
        action="store_true",
        help="Process only today's emails"
    )
    
    return parser


def process_imap_emails(args):
    """Process emails from IMAP server using Ollama AI."""
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
                    
                    # Check if we should process only today's emails
                    if args.today_only:
                        date_hdr = msg.get('Date')
                        if not date_hdr:
                            logger.info(
                                f"Skipping email {email_id} (no date header)"
                            )
                            continue
                        
                        try:
                            msg_dt = email.utils.parsedate_to_datetime(
                                date_hdr
                            )
                            # Convert to local timezone if necessary
                            if msg_dt.tzinfo is not None:
                                today = datetime.now(msg_dt.tzinfo).date()
                            else:
                                today = datetime.today().date()
                                
                            if msg_dt.date() != today:
                                logger.info(
                                    f"Skipping email {email_id} "
                                    f"(not from today)"
                                )
                                continue
                        except Exception as e:
                            logger.warning(
                                f"Skipping email {email_id} "
                                f"(date parsing error): {e}"
                            )
                            continue
                        
                    # Parse the email
                    email_text = parse_email(msg)
                    
                    # Get decision from Ollama
                    logger.info(f"Processing email {email_id}")
                    decision = query_ollama(email_text)
                    logger.info(f"AI Decision: {decision}")
                    
                    # Process the decision
                    target_folder = process_email_decision(
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


def main():
    """
    Main function that handles command line arguments and starts
    email processing.
    """
    parser = setup_argparser()
    args = parser.parse_args()
    return process_imap_emails(args)


if __name__ == "__main__":
    sys.exit(main())
