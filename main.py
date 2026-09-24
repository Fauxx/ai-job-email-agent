import time
import os
import imaplib
import email
from email.header import decode_header
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

NOTIFIED_CACHE = "cache/notified_today.json"

def load_notified_cache():
    """Load the set of UIDs we already sent Telegram alerts for today."""
    if not os.path.exists(NOTIFIED_CACHE):
        return {"date": "", "uids": []}
    with open(NOTIFIED_CACHE, "r") as f:
        data = json.load(f)
    # Reset if it's a new day (UTC)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if data.get("date") != today:
        return {"date": today, "uids": []}
    return data

def save_notified_cache(data):
    os.makedirs("cache", exist_ok=True)
    with open(NOTIFIED_CACHE, "w") as f:
        json.dump(data, f)

EMAIL_USER = os.getenv("IMAP_USER")
EMAIL_PASS = os.getenv("IMAP_PASS")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-3.6-flash')

def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    else:
        return msg.get_payload(decode=True).decode(errors="ignore")
    return ""

def analyze_batch_with_ai(email_list, retries=3):
    """Analyze all emails in a single AI call. Returns a list of result dicts."""
    if not email_list:
        return []

    # Build a numbered list of emails for the prompt
    email_entries = ""
    for i, e in enumerate(email_list, 1):
        email_entries += f"""
--- Email {i} ---
From: {e['sender']}
Subject: {e['subject']}
Body snippet: {e['body'][:1000]}
"""

    prompt = f"""
You are a smart assistant managing a job seeker's inbox.
Read the following {len(email_list)} emails and determine if each is related to a job application, interview, rejection, or recruiter reaching out.

{email_entries}

Respond strictly with a JSON array of {len(email_list)} objects (one per email, in order):
[
  {{
    "email_index": 1,
    "is_job_related": true/false,
    "type": "Interview" | "Recruiter Reachout" | "Update" | "Rejection" | "Offer" | "None",
    "company_name": "Name of company or N/A",
    "job_position": "Name of job position/role or N/A",
    "summary": "1 sentence summary"
  }},
  ...
]
"""
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            text = (response.text
                    .replace("```json", "").replace("```", "")
                    .replace("True", "true").replace("False", "false")
                    .strip())
            print(f"🤖 RAW AI OUTPUT: {text}")
            return json.loads(text)
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait = 30 * (attempt + 1)  # 30s, 60s
                print(f"⚠️ Rate limit hit. Retrying in {wait}s... (Attempt {attempt+1}/{retries})")
                time.sleep(wait)
            else:
                print(f"🚨 EXCEPTION: {e}")
                return None  # Signal total failure — don't cache anything

def send_summary_alert(total, job_related, job_details):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
        
    if job_related == 0:
        message = f"📊 *Run Summary*\nProcessed {total} emails.\nNo new job-related emails."
    else:
        message = f"📊 *Run Summary*\nProcessed {total} new emails. Found {job_related} job-related updates.\n\n"
        for job in job_details:
            comp = job.get('company_name', 'Unknown')
            pos = job.get('job_position', 'N/A')
            t = job.get('type', 'Unknown')
            summ = job.get('summary', '')
            link = job.get('link', '')
            
            message += f"🏢 *{comp}*\n"
            message += f"💼 *Role:* {pos}\n"
            message += f"📌 *Type:* {t}\n"
            message += f"📝 *Details:* {summ}\n"
            message += f"🔗 [Open Email in Gmail]({link})\n\n"
            message += "──────────────\n\n"
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

def run_email_agent():
    print("🔍 Connecting to inbox...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    # Search for today's emails
    today_str = datetime.now(timezone.utc).strftime("%d-%b-%Y")  # e.g. "24-Sep-2026"
    status, messages = mail.uid('search', None, f'SINCE "{today_str}"')
    all_uids = messages[0].split()

    # Filter out already-notified UIDs
    cache = load_notified_cache()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache["date"] = today
    notified_set = set(cache.get("uids", []))
    new_uids = [uid for uid in all_uids if uid.decode() not in notified_set]

    if not new_uids:
        print("📭 No new emails to process today.")
        mail.logout()
        return

    print(f"📧 Found {len(new_uids)} new emails today. Fetching...")

    # Fetch all email metadata
    email_list = []
    for uid in new_uids:
        res, msg_data = mail.uid('fetch', uid, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                subject_header = decode_header(msg["Subject"])[0]
                subject = subject_header[0]
                encoding = subject_header[1]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")

                sender = msg.get("From")
                body = get_email_body(msg)

                msg_id = msg.get("Message-ID", "")
                if msg_id:
                    msg_id_clean = msg_id.strip("<>")
                    gmail_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid%3A{msg_id_clean}"
                else:
                    gmail_link = "https://mail.google.com/mail/u/0/#inbox"

                email_list.append({
                    "uid": uid.decode(),
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "gmail_link": gmail_link,
                })

    print(f"🤖 Sending {len(email_list)} emails to AI in one batch...")
    results = analyze_batch_with_ai(email_list)

    if results is None:
        print("🚨 AI call failed entirely. Will retry these emails next run.")
        mail.logout()
        return  # Don't update cache — emails will be retried

    # Process results
    job_details = []
    processed_uids = []
    for i, result in enumerate(results):
        idx = result.get("email_index", i + 1) - 1
        if idx < len(email_list):
            e = email_list[idx]
            processed_uids.append(e["uid"])
            if result.get("is_job_related"):
                print(f"✅ Job Related: {result.get('company_name')} — {e['subject'][:40]}")
                result["link"] = e["gmail_link"]
                job_details.append(result)
            else:
                print(f"❌ Not job-related: {e['subject'][:40]}")

    # Send Telegram summary
    if email_list:
        send_summary_alert(len(email_list), len(job_details), job_details)

    # Update notified cache
    cache["uids"] = list(notified_set | set(processed_uids))
    save_notified_cache(cache)
    print(f"\n💾 Cached {len(processed_uids)} processed UIDs for today.")
    mail.logout()

if __name__ == "__main__":
    run_email_agent()
