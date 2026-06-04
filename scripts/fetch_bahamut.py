import os
import json
import hashlib
import asyncio
import re
import requests
import gspread
import discord
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter
from google.oauth2.service_account import Credentials
from google_play_scraper import reviews, Sort
from app_store_scraper import AppStore

GAME_NAME = "錫葛尼斯：紅月再臨"

BASE_URL = "https://forum.gamer.com.tw"
BOARD_BSN = "84023"
BOARD_URL = f"https://forum.gamer.com.tw/B.php?bsn={BOARD_BSN}"

GOOGLE_PLAY_APP_ID = "com.hongyue.android"
GOOGLE_PLAY_URL = "https://play.google.com/store/apps/details?id=com.hongyue.android"

APP_STORE_APP_ID = 6756251184
APP_STORE_APP_NAME = "redmoon"
APP_STORE_URL = "https://apps.apple.com/app/id6756251184"

SPREADSHEET_ID = "14Y_HbfXTNYvkbufc5tgys2YGl4msBWASbggllNCfLyQ"
RAW_SHEET_NAME = "raw_data"
REPORT_SHEET_NAME = "weekly_report"
HISTORY_SHEET_NAME = "weekly_history"
SHEET_URL = "https://docs.google.com/spreadsheets/d/14Y_HbfXTNYvkbufc5tgys2YGl4msBWASbggllNCfLyQ/edit"

DISCORD_CHANNELS = {
    "錫葛尼斯議事廳": 1426406162190041114,
    "BUG反應": 1426406163020382225,
    "建議": 1426406163020382226,
    "疑問": 1426406163020382227,
}

DISCORD_FETCH_LIMIT = 100
headers = {"User-Agent": "Mozilla/5.0"}

LOW_VALUE_TOPICS = ["其他", "社群闲聊", "社群互动"]

HIGH_RISK_WORDS = [
    "退坑", "詐騙", "騙", "外掛", "工作室", "封號", "鎖帳",
    "無法登入", "登入失敗", "黑屏", "閃退", "回檔", "當機",
    "卡死", "斷線", "儲值未到", "儲值沒到", "儲值未到账", "沒收到", "退款", "倒閉"
]

NEGATIVE_WORDS = [
    "爛", "差", "卡", "閃退", "登入", "異常", "BUG", "外掛", "工作室",
    "騙", "退坑", "不玩", "無聊", "垃圾", "失望", "不能", "沒辦法",
    "黑屏", "掉線", "延遲", "坑", "貴", "廣告", "封號", "回檔", "當機"
]

POSITIVE_WORDS = [
    "好玩", "不錯", "讚", "佛", "喜歡", "順", "推薦", "懷念", "經典",
    "爽", "好看", "有趣", "刷寶", "懷舊", "打寶", "熱血"
]

STOP_KEYWORDS = [
    "錫葛尼斯", "紅月", "建議", "疑問", "BUG", "反應",
    "Discord", "Google", "Play", "App", "Store"
]

KEYWORDS = [
    "轉生", "裝備", "強化", "掉寶", "打寶", "BOSS",
    "掛機", "離線", "練功", "經驗", "伺服器", "職業", "技能", "PVP", "PK",
    "商城", "課金", "儲值", "月卡", "禮包", "成長基金", "活動", "補償", "獎勵",
    "公會", "攻城", "跨服", "副本", "外掛", "工作室", "閃退", "登入", "黑屏",
    "退坑", "廣告", "封號", "回檔", "更新", "下載", "帳號", "序號", "禮包碼",
    "新手", "教學", "背包", "倉庫", "交易", "自動", "任務", "主線", "客服",
    "公告", "聊天", "頻道", "VIP", "至尊", "金幣", "對話框", "兌換", "坐騎",
    "NPC", "地圖", "稱號", "外觀", "聊天框"
]

RISK_TOPICS = ["BUG/技术问题", "外挂/工作室"]

DEMAND_RULES = {
    "FAQ-至尊VIP获取说明": ["至尊VIP", "至尊 vip", "至尊", "VIP哪裡", "vip哪裡", "儲值多少", "具體儲值"],
    "FAQ-金币/货币用途说明": ["金幣袋", "金幣", "貨幣", "兌換", "為何要賣", "有什麼用"],
    "FAQ-外观/对话框获取说明": ["對話框", "聊天框", "外觀", "造型", "哪裡獲得", "稱號"],
    "FAQ-任务/NPC位置说明": ["任務", "主線", "NPC", "哪裡", "找不到", "怎麼走", "地圖"],
    "FAQ-装备强化说明": ["裝備", "強化", "寶石", "武器", "防具", "戰力"],
    "FAQ-兑换码/礼包说明": ["序號", "禮包碼", "兌換碼", "禮包", "獎勵"],
    "优化储值/商城说明": ["儲值", "商城", "禮包", "月卡", "成長基金", "VIP", "至尊"],
    "增加活动/福利": ["活動", "獎勵", "補償", "福利", "序號", "禮包碼"],
    "优化更新/下载体验": ["更新", "下載", "安裝", "版本"],
    "优化自动挂机": ["自動掛機", "自動", "掛機", "離線掛機"],
    "优化登录/账号体验": ["登入", "帳號", "綁定", "密碼", "驗證"],
    "增加交易/社交功能": ["交易", "拍賣", "公會", "好友", "聊天", "頻道"],
    "增加背包/仓库空间": ["背包", "倉庫", "格子", "空間不夠", "容量"],
    "提高掉宝/爆率": ["掉寶", "爆率", "打寶", "掉落"],
    "优化职业/PVP平衡": ["職業", "技能", "PVP", "PK", "騎士", "法師", "刺客"],
}

