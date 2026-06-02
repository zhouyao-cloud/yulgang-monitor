import os
import json
import hashlib
import requests
import gspread
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter
from google.oauth2.service_account import Credentials
from google_play_scraper import reviews, Sort
from app_store_scraper import AppStore

BASE_URL = "https://forum.gamer.com.tw"
BOARD_URL = "https://forum.gamer.com.tw/B.php?bsn=84232"

GOOGLE_PLAY_APP_ID = "com.mover.twrxjhw"
GOOGLE_PLAY_URL = "https://play.google.com/store/apps/details?id=com.mover.twrxjhw"

APP_STORE_APP_ID = 6756000886
APP_STORE_APP_NAME = "yulgang-world"
APP_STORE_URL = "https://apps.apple.com/app/id6756000886"

SPREADSHEET_ID = "14Y_HbfXTNYvkbufc5tgys2YGl4msBWASbggllNCfLyQ"
RAW_SHEET_NAME = "raw_data"
REPORT_SHEET_NAME = "weekly_report"

headers = {"User-Agent": "Mozilla/5.0"}

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
    topics = []
    seen = set()

    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")

        if not text:
            continue

        if "C.php?bsn=84232" in href and len(text) >= 6 and "【" in text:
            full_url = BASE_URL + "/" + href.lstrip("/")

            if full_url in seen:
                continue

            seen.add(full_url)

            topics.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Bahamut",
                "topic": classify_topic(text),
                "title": text,
                "url": full_url
            })

    return topics

def fetch_google_play_reviews():
    rows = []

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

            rows.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Google Play",
                "topic": classify_topic(content),
                "title": f"【Google Play {score}星】{content[:80]}",
                "url": f"{GOOGLE_PLAY_URL}#review-{review_id}"
            })

        print("Google Play 抓到评论数量:", len(rows))

    except Exception as e:
        print("Google Play 抓取失败:", str(e))

    return rows

def fetch_app_store_reviews():
    rows = []

    try:
        app = AppStore(country="tw", app_name=APP_STORE_APP_NAME, app_id=APP_STORE_APP_ID)
        app.review(how_many=100)

        for item in app.reviews:
            content = item.get("review", "")
            rating = item.get("rating", "")
            title_text = item.get("title", "")
            date_text = str(item.get("date", ""))

            if not content and not title_text:
                continue

            combined = f"{title_text} {content}".strip()
            review_hash = hashlib.md5(f"{combined}_{rating}_{date_text}".encode("utf-8")).hexdigest()

            rows.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "App Store",
                "topic": classify_topic(combined),
                "title": f"【App Store {rating}星】{combined[:80]}",
                "url": f"{APP_STORE_URL}#review-{review_hash}"
            })

        print("App Store 抓到评论数量:", len(rows))

    except Exception as e:
        print("App Store 抓取失败:", str(e))

    return rows

def get_client():
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    return gspread.authorize(credentials)

def write_raw_data(sheet, items):
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

    return len(rows)

def update_weekly_report(report_sheet, all_records):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    source_counter = Counter()
    topic_counter = Counter()

    titles = []

    for row in all_records:
        source = row.get("source", "")
        topic = row.get("topic", "")
        title = row.get("title", "")
        url = row.get("url", "")

        if source:
            source_counter[source] += 1

        if topic:
            topic_counter[topic] += 1

        if title:
            titles.append((title, topic, source, url))

    report_rows = []

    report_rows.append(["更新时间", now])
    report_rows.append(["总数据量", len(all_records)])
    report_rows.append([])
    report_rows.append(["一、来源分布"])
    report_rows.append(["来源", "数量"])

    for source, count in source_counter.most_common():
        report_rows.append([source, count])

    report_rows.append([])
    report_rows.append(["二、分类分布"])
    report_rows.append(["分类", "数量"])

    for topic, count in topic_counter.most_common():
        report_rows.append([topic, count])

    report_rows.append([])
    report_rows.append(["三、最新内容TOP20"])
    report_rows.append(["标题/评论", "分类", "来源", "链接"])

    for title, topic, source, url in titles[-20:][::-1]:
        report_rows.append([title, topic, source, url])

    report_sheet.clear()
    report_sheet.update(report_rows)

    print("weekly_report 已更新")

if __name__ == "__main__":
    bahamut_items = fetch_bahamut_topics()
    google_play_items = fetch_google_play_reviews()
    app_store_items = fetch_app_store_reviews()

    all_items = bahamut_items + google_play_items + app_store_items

    for item in all_items[:10]:
        print(item["source"], item["title"], item["topic"])

    client = get_client()
    workbook = client.open_by_key(SPREADSHEET_ID)

    raw_sheet = workbook.worksheet(RAW_SHEET_NAME)
    report_sheet = workbook.worksheet(REPORT_SHEET_NAME)

    write_raw_data(raw_sheet, all_items)

    all_records = raw_sheet.get_all_records()
    update_weekly_report(report_sheet, all_records)
