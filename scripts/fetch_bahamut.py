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

NEGATIVE_WORDS = [
    "爛", "差", "卡", "閃退", "登入", "異常", "BUG", "外掛", "工作室",
    "課金", "儲值", "騙", "退坑", "不玩", "無聊", "垃圾", "失望",
    "不能", "沒辦法", "黑屏", "掉線", "延遲", "坑", "貴"
]

POSITIVE_WORDS = [
    "好玩", "不錯", "讚", "佛", "喜歡", "順", "推薦", "懷念", "經典",
    "爽", "好看", "有趣"
]

KEYWORDS = [
    "外掛", "工作室", "閃退", "登入", "卡", "BUG", "課金", "儲值",
    "禮包", "商城", "活動", "補償", "獎勵", "職業", "正派", "邪派",
    "掛機", "離線", "經驗", "伺服器", "黑屏", "退坑", "爆率"
]

def classify_topic(text):
    if any(w in text for w in ["BUG", "異常", "閃退", "卡", "黑屏", "登入", "掉線", "延遲"]):
        return "BUG/技术问题"
    if any(w in text for w in ["課金", "儲值", "商城", "禮包", "錢", "貴"]):
        return "付费问题"
    if any(w in text for w in ["職業", "正派", "邪派"]):
        return "职业/门派"
    if any(w in text for w in ["活動", "獎勵", "補償"]):
        return "活动反馈"
    if any(w in text for w in ["外掛", "工作室"]):
        return "外挂/工作室"
    if any(w in text for w in ["攻略", "心得"]):
        return "攻略心得"
    if any(w in text for w in ["問題", "請問"]):
        return "玩家问题"
    return "其他"

def classify_sentiment(text):
    negative_score = sum(1 for w in NEGATIVE_WORDS if w in text)
    positive_score = sum(1 for w in POSITIVE_WORDS if w in text)

    if negative_score > positive_score:
        return "负面"
    if positive_score > negative_score:
        return "正面"
    return "中立"

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
                "sentiment": classify_sentiment(text),
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

            title = f"【Google Play {score}星】{content[:80]}"

            if score <= 2:
                sentiment = "负面"
            elif score >= 4:
                sentiment = "正面"
            else:
                sentiment = classify_sentiment(content)

            rows.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Google Play",
                "topic": classify_topic(content),
                "sentiment": sentiment,
                "title": title,
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

            if rating <= 2:
                sentiment = "负面"
            elif rating >= 4:
                sentiment = "正面"
            else:
                sentiment = classify_sentiment(combined)

            rows.append({
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "App Store",
                "topic": classify_topic(combined),
                "sentiment": sentiment,
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
            item["url"],
            item["sentiment"]
        ])

    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")

    print("本次抓到总数量:", len(items))
    print("去重后新增写入数量:", len(rows))

def update_weekly_report(report_sheet, all_records):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    source_counter = Counter()
    topic_counter = Counter()
    sentiment_counter = Counter()
    keyword_counter = Counter()

    negative_items = []
    titles = []

    for row in all_records:
        source = row.get("source", "")
        topic = row.get("topic", "")
        title = row.get("title", "")
        url = row.get("url", "")
        sentiment = row.get("sentiment", "")

        if source:
            source_counter[source] += 1
        if topic:
            topic_counter[topic] += 1
        if sentiment:
            sentiment_counter[sentiment] += 1

        for kw in KEYWORDS:
            if kw in title:
                keyword_counter[kw] += 1

        if sentiment == "负面" or topic in ["BUG/技术问题", "付费问题", "外挂/工作室"]:
            negative_items.append((title, topic, source, url))

        if title:
            titles.append((title, topic, sentiment, source, url))

    total = len(all_records)
    negative_count = sentiment_counter.get("负面", 0)
    negative_rate = f"{round(negative_count / total * 100, 1)}%" if total else "0%"

    report_rows = []

    report_rows.append(["《新熱血江湖：世界》舆情分析看板"])
    report_rows.append(["更新时间", now])
    report_rows.append(["总数据量", total])
    report_rows.append(["负面数量", negative_count])
    report_rows.append(["负面占比", negative_rate])
    report_rows.append([])

    report_rows.append(["一、来源分布"])
    report_rows.append(["来源", "数量"])
    for source, count in source_counter.most_common():
        report_rows.append([source, count])

    report_rows.append([])
    report_rows.append(["二、情绪分布"])
    report_rows.append(["情绪", "数量"])
    for sentiment, count in sentiment_counter.most_common():
        report_rows.append([sentiment, count])

    report_rows.append([])
    report_rows.append(["三、分类分布"])
    report_rows.append(["分类", "数量"])
    for topic, count in topic_counter.most_common():
        report_rows.append([topic, count])

    report_rows.append([])
    report_rows.append(["四、热门关键词TOP20"])
    report_rows.append(["关键词", "出现次数"])
    for kw, count in keyword_counter.most_common(20):
        report_rows.append([kw, count])

    report_rows.append([])
    report_rows.append(["五、负面反馈TOP20"])
    report_rows.append(["标题/评论", "分类", "来源", "链接"])
    for title, topic, source, url in negative_items[-20:][::-1]:
        report_rows.append([title, topic, source, url])

    report_rows.append([])
    report_rows.append(["六、最新内容TOP20"])
    report_rows.append(["标题/评论", "分类", "情绪", "来源", "链接"])
    for title, topic, sentiment, source, url in titles[-20:][::-1]:
        report_rows.append([title, topic, sentiment, source, url])

    report_sheet.clear()
    report_sheet.update(report_rows)

    print("weekly_report 舆情看板已更新")

if __name__ == "__main__":
    bahamut_items = fetch_bahamut_topics()
    google_play_items = fetch_google_play_reviews()
    app_store_items = fetch_app_store_reviews()

    all_items = bahamut_items + google_play_items + app_store_items

    for item in all_items[:10]:
        print(item["source"], item["title"], item["topic"], item["sentiment"])

    client = get_client()
    workbook = client.open_by_key(SPREADSHEET_ID)

    raw_sheet = workbook.worksheet(RAW_SHEET_NAME)
    report_sheet = workbook.worksheet(REPORT_SHEET_NAME)

    write_raw_data(raw_sheet, all_items)

    all_records = raw_sheet.get_all_records()
    update_weekly_report(report_sheet, all_records)