PRODUCT_DEMAND_RULES = {
    "增加离线挂机/自动挂机体验": ["離線掛機", "自動掛機", "掛機", "離線"],
    "增加背包/仓库容量": ["背包", "倉庫", "格子", "容量", "空間不夠"],
    "优化掉宝率/打宝体验": ["掉寶", "爆率", "打寶", "掉落"],
    "优化装备强化成本": ["強化", "裝備", "寶石", "戰力"],
    "增加交易/拍卖功能": ["交易", "拍賣", "擺攤"],
    "优化职业/PVP平衡": ["職業", "技能", "PVP", "PK", "騎士", "法師", "刺客"],
    "增加公会/跨服玩法": ["公會", "跨服", "攻城", "團戰"],
    "优化任务引导/NPC定位": ["任務", "主線", "NPC", "找不到", "地圖"],
    "优化商城/VIP说明": ["商城", "VIP", "至尊", "月卡", "禮包", "成長基金"],
    "优化活动奖励与福利": ["活動", "福利", "獎勵", "補償", "禮包碼"],
}

ACTION_RULES = {
    "补充至尊VIP获取与储值门槛说明": ["至尊VIP", "至尊", "儲值多少", "具體儲值"],
    "补充金币袋/兑换道具用途说明": ["金幣袋", "金幣", "兌換", "為何要賣"],
    "补充对话框/外观获取方式FAQ": ["對話框", "聊天框", "外觀", "哪裡獲得", "稱號"],
    "整理常见任务/NPC位置说明": ["任務", "主線", "NPC", "找不到", "哪裡", "地圖"],
    "检查储值不到账问题": ["儲值未到", "儲值沒到", "儲值未到账", "沒收到", "未到帳", "沒到帳"],
    "补充商城/VIP/礼包说明": ["商城", "VIP", "至尊", "月卡", "禮包", "成長基金"],
    "整理更新/下载异常处理公告": ["更新失敗", "無法下載", "下載", "安裝"],
    "整理外挂/工作室处理公告": ["外掛", "工作室", "腳本", "多開"],
    "整理登录/账号异常处理FAQ": ["無法登入", "登入失敗", "帳號", "綁定"],
}

RISK_EVENT_RULES = {
    "外挂/工作室疑似影响游戏公平": {
        "words": ["外掛", "工作室", "腳本", "多開"],
        "level": "高",
        "owner": "安全/运营"
    },
    "登录/账号异常": {
        "words": ["無法登入", "登入失敗", "登不進", "帳號", "綁定"],
        "level": "中",
        "owner": "技术/客服"
    },
    "闪退/黑屏/卡死": {
        "words": ["閃退", "黑屏", "卡死", "當機"],
        "level": "中",
        "owner": "客户端/技术"
    },
    "储值未到账": {
        "words": ["儲值未到", "儲值沒到", "儲值未到账", "未到帳", "沒到帳", "儲值沒收到"],
        "level": "高",
        "owner": "运营/支付/客服"
    },
    "商城/VIP说明争议": {
        "words": ["至尊VIP", "至尊", "VIP", "商城", "月卡", "成長基金", "禮包"],
        "level": "中",
        "owner": "运营/客服"
    },
    "礼包/月卡性价比争议": {
        "words": ["太貴", "性價比", "月卡", "禮包", "課金", "不划算"],
        "level": "中",
        "owner": "运营/商业化"
    },
    "封号/锁号争议": {
        "words": ["封號", "鎖帳", "鎖號"],
        "level": "高",
        "owner": "客服/安全"
    },
    "回档/数据异常": {
        "words": ["回檔", "資料不見", "道具不見"],
        "level": "高",
        "owner": "服务端/技术"
    },
    "退坑/强负面口碑": {
        "words": ["退坑", "不玩", "垃圾", "失望", "太坑"],
        "level": "中",
        "owner": "运营"
    },
}


def strip_prefix(text):
    if not text:
        return ""

    prefixes = [
        "【Discord-錫葛尼斯議事廳】", "【Discord-BUG反應】", "【Discord-建議】", "【Discord-疑問】",
        "【Google Play 1星】", "【Google Play 2星】", "【Google Play 3星】", "【Google Play 4星】", "【Google Play 5星】",
        "【App Store 1星】", "【App Store 2星】", "【App Store 3星】", "【App Store 4星】", "【App Store 5星】",
    ]

    clean = text
    for p in prefixes:
        clean = clean.replace(p, "")

    if "】" in clean and clean.startswith("【"):
        clean = clean.split("】", 1)[-1]

    return clean.strip()


def platform_name(source):
    if source.startswith("Discord"):
        return "Discord"
    if source.startswith("Google Play"):
        return "Google Play 最新100条"
    if source.startswith("App Store"):
        return "App Store 最新100条"
    if source.startswith("Bahamut"):
        return "Bahamut"
    return source or "未知"


def is_valid_voice_text(text):
    clean = strip_prefix(text)

    if len(clean) < 8:
        return False

    if re.fullmatch(r"[0-9\s\W_]+", clean):
        return False

    invalid_short = ["ok", "OK", "好", "嗯", "是", "對", "收到", "謝謝", "感謝"]
    if clean in invalid_short:
        return False

    low_value_starts = ["因為", "所以", "應該是", "我也是", "不是", "對啊", "可以啊", "好像是"]
    if any(clean.startswith(x) for x in low_value_starts):
        return False

    return True


def voice_priority_score(text):
    clean = strip_prefix(text)
    score = 0

    high_words = ["請問", "為什麼", "希望", "建議", "不能", "無法", "沒收到", "閃退", "黑屏", "儲值", "外掛", "退坑", "哪裡", "怎麼"]
    medium_words = ["VIP", "至尊", "商城", "任務", "NPC", "金幣", "裝備", "強化", "活動", "更新"]

    for w in high_words:
        if w in clean:
            score += 5

    for w in medium_words:
        if w in clean:
            score += 2

    if is_high_risk_text(clean):
        score += 10

    topic = classify_topic(clean)
    if topic in ["BUG/技术问题", "商城付费", "玩家建议", "玩家问题", "外挂/工作室"]:
        score += 4

    return score


