import feedparser
import requests
import json
import time
import hashlib
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

SEARCH_KEYWORDS = [
    "SAP MM",
    "SAP PS",
    "SAP PM consultant",
    "SAP S/4HANA",
    "SAP documentation",
    "SAP testing",
    "SAP UAT",
    "test automation selenium",
    "playwright automation",
    "QA engineer automation",
    "BDD cucumber",
    "SAP SOP",
]

CHECK_INTERVAL  = 300
SEEN_JOBS_FILE  = "seen_jobs.json"

# ─────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)

def build_rss_url(keyword):
    query = keyword.strip().replace(" ", "%20")
    return f"https://www.upwork.com/ab/feed/jobs/rss?q={query}&sort=recency&paging=0%3B10"

def fetch_jobs(keyword):
    url = build_rss_url(keyword)
    try:
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        print(f"[ERROR] Failed to fetch '{keyword}': {e}")
        return []

def job_id(entry):
    return hashlib.md5(entry.get("link", entry.get("title", "")).encode()).hexdigest()

def clean_summary(text, max_chars=300):
    import re
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10, verify=False)
        if r.status_code != 200:
            print(f"[TELEGRAM ERROR] {r.text}")
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

def format_message(entry, keyword):
    title   = entry.get("title", "No title")
    link    = entry.get("link", "")
    summary = clean_summary(entry.get("summary", ""))
    posted  = entry.get("published", "")
    msg = (
        f"🔔 <b>New Upwork Job</b>\n"
        f"🔍 Keyword: <i>{keyword}</i>\n\n"
        f"<b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"🕐 Posted: {posted}\n"
        f"🔗 <a href='{link}'>View Job</a>"
    )
    return msg

def check_all_keywords(seen_jobs):
    new_count = 0
    for keyword in SEARCH_KEYWORDS:
        entries = fetch_jobs(keyword)
        for entry in entries:
            jid = job_id(entry)
            if jid not in seen_jobs:
                seen_jobs.add(jid)
                msg = format_message(entry, keyword)
                send_telegram(msg)
                title = entry.get("title", "")[:60]
                print(f"[NEW] {keyword} → {title}")
                new_count += 1
                time.sleep(1)
        time.sleep(2)
    return new_count

def send_startup_message():
    keywords_list = "\n".join([f"  • {k}" for k in SEARCH_KEYWORDS])
    msg = (
        f"✅ <b>Upwork Job Alert Bot started</b>\n\n"
        f"Monitoring {len(SEARCH_KEYWORDS)} keyword searches:\n"
        f"{keywords_list}\n\n"
        f"⏱ Checking every {CHECK_INTERVAL // 60} minutes."
    )
    send_telegram(msg)

# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Upwork Job Alert Bot")
    print("=" * 50)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n[SETUP REQUIRED] .env file missing or incomplete.")
        print("Create a .env file in the same folder with:")
        print("  TELEGRAM_BOT_TOKEN=your_token_here")
        print("  TELEGRAM_CHAT_ID=your_chat_id_here")
        exit(0)

    seen_jobs = load_seen_jobs()
    print(f"[INFO] Loaded {len(seen_jobs)} previously seen jobs")
    print(f"[INFO] Monitoring {len(SEARCH_KEYWORDS)} keywords")
    print(f"[INFO] Checking every {CHECK_INTERVAL // 60} minutes\n")

    send_startup_message()

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Checking for new jobs...")
        new = check_all_keywords(seen_jobs)
        save_seen_jobs(seen_jobs)
        print(f"[{now}] Done. {new} new jobs found. Sleeping {CHECK_INTERVAL // 60} min...\n")
        time.sleep(CHECK_INTERVAL)