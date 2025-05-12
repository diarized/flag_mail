# IMAP Email Mover

This module allows you to connect to a remote IMAP server using credentials stored in a `.env` file and move emails between folders.

## Features

- Connect to IMAP servers securely
- Search for emails using IMAP search criteria
- Filter emails by subject or sender using regex patterns
- Move emails between folders
- Supports context manager for automatic connection handling
- Command-line interface for easy use

## Available Folders

The following folders are available for email organization:

- INBOX/Important
- Archives
- Newsletters
- Spam
- Trash

## Setup

1. Create a `.env` file based on the `.env.example` template:

```
cp .env.example .env
```

2. Edit the `.env` file with your IMAP server credentials:

```
# IMAP Server Configuration
IMAP_SERVER=mail.example.com
IMAP_PORT=993
IMAP_USERNAME=your_email@example.com
IMAP_PASSWORD=your_password
```

3. Install required dependencies:

```
pip install python-dotenv
```

## Usage

### Command Line Interface

The `move_emails.py` script provides a command-line interface for moving emails:

```bash
# Move all emails from INBOX to Archives
python move_emails.py --destination Archives

# Move up to 5 emails with "Newsletter" in the subject to the Newsletters folder
python move_emails.py --destination Newsletters --subject-match "Newsletter" --limit 5

# Move emails from a specific sender to Spam
python move_emails.py --destination Spam --sender-match "suspicious@example.com"

# Do a dry run (don't actually move emails, just show what would be moved)
python move_emails.py --destination Trash --dry-run
```

### Using the API in Your Code

```python
from imap_connector import IMAPConnector

# Using a context manager (recommended)
with IMAPConnector() as imap:
    if imap.logged_in:
        # Select inbox
        imap.select_folder("INBOX")

        # Search for unread emails
        email_ids = imap.search_emails('UNSEEN')

        # Move the first email to Archives
        if email_ids:
            imap.move_email(email_ids[0], "Archives")
```

## Integration with Existing Code

You can integrate the IMAPConnector with the existing flag.py script to move emails based on AI decisions:

```python
from imap_connector import IMAPConnector

def process_email_actions(decision, email_id, imap_connector):
    """Process the decision from AI and take appropriate action."""
    if "archive" in decision.lower():
        imap_connector.move_email(email_id, "Archives")
    elif "newsletter" in decision.lower():
        imap_connector.move_email(email_id, "Newsletters")
    elif "spam" in decision.lower():
        imap_connector.move_email(email_id, "Spam")
    elif "important" in decision.lower():
        imap_connector.move_email(email_id, "INBOX/Important")
```

## Running Tests

To run the unit tests:

```bash
python -m unittest test_imap_connector.py
```