def classify_topic(text):
    clean_text = strip_prefix(text)

    if any(w in clean_text for w in ["外掛", "工作室", "腳本", "多開"]):
        return "外挂/工作室"
    if any(w in clean_text for w in ["BUG", "異常", "閃退", "黑屏", "無法登入", "登入失敗", "掉線", "延遲", "斷線", "當機", "回檔", "卡死"]):
        return "BUG/技术问题"
    if any(w in clean_text for w in ["登入", "帳號", "綁定", "密碼", "驗證", "登不進", "進不去"]):
        return "登录/账号问题"
    if any(w in clean_text for w in ["更新", "下載", "安裝", "版本", "補丁", "無法下載", "更新失敗"]):
        return "下载/更新问题"
    if any(w in clean_text for w in ["伺服器", "伺服", "排隊", "延遲", "斷線", "爆滿", "卡服"]):
        return "服务器问题"
    if any(w in clean_text for w in ["至尊VIP", "至尊", "VIP", "月卡", "成長基金", "首儲", "商城", "課金", "儲值", "禮包", "廣告"]):
        return "商城付费"
    if any(w in clean_text for w in ["金幣袋", "金幣", "貨幣", "兌換"]):
        return "货币/道具说明"
    if any(w in clean_text for w in ["對話框", "聊天框", "外觀", "造型", "稱號", "坐騎"]):
        return "外观/展示系统"
    if any(w in clean_text for w in ["裝備", "強化", "掉寶", "打寶", "爆率", "寶石", "戰力", "武器", "防具"]):
        return "装备养成"
    if any(w in clean_text for w in ["掛機", "離線", "練功", "經驗", "刷怪", "打怪", "升級", "轉生"]):
        return "挂机成长"
    if any(w in clean_text for w in ["職業", "騎士", "法師", "刺客", "吸血鬼", "角色", "技能", "PVP", "PK"]):
        return "职业战斗"
    if any(w in clean_text for w in ["公會", "攻城", "跨服", "氏族", "團戰", "BOSS", "副本"]):
        return "公会玩法"
    if any(w in clean_text for w in ["活動", "獎勵", "補償", "簽到", "序號", "禮包碼", "兌換碼"]):
        return "活动奖励"
    if any(w in clean_text for w in ["背包", "倉庫", "格子", "交易", "拍賣", "聊天", "頻道", "客服", "公告"]):
        return "功能体验"
    if any(w in clean_text for w in ["攻略", "心得", "教學", "新手", "怎麼玩", "玩法", "主線", "任務", "NPC", "地圖"]):
        return "攻略心得"
    if any(w in clean_text for w in ["建議", "希望", "可以新增", "能不能", "應該", "建議官方", "可不可以"]):
        return "玩家建议"
    if any(w in clean_text for w in ["問題", "請問", "求解", "疑問", "為什麼", "怎麼辦", "哪裡", "多少", "怎麼", "如何"]):
        return "玩家问题"
    if any(w in clean_text for w in ["哈哈", "笑死", "有人", "我也是", "感謝", "謝謝", "收到"]):
        return "社群互动"
    if len(clean_text) <= 10:
        return "社群闲聊"
    return "其他"


def classify_sentiment(text):
    negative_score = sum(1 for w in NEGATIVE_WORDS if w in text)
    positive_score = sum(1 for w in POSITIVE_WORDS if w in text)

    if negative_score > positive_score:
        return "负面"
    if positive_score > negative_score:
        return "正面"
    return "中立"


def is_high_risk_text(text):
    return any(w in text for w in HIGH_RISK_WORDS)


def classify_demand(text):
    clean_text = strip_prefix(text)
    return [d for d, words in DEMAND_RULES.items() if any(w in clean_text for w in words)]


def classify_product_demand(text):
    clean_text = strip_prefix(text)
    return [d for d, words in PRODUCT_DEMAND_RULES.items() if any(w in clean_text for w in words)]


def classify_action_item(text):
    clean_text = strip_prefix(text)
    return [a for a, words in ACTION_RULES.items() if any(w in clean_text for w in words)]


def classify_risk_event(text):
    clean_text = strip_prefix(text)
    matched = []

    for event, info in RISK_EVENT_RULES.items():
        if any(w in clean_text for w in info["words"]):
            matched.append((event, info["level"], info["owner"]))

    return matched


def fetch_bahamut_topics():
    rows = []

    try:
        r = requests.get(BOARD_URL, headers=headers, timeout=20)
        print("Bahamut Status:", r.status_code)

        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()

        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")

            if not text:
                continue

            if f"C.php?bsn={BOARD_BSN}" in href and len(text) >= 6 and "【" in text:
                full_url = BASE_URL + "/" + href.lstrip("/")

                if full_url in seen:
                    continue

                seen.add(full_url)

                rows.append({
                    "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "Bahamut",
                    "topic": classify_topic(text),
                    "sentiment": classify_sentiment(text),
                    "title": text,
                    "url": full_url
                })

    except Exception as e:
        print("Bahamut 抓取失败:", str(e))

    print("Bahamut 抓到数量:", len(rows))
    return rows


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

            title = f"【Google Play {score}星】{content[:120]}"

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
                "title": f"【App Store {rating}星】{combined[:120]}",
                "url": f"{APP_STORE_URL}#review-{review_hash}"
            })

        print("App Store 抓到评论数量:", len(rows))

    except Exception as e:
        print("App Store 抓取失败:", str(e))

    return rows


