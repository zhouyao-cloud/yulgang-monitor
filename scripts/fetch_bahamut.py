import os
import json
import requests
import gspread
from bs4 import BeautifulSoup
from datetime import datetime
from google.oauth2.service_account import Credentials

BASE_URL = "https://forum.gamer.com.tw"
BOARD_URL = "https://forum.gamer.com.tw/B.php?bsn=84232"
SPREADSHEET_ID = "14Y_HbfXTNYvkbufc5tgys2YGl4msBWASbggllNCfLyQ"
SHEET_NAME = "raw_data"

headers = {
    "User-Agent": "Mozilla/5.0"
}

def classify_topic(title):
    if "BUG" in title or "異常" in title or "閃退" in title or "卡" in title:
        return "BUG/技术问题"
    if "課金" in title or "儲值" in title or "商城" in title or "禮包" in title:
        return "付费问题"
    if "職業" in title or "正派" in title or "邪派":
        return "职业/门派"
    if "活動" in title or "獎勵" in title or "補償" in title:
        return "活动反馈"
    if "外掛" in title or "工作室" in title:
        return "外挂/工作室"
    if "攻略" in title or "心得" in title:
        return "攻略心得"
    if "問題" in title or "請問" in title:
        return "玩家问题"
    return "其他"

def fetch_bahamut_topics():
    r = requests.get(BOARD_URL, headers=headers)
    print("Status:", r.status_code)

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

def write_to_sheet(topics):
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets"
    ]

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes
    )

    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    rows = []

    for item in topics:
        rows.append([
            item["collect_time"],
            item["source"],
            item["topic"],
            item["title"],
            item["url"]
        ])

    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")

    print("写入Google Sheet数量:", len(rows))

if __name__ == "__main__":
    topics = fetch_bahamut_topics()
    print("抓到帖子数量:", len(topics))

    for topic in topics[:10]:
        print(topic["title"], topic["topic"])

    write_to_sheet(topics)
