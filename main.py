import time
import os
import imaplib
import email
from email.header import decode_header
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

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

def analyze_with_ai(sender, subject, body):
    prompt = f"""
    You are a smart assistant managing a job seeker's inbox. 
    Read the following email and determine if it is related to a job application, an interview, a rejection, or a recruiter reaching out.
    
    From: {sender}
    Subject: {subject}
    Body snippet: {body[:1500]}
    
    Respond strictly in JSON format:
    {{
        "is_job_related": true/false,
        "type": "Interview" | "Recruiter Reachout" | "Update" | "Rejection" | "Offer" | "None",
        "company_name": "Name of company or N/A",
        "job_position": "Name of job position/role or N/A",
        "summary": "1 sentence summary of what they want"
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").replace("True", "true").replace("False", "false").strip()
        print(f"🤖 RAW AI OUTPUT: {text}")
        return json.loads(text)
    except Exception as e:
        print(f"🚨 EXCEPTION: {e}")
        return {"is_job_related": False, "error": str(e)}

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
            
            message += f"🏢 *{comp}* - {pos}\n"
            message += f"  ├ *Type:* {t}\n"
            message += f"  ├ *Details:* {summ}\n"
            message += f"  └ 🔗 [Open Email in Gmail]({link})\n\n"
        
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

    last_uid = 0
    if os.path.exists("cache/last_uid.txt"):
        with open("cache/last_uid.txt", "r") as f:
            content = f.read().strip()
            if content.isdigit():
                last_uid = int(content)

    print(f"📂 Last processed UID: {last_uid}")

    if last_uid > 0:
        status, messages = mail.uid('search', None, f'UID {last_uid + 1}:*')
    else:
        print("🚀 First run detected. Scanning from Sept 5, 2026 onwards...")
        status, messages = mail.uid('search', None, 'SINCE "05-Sep-2026"')

    uids = messages[0].split()
    new_uids = [uid for uid in uids if int(uid) > last_uid]

    if not new_uids:
        print("📭 No new emails since last check.")
        mail.logout()
        return

    print(f"📧 Found {len(new_uids)} new emails. Asking AI to analyze...\n")
    highest_uid = last_uid
    
    total_processed = 0
    job_related_count = 0
    job_details = []

    for uid in new_uids:
        total_processed += 1
        uid_int = int(uid)
        if uid_int > highest_uid:
            highest_uid = uid_int
            
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
                
                # Extract Message-ID to build a direct Gmail link
                msg_id = msg.get("Message-ID", "")
                if msg_id:
                    msg_id_clean = msg_id.strip("<>")
                    gmail_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid%3A{msg_id_clean}"
                else:
                    gmail_link = "https://mail.google.com/mail/u/0/#inbox"
                
                print(f"👀 Scanning: {subject[:40]}...")
                ai_result = analyze_with_ai(sender, subject, body)
                
                if ai_result.get("is_job_related"):
                    print(f"✅ Job Related: {ai_result.get('company_name')}")
                    job_related_count += 1
                    ai_result['link'] = gmail_link
                    job_details.append(ai_result)
                    time.sleep(4)
                else:
                    print(f"❌ Ignored")
                    time.sleep(4)

    if total_processed > 0:
        send_summary_alert(total_processed, job_related_count, job_details)

    os.makedirs("cache", exist_ok=True)
    with open("cache/last_uid.txt", "w") as f:
        f.write(str(highest_uid))
        
    print(f"\n💾 Saved highest UID ({highest_uid}) to cache.")
    mail.logout()

if __name__ == "__main__":
    run_email_agent()
