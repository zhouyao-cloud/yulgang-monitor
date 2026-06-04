import os
import json
import hashlib
import asyncio
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

HIGH_RISK_WORDS = [
    "退坑", "詐騙", "騙", "外掛", "工作室", "封號", "鎖帳",
    "無法登入", "登入失敗", "黑屏", "閃退", "回檔", "當機",
    "卡死", "斷線", "儲值未到", "沒收到", "退款", "倒閉"
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

KEYWORDS = [
    "紅月", "錫葛尼斯", "轉生", "裝備", "強化", "掉寶", "打寶", "BOSS",
    "掛機", "離線", "練功", "經驗", "伺服器", "職業", "技能", "PVP", "PK",
    "商城", "課金", "儲值", "月卡", "禮包", "成長基金", "活動", "補償", "獎勵",
    "公會", "攻城", "跨服", "副本", "外掛", "工作室", "閃退", "登入", "黑屏",
    "BUG", "退坑", "廣告", "封號", "回檔", "疑問", "建議", "更新", "下載",
    "帳號", "序號", "禮包碼", "新手", "教學"
]

RISK_TOPICS = ["BUG/技术问题", "外挂/工作室"]


def strip_prefix(text):
    if "】" in text:
        return text.split("】", 1)[-1]
    return text


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

    if any(w in clean_text for w in ["商城", "課金", "儲值", "禮包", "月卡", "成長基金", "首儲", "廣告"]):
        return "商城付费"

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

    if any(w in clean_text for w in ["攻略", "心得", "教學", "新手", "怎麼玩", "玩法"]):
        return "攻略心得"

    if any(w in clean_text for w in ["問題", "請問", "求解", "疑問", "為什麼", "怎麼辦"]):
        return "玩家问题"

    if any(w in clean_text for w in ["建議", "希望", "可以新增", "能不能", "應該", "建議官方"]):
        return "玩家建议"

    if len(clean_text) <= 8:
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


def build_operation_suggestions(topic_counter, risk_count):
    suggestions = []

    if risk_count >= 10:
        suggestions.append("高风险关键词数量偏高，建议优先排查登录、闪退、封号、回档、外挂等集中问题。")

    if topic_counter.get("BUG/技术问题", 0) >= 10:
        suggestions.append("BUG/技术问题数量较高，建议按登录、闪退、黑屏、更新失败等二级问题拆分给研发排查。")

    if topic_counter.get("玩家建议", 0) >= 10:
        suggestions.append("Discord/社群建议较多，建议整理高频需求，形成版本优化池。")

    if topic_counter.get("玩家问题", 0) >= 10:
        suggestions.append("玩家疑问较多，建议客服/社群补充FAQ，降低重复咨询。")

    if topic_counter.get("商城付费", 0) >= 10:
        suggestions.append("商城付费讨论较多，建议检查礼包、月卡、成长基金与储值流程体验。")

    if topic_counter.get("挂机成长", 0) >= 10:
        suggestions.append("挂机成长讨论较高，建议关注离线收益、练功效率与玩家日常负担。")

    if topic_counter.get("装备养成", 0) >= 10:
        suggestions.append("装备养成讨论较多，建议关注强化成本、掉宝体验与战力追赶压力。")

    if topic_counter.get("外挂/工作室", 0) >= 1:
        suggestions.append("出现外挂/工作室相关反馈，建议持续监控是否影响打宝、公平性与玩家留存。")

    if not suggestions:
        suggestions.append("本期风险整体较低，建议继续观察玩家对活动、成长、付费与大型玩法的反馈变化。")

    return suggestions


def build_counters(records):
    source_counter = Counter()
    topic_counter = Counter()
    sentiment_counter = Counter()
    keyword_counter = Counter()

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

        for kw in KEYWORDS:
            if kw in title:
                keyword_counter[kw] += 1

    return source_counter, topic_counter, sentiment_counter, keyword_counter


def build_discord_channel_counter(records):
    counter = Counter()

    for row in records:
        source = row.get("source", "")
        if source.startswith("Discord-"):
            channel = source.replace("Discord-", "")
            counter[channel] += 1

    return counter


def get_risk_count_from_records(records):
    count = 0
    for row in records:
        title = row.get("title", "")
        if is_high_risk_text(title):
            count += 1
    return count


def safe_json_loads(text):
    try:
        return json.loads(text) if text else {}
    except Exception:
        return {}


def get_previous_history(history_sheet):
    rows = history_sheet.get_all_records()

    if not rows:
        return None

    return rows[-1]


def append_history(history_sheet, snapshot):
    existing = history_sheet.get_all_values()

    if not existing:
        history_sheet.append_row([
            "run_time",
            "total",
            "new_count",
            "risk_count",
            "risk_rate",
            "risk_level",
            "source_counter",
            "topic_counter",
            "sentiment_counter",
            "keyword_counter"
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
        json.dumps(snapshot["keyword_counter"], ensure_ascii=False)
    ], value_input_option="USER_ENTERED")


def build_trend_analysis(current_snapshot, previous_history):
    if not previous_history:
        return ["首次记录历史快照，暂无上期数据可对比。"]

    insights = []

    prev_total = int(previous_history.get("total", 0) or 0)
    curr_total = current_snapshot["total"]

    prev_risk = int(previous_history.get("risk_count", previous_history.get("risk_negative_count", 0)) or 0)
    curr_risk = current_snapshot["risk_count"]

    prev_topic = safe_json_loads(previous_history.get("topic_counter", ""))
    curr_topic = current_snapshot["topic_counter"]

    total_diff = curr_total - prev_total
    risk_diff = curr_risk - prev_risk

    if total_diff > 0:
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
        "登录/账号问题", "下载/更新问题", "服务器问题"
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


def build_player_voice(records, limit=5):
    selected = []

    priority_topics = ["BUG/技术问题", "玩家建议", "玩家问题", "商城付费", "外挂/工作室"]

    for row in reversed(records):
        title = row.get("title", "")
        source = row.get("source", "")
        url = row.get("url", "")
        topic = classify_topic(title)

        if not title:
            continue

        if topic in priority_topics or is_high_risk_text(title):
            selected.append((title, topic, source, url))

        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for row in reversed(records):
            title = row.get("title", "")
            source = row.get("source", "")
            url = row.get("url", "")
            topic = classify_topic(title)

            if not title:
                continue

            item = (title, topic, source, url)
            if item not in selected:
                selected.append(item)

            if len(selected) >= limit:
                break

    return selected[:limit]


def build_ai_like_summary(topic_counter, keyword_counter, sentiment_counter, source_counter, discord_counter, total, new_count, risk_count, risk_level):
    summaries = []

    top_source = source_counter.most_common(1)[0][0] if source_counter else "未知"

    summaries.append(
        f"本期共监控到 {total} 条舆情数据，本次新增 {new_count} 条，主要来源为 {top_source}，当前真实风险判断为 {risk_level}。"
    )

    if sum(discord_counter.values()) > 0:
        summaries.append(
            f"Discord 已接入监控，本期累计捕捉 {sum(discord_counter.values())} 条社群反馈，可提前发现玩家即时问题。"
        )

    if topic_counter.get("BUG/技术问题", 0) >= 10:
        summaries.append("BUG/技术问题数量较高，建议重点查看 Discord BUG反應 与 Google Play 差评内容，拆分登录、闪退、黑屏、更新失败等子问题。")

    if topic_counter.get("玩家建议", 0) >= 10:
        summaries.append("玩家建议数量较高，说明社群中存在较明确的版本优化诉求，建议整理进入需求池。")

    if topic_counter.get("玩家问题", 0) >= 10:
        summaries.append("玩家疑问较多，建议补充FAQ、公告说明与社群机器人回复，降低客服重复答疑压力。")

    if topic_counter.get("商城付费", 0) >= 10:
        summaries.append("商城付费相关讨论较多，但不应全部视为负面风险，建议区分正常付费讨论与储值异常、价格争议。")

    if topic_counter.get("挂机成长", 0) >= 10:
        summaries.append("挂机成长讨论较高，说明玩家对练功速度、离线收益和日常负担较敏感。")

    if topic_counter.get("外挂/工作室", 0) >= 1:
        summaries.append("外挂或工作室相关反馈已出现，建议提前建立舆情监控与官方回应预案。")

    if len(summaries) == 1:
        summaries.append("当前舆情整体平稳，暂未出现明显爆发风险。")

    return summaries


def update_weekly_report(report_sheet, all_records, new_items, trend_insights, current_snapshot):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    source_counter, topic_counter, sentiment_counter, keyword_counter = build_counters(all_records)
    new_source_counter, new_topic_counter, new_sentiment_counter, new_keyword_counter = build_counters(new_items)
    discord_counter = build_discord_channel_counter(all_records)
    new_discord_counter = build_discord_channel_counter(new_items)

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

    total = len(all_records)
    risk_count = current_snapshot["risk_count"]
    risk_rate = current_snapshot["risk_rate"]
    risk_level = current_snapshot["risk_level"]

    suggestions = build_operation_suggestions(topic_counter, risk_count)
    ai_summaries = build_ai_like_summary(
        topic_counter,
        keyword_counter,
        sentiment_counter,
        source_counter,
        discord_counter,
        total,
        current_snapshot["new_count"],
        risk_count,
        risk_level
    )

    report_rows = []

    report_rows.append([f"《{GAME_NAME}》运营级舆情看板 V6.1"])
    report_rows.append(["更新时间", now])
    report_rows.append(["风险等级", risk_level])
    report_rows.append(["总数据量", total])
    report_rows.append(["本次新增", current_snapshot["new_count"]])
    report_rows.append(["真实风险数量", risk_count])
    report_rows.append(["真实风险占比", risk_rate])
    report_rows.append([])

    report_rows.append(["一、AI运营摘要"])
    for i, summary in enumerate(ai_summaries, start=1):
        report_rows.append([f"{i}. {summary}"])

    report_rows.append([])
    report_rows.append(["二、本次新增分析"])
    report_rows.append(["新增来源", "数量"])
    for source, count in new_source_counter.most_common():
        report_rows.append([source, count])
    report_rows.append(["新增分类", "数量"])
    for topic, count in new_topic_counter.most_common():
        report_rows.append([topic, count])

    report_rows.append([])
    report_rows.append(["三、Discord频道分布"])
    report_rows.append(["频道", "累计数量", "本次新增"])
    for channel_name in DISCORD_CHANNELS.keys():
        report_rows.append([
            channel_name,
            discord_counter.get(channel_name, 0),
            new_discord_counter.get(channel_name, 0)
        ])

    report_rows.append([])
    report_rows.append(["四、趋势变化分析"])
    for i, insight in enumerate(trend_insights, start=1):
        report_rows.append([f"{i}. {insight}"])

    report_rows.append([])
    report_rows.append(["五、来源分布"])
    report_rows.append(["来源", "数量"])
    for source, count in source_counter.most_common():
        report_rows.append([source, count])

    report_rows.append([])
    report_rows.append(["六、情绪分布"])
    report_rows.append(["情绪", "数量"])
    for sentiment, count in sentiment_counter.most_common():
        report_rows.append([sentiment, count])

    report_rows.append([])
    report_rows.append(["七、分类分布"])
    report_rows.append(["分类", "数量"])
    for topic, count in topic_counter.most_common():
        report_rows.append([topic, count])

    report_rows.append([])
    report_rows.append(["八、热门关键词TOP20"])
    report_rows.append(["关键词", "出现次数"])
    for kw, count in keyword_counter.most_common(20):
        report_rows.append([kw, count])

    report_rows.append([])
    report_rows.append(["九、玩家原声TOP5"])
    report_rows.append(["内容", "分类", "来源", "链接"])
    for title, topic, source, url in player_voices:
        report_rows.append([title, topic, source, url])

    report_rows.append([])
    report_rows.append(["十、重点风险反馈TOP20"])
    report_rows.append(["标题/评论", "分类", "来源", "链接"])
    for title, topic, source, url in risk_items[-20:][::-1]:
        report_rows.append([title, topic, source, url])

    report_rows.append([])
    report_rows.append(["十一、运营建议"])
    for i, suggestion in enumerate(suggestions, start=1):
        report_rows.append([f"{i}. {suggestion}"])

    report_rows.append([])
    report_rows.append(["十二、最新内容TOP20"])
    report_rows.append(["标题/评论", "分类", "情绪", "来源", "链接"])
    for title, topic, sentiment, source, url in titles[-20:][::-1]:
        report_rows.append([title, topic, sentiment, source, url])

    report_sheet.clear()
    report_sheet.update(report_rows)

    print(f"weekly_report {GAME_NAME} 运营级舆情看板 V6.1 已更新")


def build_feishu_summary(all_records, new_items, trend_insights, current_snapshot):
    source_counter, topic_counter, sentiment_counter, keyword_counter = build_counters(all_records)
    new_source_counter, new_topic_counter, _, _ = build_counters(new_items)
    discord_counter = build_discord_channel_counter(all_records)
    new_discord_counter = build_discord_channel_counter(new_items)

    suggestions = build_operation_suggestions(topic_counter, current_snapshot["risk_count"])

    ai_summaries = build_ai_like_summary(
        topic_counter,
        keyword_counter,
        sentiment_counter,
        source_counter,
        discord_counter,
        len(all_records),
        current_snapshot["new_count"],
        current_snapshot["risk_count"],
        current_snapshot["risk_level"]
    )

    player_voices = build_player_voice(new_items if new_items else all_records, 5)

    topic_text = "\n".join([f"- {k}：{v}" for k, v in topic_counter.most_common(5)])
    new_topic_text = "\n".join([f"- {k}：{v}" for k, v in new_topic_counter.most_common(5)]) or "- 本次暂无新增分类"
    keyword_text = "\n".join([f"- {k}：{v}" for k, v in keyword_counter.most_common(10)])
    suggestion_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(suggestions)])
    ai_summary_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(ai_summaries)])
    trend_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(trend_insights[:5])])

    discord_text = "\n".join([
        f"- {name}：累计 {discord_counter.get(name, 0)} / 新增 {new_discord_counter.get(name, 0)}"
        for name in DISCORD_CHANNELS.keys()
    ])

    voice_text = "\n".join([
        f"{i+1}. [{source}] {title[:80]}"
        for i, (title, topic, source, url) in enumerate(player_voices)
    ]) or "暂无"

    return {
        "total": current_snapshot["total"],
        "new_count": current_snapshot["new_count"],
        "risk_count": current_snapshot["risk_count"],
        "risk_rate": current_snapshot["risk_rate"],
        "risk_level": current_snapshot["risk_level"],
        "topic_text": topic_text,
        "new_topic_text": new_topic_text,
        "keyword_text": keyword_text,
        "suggestion_text": suggestion_text,
        "ai_summary_text": ai_summary_text,
        "trend_text": trend_text,
        "discord_text": discord_text,
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
                "title": {
                    "tag": "plain_text",
                    "content": f"《{GAME_NAME}》舆情监控周报 V6.1"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**风险等级：** {summary['risk_level']}\n"
                            f"**总数据量：** {summary['total']}\n"
                            f"**本次新增：** {summary['new_count']}\n"
                            f"**真实风险数量：** {summary['risk_count']}\n"
                            f"**真实风险占比：** {summary['risk_rate']}"
                        )
                    }
                },
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**一、AI运营摘要**\n{summary['ai_summary_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**二、本次新增问题TOP5**\n{summary['new_topic_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**三、Discord频道分布**\n{summary['discord_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**四、玩家原声TOP5**\n{summary['voice_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**五、趋势变化分析**\n{summary['trend_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**六、主要问题TOP5**\n{summary['topic_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**七、热门关键词TOP10**\n{summary['keyword_text']}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**八、运营建议**\n{summary['suggestion_text']}"}},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看完整舆情看板"},
                            "url": SHEET_URL,
                            "type": "primary"
                        }
                    ]
                }
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

    for item in all_items[:10]:
        print(item["source"], item["title"], item["topic"], item["sentiment"])

    client = get_client()
    workbook = client.open_by_key(SPREADSHEET_ID)

    raw_sheet = workbook.worksheet(RAW_SHEET_NAME)
    report_sheet = workbook.worksheet(REPORT_SHEET_NAME)
    history_sheet = get_or_create_sheet(workbook, HISTORY_SHEET_NAME)

    new_count, new_items = write_raw_data(raw_sheet, all_items)

    all_records = raw_sheet.get_all_records()

    source_counter, topic_counter, sentiment_counter, keyword_counter = build_counters(all_records)

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
        "keyword_counter": dict(keyword_counter)
    }

    previous_history = get_previous_history(history_sheet)
    trend_insights = build_trend_analysis(current_snapshot, previous_history)

    update_weekly_report(report_sheet, all_records, new_items, trend_insights, current_snapshot)

    append_history(history_sheet, current_snapshot)

    feishu_summary = build_feishu_summary(all_records, new_items, trend_insights, current_snapshot)
    send_feishu_message(feishu_summary)
