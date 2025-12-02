import os
import time
import re
import html
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IVAS_EMAIL = os.getenv("IVAS_EMAIL")
IVAS_PASSWORD = os.getenv("IVAS_PASSWORD")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36"
}

BASE = "https://www.ivasms.com"


def send_telegram(text):
    try:
        r = requests.post(
            TELEGRAM_API,
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except:
        return False


def login(session):
    """
    IVAS login works through API endpoint, not through HTML form.
    This bypass avoids JavaScript.
    """

    login_url = BASE + "/portal/login"
    auth_url = BASE + "/portal/login"

    # Step-1: get CSRF token
    r = session.get(login_url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.find("input", {"name": "_token"})
    csrf = token.get("value") if token else ""

    payload = {
        "_token": csrf,
        "email": IVAS_EMAIL,
        "password": IVAS_PASSWORD
    }

    # Step-2: login POST
    r = session.post(auth_url, headers=HEADERS, data=payload, timeout=15)

    # Step-3: verify login
    live = session.get(BASE + "/portal/live/my_sms", headers=HEADERS, timeout=15)
    if "login" in live.url.lower():
        return False
    return True


def fetch_sms(session):
    url = BASE + "/portal/live/my_sms"
    r = session.get(url, headers=HEADERS, timeout=15)
    sms_list = []

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        return sms_list

    rows = table.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        number = cols[0].get_text(strip=True)
        sid = cols[1].get_text(strip=True) or "IVAS"
        msg = cols[3].get_text(strip=True)

        if msg and "No messages" not in msg:
            sms_list.append((number, sid, msg))

    return sms_list


def extract_otp(message):
    m = re.search(r"(?<!\d)\d{4,8}(?!\d)", message)
    return m.group(0) if m else "Not Found"


def main():
    if not (TELEGRAM_TOKEN and CHAT_ID and IVAS_EMAIL and IVAS_PASSWORD):
        print("Missing secrets!")
        return

    session = requests.Session()
    session.headers.update(HEADERS)

    print("[INFO] Logging in to IVAS...")
    if not login(session):
        print("[ERROR] Login failed!")
        send_telegram("❌ IVAS Login Failed!")
        return

    print("[INFO] Login successful")
    send_telegram("✅ IVAS Bot Started — Monitoring SMS")

    seen = set()

    while True:
        try:
            sms_list = fetch_sms(session)
            for num, sid, msg in sms_list:
                key = num + "|" + msg[:100]
                if key not in seen:
                    otp = extract_otp(msg)
                    text = (
                        f"<b>New OTP Received</b>\n"
                        f"OTP: <code>{otp}</code>\n\n"
                        f"<b>Number:</b> +{num}\n"
                        f"<b>Service:</b> {sid}\n\n"
                        f"<pre>{html.escape(msg)}</pre>"
                    )
                    send_telegram(text)
                    seen.add(key)

            time.sleep(30)

        except Exception as e:
            print("Loop error:", e)
            time.sleep(10)


if __name__ == "__main__":
    main()
