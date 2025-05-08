#!/usr/bin/env python

import mailbox
import requests
import email.utils
from datetime import datetime

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:14b"  # Replace with the model you've loaded

# Define your criteria as part of the system prompt
SYSTEM_PROMPT = """
You are an assistant that helps manage emails. Based on the content of the email and the user's rules,
decide whether to "archive", "flag", or "reply".
Return your decision in the format: Action: <archive|flag|reply>. Reason: <brief reason>.
User rules:
- Archive newsletters and notifications unless urgent
- Flag emails that seem personal or urgent
- Suggest replies only if there's a direct question
"""

def query_ollama(email_text):
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{SYSTEM_PROMPT}\n\nEmail:\n{email_text}",
        "stream": False
    }
    response = requests.post(OLLAMA_API_URL, json=payload)
    response.raise_for_status()
    return response.json()["response"]

def parse_email(msg):
    subject = msg.get("subject", "(no subject)")
    from_ = msg.get("from", "")
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body += part.get_payload(decode=True).decode(errors="ignore")
    else:
        body = msg.get_payload(decode=True).decode(errors="ignore")
    return f"From: {from_}\nSubject: {subject}\n\n{body}"

def main(mbox_path):
    mbox = mailbox.mbox(mbox_path)
    for i in range(len(mbox)):
        try:
            msg = mbox[i]
        except UnicodeDecodeError as e:
            print(f"Skipping email #{i+1} due to read error: {e}")
            continue

        date_hdr = msg.get('Date')
        if not date_hdr:
            continue  # Skip if no date
        try:
            print(date_hdr)
            msg_dt = email.utils.parsedate_to_datetime(date_hdr)
            # Convert to local timezone if necessary
            if msg_dt.tzinfo is not None:
                today = datetime.now(msg_dt.tzinfo).date()
            else:
                today = datetime.today().date()
            if msg_dt.date() != today:
                continue
        except Exception:
            raise
            continue  # Skip if can't parse date

        print(f"\n--- Email #{i+1} ---")
        email_text = parse_email(msg)
        decision = query_ollama(email_text)
        print(decision)

if __name__ == "__main__":
    main("/tmp/imap.stonith.mbox")
