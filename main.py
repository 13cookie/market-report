# -*- coding: utf-8 -*-
"""
每日市場晨報:幣圈(BTC/ETH)+ 台股大盤
流程:抓行情與新聞 -> Claude API 分析 -> LINE 官方帳號推送
※ 本報告為 AI 自動彙整之市場觀察,僅供參考,不構成投資建議。
"""

import os
import sys
import time
import json
import requests
import feedparser
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TW_TZ)

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
LINE_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

CLAUDE_MODEL = "claude-sonnet-4-6"

# ---------- 新聞來源(RSS)----------
# 想換來源直接改這裡即可;任何一個來源掛掉都會自動略過,不影響其他來源。
CRYPTO_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "動區 BlockTempo": "https://www.blocktempo.com/feed/",
    "Google News 加密貨幣": (
        "https://news.google.com/rss/search?"
        "q=%E6%AF%94%E7%89%B9%E5%B9%A3%20OR%20%E4%BB%A5%E5%A4%AA%E5%9D%8A"
        "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ),
}
TAIWAN_FEEDS = {
    "Google News 台股": (
        "https://news.google.com/rss/search?"
        "q=%E5%8F%B0%E8%82%A1%20OR%20%E5%8A%A0%E6%AC%8A%E6%8C%87%E6%95%B8"
        "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ),
    "Google News 總經": (
        "https://news.google.com/rss/search?"
        "q=%E8%81%AF%E6%BA%96%E6%9C%83%20OR%20%E7%BE%8E%E8%82%A1%20OR%20%E9%80%9A%E8%86%A8"
        "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ),
}

MAX_ITEMS_PER_FEED = 6
RECENT_HOURS = 36  # 只取最近 36 小時內的文章


def fetch_feed(name, url):
    """抓單一 RSS 來源,失敗回傳空清單。"""
    items = []
    try:
        parsed = feedparser.parse(url)
        cutoff = NOW - timedelta(hours=RECENT_HOURS)
        for entry in parsed.entries[:20]:
            published = None
            for key in ("published_parsed", "updated_parsed"):
                if getattr(entry, key, None):
                    published = datetime.fromtimestamp(
                        time.mktime(getattr(entry, key)), tz=timezone.utc
                    ).astimezone(TW_TZ)
                    break
            if published and published < cutoff:
                continue
            title = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "")
            # 粗略去除 HTML 標籤並截斷,避免 prompt 過長
            summary = (
                requests.utils.re.sub(r"<[^>]+>", "", summary).strip()[:150]
            )
            if title:
                items.append(f"- [{name}] {title}" + (f":{summary}" if summary else ""))
            if len(items) >= MAX_ITEMS_PER_FEED:
                break
    except Exception as e:
        print(f"[warn] feed 失敗 {name}: {e}", file=sys.stderr)
    return items


def fetch_crypto_prices():
    """CoinGecko:BTC/ETH 現價與漲跌幅(免金鑰)。"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": "bitcoin,ethereum",
                "price_change_percentage": "24h,7d",
            },
            timeout=20,
        )
        r.raise_for_status()
        lines = []
        for c in r.json():
            lines.append(
                "{sym}: ${price:,.0f} | 24h {d1:+.2f}% | 7d {d7:+.2f}%".format(
                    sym=c["symbol"].upper(),
                    price=c["current_price"],
                    d1=c.get("price_change_percentage_24h_in_currency") or 0,
                    d7=c.get("price_change_percentage_7d_in_currency") or 0,
                )
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"[warn] CoinGecko 失敗: {e}", file=sys.stderr)
        return "(行情抓取失敗)"


def fetch_taiex():
    """台灣證交所 OpenAPI:加權指數最近一個交易日收盤。"""
    try:
        r = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK", timeout=20
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return "(無資料)"
        last = data[-1]
        return "加權指數(最近交易日 {d}):收盤 {i},漲跌 {c},成交金額 {v} 元".format(
            d=last.get("Date", "?"),
            i=last.get("TAIEX", "?"),
            c=last.get("Change", "?"),
            v=last.get("TradeValue", "?"),
        )
    except Exception as e:
        print(f"[warn] TWSE 失敗: {e}", file=sys.stderr)
        return "(台股行情抓取失敗)"


def collect_news(feeds):
    items = []
    for name, url in feeds.items():
        items.extend(fetch_feed(name, url))
    return "\n".join(items) if items else "(今日無可用新聞來源)"


def analyze_with_claude(crypto_prices, taiex, crypto_news, tw_news):
    is_weekend = NOW.weekday() >= 5  # 週六=5、週日=6
    weekend_note = "今天是週末,台股休市,台股部分請以上一交易日與展望為主。" if is_weekend else ""

    prompt = f"""你是專業的市場分析師。以下是 {NOW:%Y-%m-%d}(台灣時間)早晨蒐集的市場資料,請撰寫一份「每日市場晨報」。

【幣圈行情】
{crypto_prices}

【台股行情】
{taiex}

【幣圈新聞(最近 36 小時)】
{crypto_news}

【台股/總經新聞(最近 36 小時)】
{tw_news}

撰寫要求:
1. 全部使用繁體中文,總長度嚴格控制在 500 字以內(這會透過 LINE 傳送)。
2. 結構:先「幣圈」(BTC/ETH 為主)再「台股大盤與總經」,各含:當前局勢重點 2-3 點、未來走向觀察 1-2 點。
3. 用純文字排版(可用 emoji 與「▌」「•」符號),不要用 Markdown 語法(不要 # 和 **)。
4. 開頭第一行為:📊 {NOW:%m/%d} 市場晨報
5. 最後一行加上:⚠️ AI 自動彙整,僅供參考,非投資建議
6. {weekend_note}
7. 直接輸出報告內容,不要任何前言或說明。"""

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text").strip()


def push_line(text):
    # LINE 單則文字訊息上限 5000 字元,保險起見截到 4900
    text = text[:4900]
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"LINE 推送失敗 {r.status_code}: {r.text}")


def main():
    print("抓取行情…")
    crypto_prices = fetch_crypto_prices()
    taiex = fetch_taiex()
    print("抓取新聞…")
    crypto_news = collect_news(CRYPTO_FEEDS)
    tw_news = collect_news(TAIWAN_FEEDS)
    print("Claude 分析中…")
    report = analyze_with_claude(crypto_prices, taiex, crypto_news, tw_news)
    print("推送 LINE…")
    push_line(report)
    print("完成 ✅")
    print("----- 報告內容 -----")
    print(report)


if __name__ == "__main__":
    main()
