import os
import imaplib
import email
from email.header import decode_header
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# Load env variables (for local testing)
load_dotenv()

# Configuration
EMAIL_USER = os.getenv("IMAP_USER")
EMAIL_PASS = os.getenv("IMAP_PASS")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

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
        "summary": "1 sentence summary of what they want"
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        return {"is_job_related": False, "error": str(e)}

def send_alert(company, type_, summary):
    if not WEBHOOK_URL:
        print("No Webhook URL configured. Alerting in console only.")
        return
        
    payload = {
        "content": f"🚨 **JOB ALERT: {company}** 🚨\n**Type:** {type_}\n**Summary:** {summary}"
    }
    requests.post(WEBHOOK_URL, json=payload)

def run_email_agent():
    print("🔍 Connecting to inbox...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    # Search for UNSEEN emails
    status, messages = mail.search(None, 'UNSEEN')
    email_ids = messages[0].split()
    
    if not email_ids:
        print("📭 No new emails to check.")
        mail.logout()
        return

    print(f"📧 Found {len(email_ids)} new emails. Asking AI to analyze...\n")

    for e_id in email_ids:
        res, msg_data = mail.fetch(e_id, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                sender = msg.get("From")
                body = get_email_body(msg)
                
                ai_result = analyze_with_ai(sender, subject, body)
                
                if ai_result.get("is_job_related"):
                    print(f"✅ Alert Triggered for {ai_result.get('company_name')}")
                    send_alert(
                        ai_result.get("company_name"), 
                        ai_result.get("type"), 
                        ai_result.get("summary")
                    )
                else:
                    print(f"❌ Ignored: {subject[:30]}...")
                    
    mail.logout()

if __name__ == "__main__":
    run_email_agent()
