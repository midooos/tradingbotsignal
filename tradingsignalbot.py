from playwright.sync_api import sync_playwright
import requests
import schedule
import time
import re
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# === Dummy server to keep Render web service alive ===
def run_dummy_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running on Render.")

        def do_HEAD(self):  # handle Render's health check
            self.send_response(200)
            self.end_headers()
            
    server = HTTPServer(("", 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# === Telegram Bot Credentials ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Debugging env variables
print(f"🤖 BOT_TOKEN: {BOT_TOKEN}")
print(f"💬 CHAT_ID: {CHAT_ID}")

# === Storage to avoid duplicate signals ===
sent_links = set()

# === Keywords to detect real signals ===
TRADING_KEYWORDS = ["buy", "sell", "شراء", "بيع"]

def extract_tp_sl(description):
    tp_match = re.search(r"(TP|Take Profit|الهدف)[^\d]*?(\d{4,6})", description, re.IGNORECASE)
    sl_match = re.search(r"(SL|Stop Loss|الوقف)[^\d]*?(\d{4,6})", description, re.IGNORECASE)
    tp = tp_match.group(2) if tp_match else None
    sl = sl_match.group(2) if sl_match else None
    return tp, sl

def send_signal(title, link, tp=None, sl=None):
    if link in sent_links:
        print(f"⚠️ Duplicate skipped: {link}")
        return
    message = f"📢 إشارة تداول جديدة\n🔸 {title}"
    if tp:
        message += f"\n🎯 TP: {tp}"
    if sl:
        message += f"\n🛑 SL: {sl}"
    message += f"\n🔗 {link}"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, data={"chat_id": CHAT_ID, "text": message})

    if response.status_code == 200:
        sent_links.add(link)
        print(f"✅ Sent: {title}")
    else:
        print(f"❌ Failed to send message ({response.status_code}): {response.text}")

def is_trading_signal(title):
    title = title.lower()
    return any(keyword in title for keyword in TRADING_KEYWORDS)

def get_signals(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"🌐 Visiting: {url}")
        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000)

        cards = page.query_selector_all(".tv-widget-idea__title-row")
        signals = []

        for card in cards[:5]:
            title = card.inner_text()
            print(f"🔍 Checking title: {title}")
            href = card.query_selector("a").get_attribute("href")
            full_link = f"https://www.tradingview.com{href}"

            if is_trading_signal(title):
                print(f"✅ Detected trading signal: {title}")
                detail_page = browser.new_page()
                detail_page.goto(full_link, timeout=60000)
                detail_page.wait_for_timeout(3000)
                desc_elem = detail_page.query_selector(".tv-chart-view__description, .tv-widget-idea__description")
                description = desc_elem.inner_text() if desc_elem else ""
                tp, sl = extract_tp_sl(description)
                signals.append((title, full_link, tp, sl))
                detail_page.close()

        browser.close()
        print(f"📦 Extracted {len(signals)} signal(s) from {url}")
        return signals

def job():
    print("🔁 Running scheduled job: Checking for new trading signals...")
    urls = [
        "https://www.tradingview.com/symbols/BTCUSD/ideas/",
        "https://www.tradingview.com/symbols/ETHUSD/ideas/",
        "https://www.tradingview.com/symbols/XAUUSD/ideas/"
    ]
    for url in urls:
        try:
            signals = get_signals(url)
            for title, link, tp, sl in signals:
                send_signal(title, link, tp, sl)
        except Exception as e:
            print(f"⚠️ Error during signal extraction or sending: {e}")

# === Initial Run ===
job()

# === Scheduler ===
schedule.every(10).minutes.do(job)

print("🚀 Bot is running and waiting for new signals...")
while True:
    schedule.run_pending()
    time.sleep(1)
