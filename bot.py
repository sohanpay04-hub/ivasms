#!/usr/bin/env python3
import os, time, re, html, hashlib, logging, requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
log = logging.getLogger("ivas_requests_bot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IVAS_EMAIL = os.getenv("IVAS_EMAIL")
IVAS_PASSWORD = os.getenv("IVAS_PASSWORD")

IVAS_LOGIN = "https://www.ivasms.com/portal/login"
IVAS_SMS = "https://www.ivasms.com/portal/live/my_sms"

def send_telegram(txt):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"},
            timeout=10)
    except: pass

def extract_otp(txt):
    m = re.search(r"(?<!\d)\d{4,8}(?!\d)", txt)
    return m.group(0) if m else "Not Found"

def parse_sms(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    res = []
    if not table: return res
    rows = table.find_all("tr")[1:]
    for r in rows:
        td = r.find_all("td")
        if len(td) < 4: continue
        num = td[0].get_text(strip=True)
        sid = td[1].get_text(strip=True) or "IVAS"
        msg = td[3].get_text(strip=True)
        if msg and msg != "No messages":
            res.append({"num": num, "sid": sid, "msg": msg})
    return res

def login(sess):
    r = sess.get(IVAS_LOGIN)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form")
    data = {}
    for i in form.find_all("input"):
        if i.get("name"):
            data[i.get("name")] = i.get("value","")
    data["email"] = IVAS_EMAIL
    data["password"] = IVAS_PASSWORD
    sess.post(IVAS_LOGIN, data=data)
    x = sess.get(IVAS_SMS)
    return "login" not in x.url.lower()

def main():
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})
    if not login(sess):
        log.error("Login failed")
        return
    send_telegram("IVAS Bot Started ✔️")
    seen = set()
    while True:
        try:
            r = sess.get(IVAS_SMS)
            sms = parse_sms(r.text)
            for s in sms:
                uid = hashlib.sha1((s["num"] + s["msg"]).encode()).hexdigest()
                if uid in seen: 
                    continue
                seen.add(uid)
                otp = extract_otp(s["msg"])
                msg = f"📩 New OTP\nOTP: <code>{otp}</code>\nService: {s['sid']}\nNumber: +{s['num']}\n\n<pre>{html.escape(s['msg'])}</pre>"
                send_telegram(msg)
            time.sleep(30)
        except Exception as e:
            log.error(e)
            time.sleep(10)

if __name__ == "__main__":
    main()