async def fetch_discord_messages_async():
    token = os.environ.get("DISCORD_TOKEN")
    rows = []

    if not token:
        print("未配置 DISCORD_TOKEN，跳过 Discord 抓取")
        return rows

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Discord Bot 已登录: {client.user}")

        try:
            for channel_name, channel_id in DISCORD_CHANNELS.items():
                channel = client.get_channel(channel_id)

                if channel is None:
                    try:
                        channel = await client.fetch_channel(channel_id)
                    except Exception as e:
                        print(f"Discord频道获取失败 {channel_name}: {e}")
                        continue

                count = 0

                async for msg in channel.history(limit=DISCORD_FETCH_LIMIT):
                    if msg.author.bot:
                        continue

                    content = (msg.content or "").strip()
                    if not content:
                        continue

                    title = f"【Discord-{channel_name}】{content[:180]}"

                    rows.append({
                        "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source": f"Discord-{channel_name}",
                        "topic": classify_topic(content),
                        "sentiment": classify_sentiment(content),
                        "title": title,
                        "url": msg.jump_url
                    })

                    count += 1

                print(f"Discord {channel_name} 抓到消息数量:", count)

        except Exception as e:
            print("Discord 抓取失败:", str(e))

        await client.close()

    try:
        await client.start(token)
    except Exception as e:
        print("Discord Bot 启动失败:", str(e))

    return rows


def fetch_discord_messages():
    return asyncio.run(fetch_discord_messages_async())


def get_client():
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    return gspread.authorize(credentials)


def get_or_create_sheet(workbook, sheet_name):
    try:
        return workbook.worksheet(sheet_name)
    except Exception:
        return workbook.add_worksheet(title=sheet_name, rows=1000, cols=20)


def write_raw_data(sheet, items):
    existing_urls = set()
    existing_rows = sheet.get_all_records()

    for row in existing_rows:
        url = row.get("url")
        if url:
            existing_urls.add(url)

    rows = []
    new_items = []

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
        new_items.append(item)

    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")

    print("本次抓到总数量:", len(items))
    print("去重后新增写入数量:", len(rows))

    return len(rows), new_items


def build_risk_level(risk_rate):
    if risk_rate >= 20:
        return "🔴 高风险"
    if risk_rate >= 8:
        return "🟡 中风险"
    return "🟢 低风险"


def build_counters(records):
    source_counter = Counter()
    topic_counter = Counter()
    sentiment_counter = Counter()
    keyword_counter = Counter()
    demand_counter = Counter()
    product_demand_counter = Counter()
    action_counter = Counter()
    risk_event_counter = Counter()
    risk_event_meta = {}

    for row in records:
        source = row.get("source", "")
        title = row.get("title", "")
        sentiment = row.get("sentiment", "")
        topic = classify_topic(title)

        if source:
            source_counter[source] += 1
        if topic:
            topic_counter[topic] += 1
        if sentiment:
            sentiment_counter[sentiment] += 1

        clean_title = strip_prefix(title)
        for kw in KEYWORDS:
            if kw in clean_title and kw not in STOP_KEYWORDS:
                keyword_counter[kw] += 1

        for demand in classify_demand(title):
            demand_counter[demand] += 1

        for demand in classify_product_demand(title):
            product_demand_counter[demand] += 1

        for action in classify_action_item(title):
            action_counter[action] += 1

        for event, level, owner in classify_risk_event(title):
            risk_event_counter[event] += 1
            risk_event_meta[event] = {"level": level, "owner": owner}

    return (
        source_counter,
        topic_counter,
        sentiment_counter,
        keyword_counter,
        demand_counter,
        product_demand_counter,
        action_counter,
        risk_event_counter,
        risk_event_meta
    )


def build_filtered_topic_counter(topic_counter):
    return Counter({k: v for k, v in topic_counter.items() if k not in LOW_VALUE_TOPICS})


def build_discord_channel_counter(records):
    counter = Counter()

    for row in records:
        source = row.get("source", "")
        if source.startswith("Discord-"):
            channel = source.replace("Discord-", "")
            counter[channel] += 1

    return counter


def build_platform_negative_rate(records):
    total = Counter()
    negative = Counter()

    for row in records:
        p = platform_name(row.get("source", ""))
        sentiment = row.get("sentiment", "")
        total[p] += 1

        if sentiment == "负面" or is_high_risk_text(row.get("title", "")):
            negative[p] += 1

    rows = []
    for p, count in total.most_common():
        neg = negative.get(p, 0)
        rate = round(neg / count * 100, 1) if count else 0
        rows.append((p, count, neg, f"{rate}%"))

    return rows


def get_risk_count_from_records(records):
    return sum(1 for row in records if is_high_risk_text(row.get("title", "")))


def safe_json_loads(text):
    try:
        return json.loads(text) if text else {}
    except Exception:
        return {}


def get_previous_history(history_sheet):
    values = history_sheet.get_all_values()
    if len(values) < 2:
        return None

    headers = values[0]
    last_row = values[-1]
    result = {}

    for i, h in enumerate(headers):
        if h and i < len(last_row):
            result[h] = last_row[i]

    return result or None


def append_history(history_sheet, snapshot):
    existing = history_sheet.get_all_values()

    if not existing:
        history_sheet.append_row([
            "run_time", "total", "new_count", "risk_count", "risk_rate", "risk_level",
            "source_counter", "topic_counter", "sentiment_counter", "keyword_counter",
            "demand_counter", "product_demand_counter", "action_counter", "risk_event_counter"
        ])

    history_sheet.append_row([
        snapshot["run_time"],
        snapshot["total"],
        snapshot["new_count"],
        snapshot["risk_count"],
        snapshot["risk_rate"],
        snapshot["risk_level"],
        json.dumps(snapshot["source_counter"], ensure_ascii=False),
        json.dumps(snapshot["topic_counter"], ensure_ascii=False),
        json.dumps(snapshot["sentiment_counter"], ensure_ascii=False),
        json.dumps(snapshot["keyword_counter"], ensure_ascii=False),
        json.dumps(snapshot["demand_counter"], ensure_ascii=False),
        json.dumps(snapshot["product_demand_counter"], ensure_ascii=False),
        json.dumps(snapshot["action_counter"], ensure_ascii=False),
        json.dumps(snapshot["risk_event_counter"], ensure_ascii=False)
    ], value_input_option="USER_ENTERED")


