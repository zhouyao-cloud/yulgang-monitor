import requests

url = "https://forum.gamer.com.tw/B.php?bsn=84232"

headers = {
    "User-Agent": "Mozilla/5.0"
}

r = requests.get(url, headers=headers)

print("Status:", r.status_code)
print(r.text[:500])
