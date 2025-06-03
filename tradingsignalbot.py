from playwright.sync_api import sync_playwright
import requests
import schedule
import time
import re

# Telegram credentials
BOT_TOKEN = "7214208491:AAFkaFAQDpD2eJ-NztiyGzQOu_gejlES3rc"
CHAT_ID = "5695598169"

# Store sent signals to avoid duplicates
sent_links = set()

# Keywords that indicate actionable signals
TRADING_KEYWORDS = ["buy", "sell", "شراء", "بيع"]

def extract_tp_sl(description):
    # Look for numbers after TP or SL (English or Arabic)
    tp_match = re.search(r"(TP|Take Profit|الهدف)[^\d]*?(\d{4,6})", description, re.IGNORECASE)
    sl_match = re.search(r"(SL|Stop Loss|الوقف)[^\d]*?(\d{4,6})", description, re.IGNORECASE)
    
    tp = tp_match.group(2) if tp_match else None
    sl = sl_match.group(2) if sl_match else None
    return tp, sl

def send_signal(title, link, tp=None, sl=None):
    if link in sent_links:
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
        print(f"❌ Failed to send: {response.text}")

def is_trading_signal(title):
    title_lower = title.lower()
    return any(word in title_lower for word in TRADING_KEYWORDS)

def get_signals(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000)

        signals = []
        cards = page.query_selector_all(".tv-widget-idea__title-row")

        for card in cards[:5]:
            title = card.inner_text()
            link_path = card.query_selector("a").get_attribute("href")
            full_link = f"https://www.tradingview.com{link_path}"

            if is_trading_signal(title):
                # Visit the full idea page to get description
                idea_page = browser.new_page()
                idea_page.goto(full_link, timeout=60000)
                idea_page.wait_for_timeout(3000)

                description_elem = idea_page.query_selector(".tv-chart-view__description, .tv-widget-idea__description")
                description = description_elem.inner_text() if description_elem else ""
                tp, sl = extract_tp_sl(description)

                signals.append((title, full_link, tp, sl))
                idea_page.close()

        browser.close()
        return signals

def job():
    print("🔍 Checking for trading signals...")
    urls = [
        "https://www.tradingview.com/symbols/BTCUSD/ideas/",
        "https://www.tradingview.com/symbols/ETHUSD/ideas/",
        "https://www.tradingview.com/symbols/XAUUSD/ideas/"
    ]
    for url in urls:
        try:
            ideas = get_signals(url)
            for title, link, tp, sl in ideas:
                send_signal(title, link, tp, sl)
        except Exception as e:
            print(f"⚠️ Error at {url}: {e}")

# Run once immediately
job()

# Schedule every 10 minutes
schedule.every(10).minutes.do(job)

print("✅ Bot is running... waiting for new signals.")
while True:
    schedule.run_pending()
    time.sleep(1)