def build_trend_analysis(current_snapshot, previous_history):
    if not previous_history:
        return ["首次记录历史快照，暂无上期数据可对比。"]

    insights = []

    prev_total = int(previous_history.get("total", 0) or 0)
    curr_total = current_snapshot["total"]

    prev_risk = int(previous_history.get("risk_count", 0) or 0)
    curr_risk = current_snapshot["risk_count"]

    prev_topic = safe_json_loads(previous_history.get("topic_counter", ""))
    curr_topic = current_snapshot["topic_counter"]

    total_diff = curr_total - prev_total
    risk_diff = curr_risk - prev_risk

    if current_snapshot["new_count"] > 0 and current_snapshot["new_count"] >= curr_total * 0.5:
        insights.append("本次新增占比较高，可能包含首次接入或数据回填，不建议直接解读为舆情突然爆发。")
    elif current_snapshot["new_count"] <= 3:
        insights.append(f"本次仅新增 {current_snapshot['new_count']} 条，今日新增舆情较少，整体较平稳。")
    elif total_diff > 0:
        insights.append(f"总舆情数据较上期新增 {total_diff} 条，说明监控池仍在持续累积。")
    elif total_diff == 0:
        insights.append("总舆情数据较上期暂无新增，说明近周期公开讨论热度相对平稳。")
    else:
        insights.append("总舆情数据较上期下降，可能是历史数据被清理或统计口径发生变化。")

    if risk_diff >= 5:
        insights.append(f"真实高风险问题较上期增加 {risk_diff} 条，需关注是否出现集中负面扩散。")
    elif risk_diff > 0:
        insights.append(f"真实高风险问题较上期小幅增加 {risk_diff} 条，建议继续观察。")
    elif risk_diff == 0:
        insights.append("真实高风险问题较上期持平，暂未出现明显恶化。")
    else:
        insights.append(f"真实高风险问题较上期减少 {abs(risk_diff)} 条，舆情风险有所缓和。")

    for topic in [
        "BUG/技术问题", "玩家建议", "玩家问题", "商城付费", "挂机成长",
        "装备养成", "职业战斗", "外挂/工作室", "活动奖励", "公会玩法",
        "登录/账号问题", "下载/更新问题", "服务器问题", "功能体验",
        "攻略心得", "货币/道具说明", "外观/展示系统"
    ]:
        curr_value = curr_topic.get(topic, 0)
        prev_value = int(prev_topic.get(topic, 0) or 0)
        diff = curr_value - prev_value

        if diff >= 5:
            insights.append(f"{topic} 较上期增加 {diff} 条，已成为需要重点关注的变化点。")
        elif diff > 0:
            insights.append(f"{topic} 较上期小幅增加 {diff} 条，可继续观察。")

    if len(insights) <= 2:
        insights.append("主要问题结构相对稳定，暂未出现明显新增风险点。")

    return insights


def build_action_plan(action_counter, risk_event_counter, risk_event_meta, product_demand_counter):
    plan = []

    for event, count in risk_event_counter.most_common(3):
        meta = risk_event_meta.get(event, {})
        level = meta.get("level", "中")
        owner = meta.get("owner", "运营")
        priority = "P0" if level == "高" or count >= 5 else "P1"
        plan.append((priority, event, count, owner, "核查风险并准备公告/客服口径"))

    for action, count in action_counter.most_common(3):
        priority = "P1" if count >= 10 else "P2"
        plan.append((priority, action, count, "运营/客服", "补充FAQ、公告或社群标准回复"))

    for demand, count in product_demand_counter.most_common(3):
        priority = "P1" if count >= 20 else "P2"
        plan.append((priority, demand, count, "产品/策划", "评估是否进入版本需求池"))

    seen = set()
    result = []

    for item in plan:
        key = item[1]
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    result.sort(key=lambda x: (priority_order.get(x[0], 9), -x[2]))

    return result[:8]


def build_operation_suggestions(topic_counter, filtered_topic_counter, demand_counter, product_demand_counter, action_counter, risk_event_counter, risk_count):
    suggestions = []

    if risk_count >= 10:
        suggestions.append("高风险关键词数量偏高，建议优先排查登录、闪退、封号、回档、外挂等集中问题。")

    if risk_event_counter:
        top_event, count = risk_event_counter.most_common(1)[0]
        suggestions.append(f"当前最需要关注的风险事件为「{top_event}」({count}次)，建议确认是否需要客服或公告介入。")

    if action_counter:
        top_action, count = action_counter.most_common(1)[0]
        suggestions.append(f"当前最优先处理事项为「{top_action}」({count}次)，建议今日先补充公告或FAQ说明。")

    if product_demand_counter:
        top_product, count = product_demand_counter.most_common(1)[0]
        suggestions.append(f"产品需求池最高频需求为「{top_product}」({count}次)，建议产品/策划评估优先级。")

    if filtered_topic_counter:
        top_topic, count = filtered_topic_counter.most_common(1)[0]
        suggestions.append(f"有效问题分类中最高频为「{top_topic}」({count}次)，建议作为本期运营关注重点。")

    if topic_counter.get("玩家问题", 0) >= 10:
        suggestions.append("玩家疑问较多，建议客服/社群补充FAQ，降低重复咨询。")

    if topic_counter.get("商城付费", 0) >= 10:
        suggestions.append("商城付费讨论较多，建议区分商城/VIP说明与真实储值不到账问题，避免误判支付风险。")

    if topic_counter.get("功能体验", 0) >= 10:
        suggestions.append("功能体验相关反馈较多，建议关注背包、仓库、交易、聊天频道等基础便利性问题。")

    if demand_counter:
        top_demand, count = demand_counter.most_common(1)[0]
        suggestions.append(f"运营FAQ需求池当前最高频需求为「{top_demand}」({count}次)，建议补充FAQ或公告。")

    if not suggestions:
        suggestions.append("本期风险整体较低，建议继续观察玩家对活动、成长、付费与大型玩法的反馈变化。")

    return suggestions


