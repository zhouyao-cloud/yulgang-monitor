import requests
from bs4 import BeautifulSoup

url = "https://forum.gamer.com.tw/B.php?bsn=84232"

headers = {
    "User-Agent": "Mozilla/5.0"
}

r = requests.get(url, headers=headers)

print("Status:", r.status_code)

soup = BeautifulSoup(r.text, "html.parser")

# 先测试所有a标签
links = soup.find_all("a")

print("链接数量:", len(links))

for link in links[:50]:
    text = link.get_text(strip=True)

    if text:
        print(text)
