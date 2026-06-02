import requests
import re

url = "https://forum.gamer.com.tw/B.php?bsn=84232"

headers = {
    "User-Agent": "Mozilla/5.0"
}

r = requests.get(url, headers=headers)

print("Status:", r.status_code)

html = r.text

# 测试抓取标题
titles = re.findall(r'data-gtm-forum-list-title="([^"]+)"', html)

print("标题数量:", len(titles))

for t in titles[:20]:
    print(t)
