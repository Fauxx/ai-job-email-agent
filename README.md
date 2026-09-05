# AI Job Email Agent

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?logo=google&logoColor=white)
![Telegram](https://img.shields.io/badge/Alerts-Telegram-26A5E4?logo=telegram&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/Automation-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)
![Terraform](https://img.shields.io/badge/IaC-Terraform-844FBA?logo=terraform&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

AI Job Email Agent monitors a Gmail inbox, uses Google Gemini to classify job-related messages, and sends Telegram alerts for important updates (interviews, recruiter outreach, rejections, offers, and more).

## What this project does

- Connects to Gmail via IMAP
- Reads only new emails based on stored UID cache
- Extracts message metadata and plain-text body
- Sends email context to Gemini for classification
- Triggers Telegram notifications for job-related emails
- Runs automatically on a schedule via GitHub Actions

## Repository structure

- `/home/runner/work/ai-job-email-agent/ai-job-email-agent/main.py`  
  Core agent logic (IMAP fetch, Gemini analysis, Telegram alerts, UID caching)
- `/home/runner/work/ai-job-email-agent/ai-job-email-agent/requirements.txt`  
  Python dependencies
- `/home/runner/work/ai-job-email-agent/ai-job-email-agent/.env.example`  
  Local environment variable template
- `/home/runner/work/ai-job-email-agent/ai-job-email-agent/.github/workflows/agent.yml`  
  Scheduled/manual CI workflow for running the agent
- `/home/runner/work/ai-job-email-agent/ai-job-email-agent/terraform/00-bootstrap/*`  
  Terraform bootstrap to provision GitHub Actions secrets

## Tech stack

- **Language:** Python
- **AI:** `google-generativeai` (Gemini)
- **Email:** `imaplib`, `email` (Python stdlib)
- **Notifications:** Telegram Bot API via `requests`
- **Config:** `python-dotenv`
- **Automation:** GitHub Actions + Actions Cache
- **Infrastructure:** Terraform + GitHub provider

## How it works

1. Loads credentials from environment variables.
2. Connects to `imap.gmail.com` over SSL.
3. Reads last processed UID from `cache/last_uid.txt` if present.
4. Fetches only unseen/new UIDs.
5. For each new message:
   - Decodes subject and sender
   - Extracts plain-text body
   - Builds a direct Gmail link using `Message-ID`
   - Sends prompt to Gemini and parses strict JSON response
6. If email is job-related, sends formatted Telegram alert.
7. Saves highest UID for the next run.

## Environment variables

Use the values defined in:

- `/home/runner/work/ai-job-email-agent/ai-job-email-agent/.env.example`

Required:

- `IMAP_USER`
- `IMAP_PASS`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Create a `.env` file from `.env.example` and fill in secrets.
4. Run:
   - `python main.py`

## GitHub Actions automation

Workflow file:

- `/home/runner/work/ai-job-email-agent/ai-job-email-agent/.github/workflows/agent.yml`

Behavior:

- Runs every 2 hours (`cron: 0 */2 * * *`)
- Can also run manually with `workflow_dispatch`
- Restores `cache/` between runs using `actions/cache`
- Injects runtime secrets from repository GitHub Actions secrets

## Terraform bootstrap (optional)

Terraform in `terraform/00-bootstrap` creates these repository secrets:

- `IMAP_USER`
- `IMAP_PASS`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Use `terraform.tfvars.example` as a starting template for variables.

## Notes and limitations

- The parser prioritizes `text/plain` email parts.
- AI output parsing assumes valid JSON and may fail on malformed responses.
- The first run currently starts scanning from `05-Sep-2026`.
- A 4-second delay is applied after each processed message.

## License

This project is licensed under the **MIT License**.