def build_player_voice(records, limit=5):
    candidates = []

    for row in records:
        title = row.get("title", "")
        source = row.get("source", "")
        url = row.get("url", "")
        topic = classify_topic(title)

        if not is_valid_voice_text(title):
            continue

        score = voice_priority_score(title)
        if score <= 0:
            continue

        candidates.append((score, title, topic, source, url))

    candidates.sort(key=lambda x: x[0], reverse=True)

    selected = []
    seen = set()

    for score, title, topic, source, url in candidates:
        clean = strip_prefix(title)
        if clean in seen:
            continue
        seen.add(clean)
        selected.append((title, topic, source, url))

        if len(selected) >= limit:
            break

    return selected[:limit]


def build_ai_like_summary(
    topic_counter, filtered_topic_counter, keyword_counter, source_counter, discord_counter,
    demand_counter, product_demand_counter, action_counter, risk_event_counter,
    total, new_count, risk_count, risk_level
):
    summaries = []
    top_source = source_counter.most_common(1)[0][0] if source_counter else "未知"

    if new_count <= 3:
        summaries.append(f"本期累计监控到 {total} 条舆情数据，本次仅新增 {new_count} 条，新增舆情较少，当前真实风险判断为 {risk_level}。")
    else:
        summaries.append(f"本期共监控到 {total} 条舆情数据，本次新增 {new_count} 条，主要来源为 {top_source}，当前真实风险判断为 {risk_level}。")

    if sum(discord_counter.values()) > 0:
        summaries.append(f"Discord 已接入监控，本期累计捕捉 {sum(discord_counter.values())} 条社群反馈，可提前发现玩家即时问题。")

    if risk_event_counter:
        event, count = risk_event_counter.most_common(1)[0]
        summaries.append(f"当前最高频风险事件为「{event}」，出现 {count} 次，建议确认是否需要运营或客服介入。")

    if action_counter:
        action, count = action_counter.most_common(1)[0]
        summaries.append(f"当前最明确的可执行事项为「{action}」，出现 {count} 次，建议优先处理。")

    if product_demand_counter:
        demand, count = product_demand_counter.most_common(1)[0]
        summaries.append(f"产品需求池中最高频需求为「{demand}」，出现 {count} 次，建议产品/策划评估。")

    if filtered_topic_counter:
        topic, count = filtered_topic_counter.most_common(1)[0]
        summaries.append(f"剔除闲聊/其他后，本期最高频有效问题为「{topic}」，出现 {count} 次。")

    if demand_counter:
        demand, count = demand_counter.most_common(1)[0]
        summaries.append(f"运营FAQ需求池最高频为「{demand}」，出现 {count} 次，建议补充公告或FAQ。")

    if topic_counter.get("商城付费", 0) >= 10:
        summaries.append("商城付费讨论较多，需区分普通商城/VIP说明争议与真实储值不到账风险。")

    if len(summaries) == 1:
        summaries.append("当前舆情整体平稳，暂未出现明显爆发风险。")

    return summaries


