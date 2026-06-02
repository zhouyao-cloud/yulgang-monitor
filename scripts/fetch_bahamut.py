import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://forum.gamer.com.tw"
BOARD_URL = "https://forum.gamer.com.tw/B.php?bsn=84232"

headers = {
    "User-Agent": "Mozilla/5.0"
}

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

    if "C.php?bsn=84232" in href and len(text) >= 6:
        full_url = BASE_URL + "/" + href.lstrip("/")

        topics.append({
            "source": "Bahamut",
            "title": text,
            "url": full_url,
            "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

# 去重
unique_topics = []
seen = set()

for topic in topics:
    if topic["url"] not in seen:
        unique_topics.append(topic)
        seen.add(topic["url"])

print("抓到帖子数量:", len(unique_topics))

for topic in unique_topics[:30]:
    print("标题:", topic["title"])
    print("链接:", topic["url"])
    print("---")
