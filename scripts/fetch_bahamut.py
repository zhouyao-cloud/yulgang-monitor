import os
import json
import hashlib
import requests
import gspread
from bs4 import BeautifulSoup
from datetime import datetime
from google.oauth2.service_account import Credentials
from google_play_scraper import reviews, Sort
from app_store_scraper import AppStore

BASE_URL = "https://forum.gamer.com.tw"
BOARD_URL = "https://forum.gamer.com.tw/B.php?bsn=84232"

GOOGLE_PLAY_APP_ID = "com.mover.twrxjhw"
GOOGLE_PLAY_URL = "https://play.google.com/store/apps/details?id=com.mover.twrxjhw"

APP_STORE_APP_ID = 6756000886
APP_STORE_APP_NAME = "新熱血江湖-世界"
APP_STORE_URL = "https://apps.apple.com/app/id6756000886"

SPREADSHEET_ID = "14Y_HbfXTNYvkbufc5tgys2YGl4msBWASbggllNCfLyQ"
SHEET_NAME = "raw_data"

headers = {
    "User-Agent": "Mozilla/5.0"
}

def classify_topic(text):
    if "BUG" in text or "異常" in text or "閃退" in text or "卡" in text or "黑屏" in text or "登入" in text:
        return "BUG/技术问题"
    if "課金" in text or "儲值" in text or "商城" in text or "禮包" in text or "錢" in text:
        return "付费问题"
    if "職業" in text or "正派" in text or "邪派" in text:
        return "职业/门派"
    if "活動" in text or "獎勵" in text or "補償" in text:
        return "活动反馈"
    if "外掛" in text or "工作室" in text:
        return "外挂/工作室"
    if "攻略" in text or "心得" in text:
        return "攻略心得"
    if "問題" in text or "請問" in text:
        return "玩家问题"
    return "其他"

def fetch_bahamut_topics():
    r = requests.get(BOARD_URL, headers=headers)
    print("Bahamut Status:", r.status_code)

    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.find_all("a")

    topics = []

    for link in links:
        text = link.get_text(strip=True)
        href = link.get("href", "")

        if not text:
            continue

        if (
            "C.php?bsn=84232" in href
            and len(text) >= 6
            and "【" in text
        ):
            full_url = BASE_URL + "/" + href.lstrip("/")

            topics.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Bahamut",
                "topic": classify_topic(text),
                "title": text,
                "url": full_url
            })

    unique_topics = []
    seen = set()

    for topic in topics:
        if topic["url"] not in seen:
            unique_topics.append(topic)
            seen.add(topic["url"])

    return unique_topics

def fetch_google_play_reviews():
    gp_rows = []

    try:
        result, _ = reviews(
            GOOGLE_PLAY_APP_ID,
            lang="zh_TW",
            country="tw",
            sort=Sort.NEWEST,
            count=100
        )

        for item in result:
            content = item.get("content", "")
            score = item.get("score", "")
            review_id = item.get("reviewId", "")

            if not content:
                continue

            title = f"【Google Play {score}星】{content[:80]}"
            unique_url = f"{GOOGLE_PLAY_URL}#review-{review_id}"

            gp_rows.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Google Play",
                "topic": classify_topic(content),
                "title": title,
                "url": unique_url
            })

        print("Google Play 抓到评论数量:", len(gp_rows))

    except Exception as e:
        print("Google Play 抓取失败:", str(e))

    return gp_rows

def fetch_app_store_reviews():
    app_rows = []

    try:
        app = AppStore(
            country="tw",
            app_name=APP_STORE_APP_NAME,
            app_id=APP_STORE_APP_ID
        )

        app.review(how_many=100)

        for item in app.reviews:
            content = item.get("review", "")
            rating = item.get("rating", "")
            title_text = item.get("title", "")
            date_text = str(item.get("date", ""))

            if not content and not title_text:
                continue

            raw_key = f"{title_text}_{content}_{rating}_{date_text}"
            review_hash = hashlib.md5(raw_key.encode("utf-8")).hexdigest()

            combined_text = f"{title_text} {content}".strip()
            title = f"【App Store {rating}星】{combined_text[:80]}"
            unique_url = f"{APP_STORE_URL}#review-{review_hash}"

            app_rows.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "App Store",
                "topic": classify_topic(combined_text),
                "title": title,
                "url": unique_url
            })

        print("App Store 抓到评论数量:", len(app_rows))

    except Exception as e:
        print("App Store 抓取失败:", str(e))

    return app_rows

def write_to_sheet(items):
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes
    )

    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    existing_urls = set()
    existing_rows = sheet.get_all_records()

    for row in existing_rows:
        url = row.get("url")
        if url:
            existing_urls.add(url)

    rows = []

    for item in items:
        if item["url"] in existing_urls:
            continue

        rows.append([
            item["collect_time"],
            item["source"],
            item["topic"],
            item["title"],
            item["url"]
        ])

    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")

    print("本次抓到总数量:", len(items))
    print("去重后新增写入数量:", len(rows))

if __name__ == "__main__":
    bahamut_items = fetch_bahamut_topics()
    google_play_items = fetch_google_play_reviews()
    app_store_items = fetch_app_store_reviews()

    all_items = bahamut_items + google_play_items + app_store_items

    for item in all_items[:10]:
        print(item["source"], item["title"], item["topic"])

    write_to_sheet(all_items)