def update_weekly_report(report_sheet, all_records, new_items, trend_insights, current_snapshot):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    (
        source_counter, topic_counter, sentiment_counter, keyword_counter,
        demand_counter, product_demand_counter, action_counter,
        risk_event_counter, risk_event_meta
    ) = build_counters(all_records)

    (
        new_source_counter, new_topic_counter, _, _, _, _, _, _, _
    ) = build_counters(new_items)

    filtered_topic_counter = build_filtered_topic_counter(topic_counter)
    new_filtered_topic_counter = build_filtered_topic_counter(new_topic_counter)

    discord_counter = build_discord_channel_counter(all_records)
    new_discord_counter = build_discord_channel_counter(new_items)
    platform_rows = build_platform_negative_rate(all_records)
    action_plan = build_action_plan(action_counter, risk_event_counter, risk_event_meta, product_demand_counter)

    risk_items = []
    titles = []

    for row in all_records:
        source = row.get("source", "")
        title = row.get("title", "")
        url = row.get("url", "")
        sentiment = row.get("sentiment", "")
        topic = classify_topic(title)

        if is_high_risk_text(title) or topic in RISK_TOPICS:
            risk_items.append((title, topic, source, url))

        if title:
            titles.append((title, topic, sentiment, source, url))

    player_voices = build_player_voice(new_items if new_items else all_records, 5)

    suggestions = build_operation_suggestions(
        topic_counter, filtered_topic_counter, demand_counter, product_demand_counter,
        action_counter, risk_event_counter, current_snapshot["risk_count"]
    )

    ai_summaries = build_ai_like_summary(
        topic_counter, filtered_topic_counter, keyword_counter, source_counter, discord_counter,
        demand_counter, product_demand_counter, action_counter, risk_event_counter,
        len(all_records), current_snapshot["new_count"],
        current_snapshot["risk_count"], current_snapshot["risk_level"]
    )

    report_rows = []

    report_rows.append([f"《{GAME_NAME}》运营级舆情看板 V6.6"])
    report_rows.append(["更新时间", now])
    report_rows.append(["风险等级", current_snapshot["risk_level"]])
    report_rows.append(["总数据量", current_snapshot["total"]])
    report_rows.append(["本次新增", current_snapshot["new_count"]])
    report_rows.append(["真实风险数量", current_snapshot["risk_count"]])
    report_rows.append(["真实风险占比", current_snapshot["risk_rate"]])
    report_rows.append([])

    report_rows.append(["一、AI运营摘要"])
    for i, summary in enumerate(ai_summaries, start=1):
        report_rows.append([f"{i}. {summary}"])

    report_rows.append([])
    report_rows.append(["二、运营行动清单"])
    report_rows.append(["优先级", "事项", "次数", "负责人", "建议动作"])
    for priority, item, count, owner, action in action_plan:
        report_rows.append([priority, item, count, owner, action])

    report_rows.append([])
    report_rows.append(["三、风险事件TOP5"])
    report_rows.append(["风险事件", "风险等级", "次数", "负责人"])
    for event, count in risk_event_counter.most_common(5):
        meta = risk_event_meta.get(event, {})
        report_rows.append([event, meta.get("level", "中"), count, meta.get("owner", "运营")])

    report_rows.append([])
    report_rows.append(["四、平台负面率对比"])
    report_rows.append(["平台", "样本量", "负面/风险数", "负面率", "说明"])
    for p, total, neg, rate in platform_rows:
        note = "商店侧为最新100条样本，非整体评分"
        if p == "Discord":
            note = "官方社群累计监控样本"
        if p == "Bahamut":
            note = "巴哈版面公开帖子样本"
        report_rows.append([p, total, neg, rate, note])

    report_rows.append([])
    report_rows.append(["五、产品需求TOP10"])
    report_rows.append(["产品需求", "出现次数"])
    for demand, count in product_demand_counter.most_common(10):
        report_rows.append([demand, count])

    report_rows.append([])
    report_rows.append(["六、重点可执行事项TOP3"])
    report_rows.append(["事项", "出现次数"])
    for action, count in action_counter.most_common(3):
        report_rows.append([action, count])

    report_rows.append([])
    report_rows.append(["七、本次新增有效问题TOP5"])
    report_rows.append(["分类", "数量"])
    for topic, count in new_filtered_topic_counter.most_common(5):
        report_rows.append([topic, count])

    report_rows.append([])
    report_rows.append(["八、Discord频道分布"])
    report_rows.append(["频道", "累计数量", "本次新增"])
    for channel_name in DISCORD_CHANNELS.keys():
        report_rows.append([channel_name, discord_counter.get(channel_name, 0), new_discord_counter.get(channel_name, 0)])

    report_rows.append([])
    report_rows.append(["九、运营FAQ需求池TOP10"])
    report_rows.append(["需求", "出现次数"])
    for demand, count in demand_counter.most_common(10):
        report_rows.append([demand, count])

    report_rows.append([])
    report_rows.append(["十、趋势变化分析"])
    for i, insight in enumerate(trend_insights, start=1):
        report_rows.append([f"{i}. {insight}"])

    report_rows.append([])
    report_rows.append(["十一、有效问题分类TOP10"])
    report_rows.append(["分类", "数量"])
    for topic, count in filtered_topic_counter.most_common(10):
        report_rows.append([topic, count])

    report_rows.append([])
    report_rows.append(["十二、全部分类分布"])
    report_rows.append(["分类", "数量"])
    for topic, count in topic_counter.most_common():
        report_rows.append([topic, count])

    report_rows.append([])
    report_rows.append(["十三、热门关键词TOP20"])
    report_rows.append(["关键词", "出现次数"])
    for kw, count in keyword_counter.most_common(20):
        report_rows.append([kw, count])

    report_rows.append([])
    report_rows.append(["十四、玩家原声TOP5"])
    report_rows.append(["内容", "分类", "来源", "链接"])
    for title, topic, source, url in player_voices:
        report_rows.append([strip_prefix(title), topic, source, url])

    report_rows.append([])
    report_rows.append(["十五、重点风险反馈TOP20"])
    report_rows.append(["标题/评论", "分类", "来源", "链接"])
    for title, topic, source, url in risk_items[-20:][::-1]:
        report_rows.append([strip_prefix(title), topic, source, url])

    report_rows.append([])
    report_rows.append(["十六、运营建议"])
    for i, suggestion in enumerate(suggestions, start=1):
        report_rows.append([f"{i}. {suggestion}"])

    report_sheet.clear()
    report_sheet.update(report_rows)

    print(f"weekly_report {GAME_NAME} 运营级舆情看板 V6.6 已更新")


def build_feishu_summary(all_records, new_items, trend_insights, current_snapshot):
    (
        source_counter, topic_counter, sentiment_counter, keyword_counter,
        demand_counter, product_demand_counter, action_counter,
        risk_event_counter, risk_event_meta
    ) = build_counters(all_records)

    _, new_topic_counter, _, _, _, _, _, _, _ = build_counters(new_items)

    filtered_topic_counter = build_filtered_topic_counter(topic_counter)
    new_filtered_topic_counter = build_filtered_topic_counter(new_topic_counter)

    discord_counter = build_discord_channel_counter(all_records)
    new_discord_counter = build_discord_channel_counter(new_items)
    platform_rows = build_platform_negative_rate(all_records)
    action_plan = build_action_plan(action_counter, risk_event_counter, risk_event_meta, product_demand_counter)

    suggestions = build_operation_suggestions(
        topic_counter, filtered_topic_counter, demand_counter, product_demand_counter,
        action_counter, risk_event_counter, current_snapshot["risk_count"]
    )

    ai_summaries = build_ai_like_summary(
        topic_counter, filtered_topic_counter, keyword_counter, source_counter, discord_counter,
        demand_counter, product_demand_counter, action_counter, risk_event_counter,
        len(all_records), current_snapshot["new_count"],
        current_snapshot["risk_count"], current_snapshot["risk_level"]
    )

    player_voices = build_player_voice(new_items if new_items else all_records, 5)

    ai_summary_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(ai_summaries)])
    action_plan_text = "\n".join([f"- {p}｜{item}｜{count}次｜{owner}" for p, item, count, owner, _ in action_plan[:5]]) or "- 暂无明确行动项"

    risk_event_text = "\n".join([
        f"- {event}：{count}次｜{risk_event_meta.get(event, {}).get('level', '中')}｜{risk_event_meta.get(event, {}).get('owner', '运营')}"
        for event, count in risk_event_counter.most_common(5)
    ]) or "- 暂无明显风险事件"

    platform_text = "\n".join([f"- {p}：{rate}（{neg}/{total}，商店侧为最新100条样本）" for p, total, neg, rate in platform_rows])
    product_demand_text = "\n".join([f"- {k}：{v}" for k, v in product_demand_counter.most_common(10)]) or "- 暂无明显产品需求"
    action_text = "\n".join([f"- {k}：{v}" for k, v in action_counter.most_common(3)]) or "- 暂无明确可执行事项"

    new_topic_text = "\n".join([f"- {k}：{v}" for k, v in new_filtered_topic_counter.most_common(5)]) or "- 本次暂无新增有效问题"

    discord_text = "\n".join([
        f"- {name}：累计 {discord_counter.get(name, 0)} / 新增 {new_discord_counter.get(name, 0)}"
        for name in DISCORD_CHANNELS.keys()
    ])

    demand_text = "\n".join([f"- {k}：{v}" for k, v in demand_counter.most_common(10)]) or "- 暂无明显高频需求"
    trend_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(trend_insights[:5])])
    topic_text = "\n".join([f"- {k}：{v}" for k, v in filtered_topic_counter.most_common(5)])
    keyword_text = "\n".join([f"- {k}：{v}" for k, v in keyword_counter.most_common(10)])
    suggestion_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(suggestions)])

    voice_text = "\n".join([
        f"{i+1}. [{source}] {strip_prefix(title)[:80]}"
        for i, (title, topic, source, url) in enumerate(player_voices)
    ]) or "暂无"

    return {
        "total": current_snapshot["total"],
        "new_count": current_snapshot["new_count"],
        "risk_count": current_snapshot["risk_count"],
        "risk_rate": current_snapshot["risk_rate"],
        "risk_level": current_snapshot["risk_level"],
        "ai_summary_text": ai_summary_text,
        "action_plan_text": action_plan_text,
        "risk_event_text": risk_event_text,
        "platform_text": platform_text,
        "product_demand_text": product_demand_text,
        "action_text": action_text,
        "new_topic_text": new_topic_text,
        "discord_text": discord_text,
        "demand_text": demand_text,
        "trend_text": trend_text,
        "topic_text": topic_text,
        "keyword_text": keyword_text,
        "suggestion_text": suggestion_text,
        "voice_text": voice_text
    }


def send_feishu_message(summary):
    webhook = os.environ.get("FEISHU_WEBHOOK")

    if not webhook:
        print("未配置 FEISHU_WEBHOOK，跳过飞书推送")
        return

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"《{GAME_NAME}》舆情监控周报 V6.6"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"**风险等级：** {summary['risk_level']}\n"
                    f"**总数据量：** {summary['total']}\n"
                    f"**本次新增：** {summary['new_count']}\n"
                    f"**真实风险数量：** {summary['risk_count']}\n"
                    f"**真实风险占比：** {summary['risk_rate']}"
                )}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**一、AI运营摘要**\n{summary['ai_summary_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**二、运营行动清单**\n{summary['action_plan_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**三、风险事件TOP5**\n{summary['risk_event_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**四、平台负面率对比**\n{summary['platform_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**五、产品需求TOP10**\n{summary['product_demand_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**六、重点可执行事项TOP3**\n{summary['action_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**七、本次新增有效问题TOP5**\n{summary['new_topic_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**八、Discord频道分布**\n{summary['discord_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**九、运营FAQ需求池TOP10**\n{summary['demand_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**十、玩家原声TOP5**\n{summary['voice_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**十一、趋势变化分析**\n{summary['trend_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**十二、有效问题TOP5**\n{summary['topic_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**十三、热门关键词TOP10**\n{summary['keyword_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**十四、运营建议**\n{summary['suggestion_text']}"}},
                {"tag": "action", "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看完整舆情看板"},
                    "url": SHEET_URL,
                    "type": "primary"
                }]}
            ]
        }
    }

    try:
        response = requests.post(webhook, json=card, timeout=20)
        print("飞书推送状态:", response.status_code)
        print(response.text)
    except Exception as e:
        print("飞书推送失败:", str(e))


if __name__ == "__main__":
    bahamut_items = fetch_bahamut_topics()
    google_play_items = fetch_google_play_reviews()
    app_store_items = fetch_app_store_reviews()
    discord_items = fetch_discord_messages()

    all_items = bahamut_items + google_play_items + app_store_items + discord_items

    client = get_client()
    workbook = client.open_by_key(SPREADSHEET_ID)

    raw_sheet = workbook.worksheet(RAW_SHEET_NAME)
    report_sheet = workbook.worksheet(REPORT_SHEET_NAME)
    history_sheet = get_or_create_sheet(workbook, HISTORY_SHEET_NAME)

    new_count, new_items = write_raw_data(raw_sheet, all_items)

    all_records = raw_sheet.get_all_records()

    (
        source_counter, topic_counter, sentiment_counter, keyword_counter,
        demand_counter, product_demand_counter, action_counter,
        risk_event_counter, risk_event_meta
    ) = build_counters(all_records)

    risk_count = get_risk_count_from_records(all_records)
    total = len(all_records)
    risk_rate_num = round(risk_count / total * 100, 1) if total else 0
    risk_rate = f"{risk_rate_num}%"
    risk_level = build_risk_level(risk_rate_num)

    current_snapshot = {
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "new_count": new_count,
        "risk_count": risk_count,
        "risk_rate": risk_rate,
        "risk_level": risk_level,
        "source_counter": dict(source_counter),
        "topic_counter": dict(topic_counter),
        "sentiment_counter": dict(sentiment_counter),
        "keyword_counter": dict(keyword_counter),
        "demand_counter": dict(demand_counter),
        "product_demand_counter": dict(product_demand_counter),
        "action_counter": dict(action_counter),
        "risk_event_counter": dict(risk_event_counter)
    }

    previous_history = get_previous_history(history_sheet)
    trend_insights = build_trend_analysis(current_snapshot, previous_history)

    update_weekly_report(report_sheet, all_records, new_items, trend_insights, current_snapshot)

    append_history(history_sheet, current_snapshot)

    feishu_summary = build_feishu_summary(all_records, new_items, trend_insights, current_snapshot)
    send_feishu_message(feishu_summary)
