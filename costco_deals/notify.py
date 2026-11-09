"""組合並送出 Discord Webhook 訊息。"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter

from .common import (
    CH_ONLINE_ONLY,
    CH_SAME_PRICE,
    CH_WAREHOUSE,
    md,
    money,
    pct_text,
    period_text,
    short_url,
)
from .store import FLAG_NEW_LOW

USERNAME = "好市多特價快報"
COLOR_RED = 0xE31837
COLOR_BLUE = 0x005DAA
COLOR_GREEN = 0x16A34A

# Discord 限制：單一 embed 說明 4096 字、單則訊息所有 embed 合計 6000 字
_DESC_LIMIT = 3900
# 商品名稱來自外部資料，一律不觸發 @提及
_NO_MENTIONS = {"parse": []}
_LEGEND = "🌐 網路獨家　🏬 線上賣場同價　🔥 歷史新低"


class NotifyError(RuntimeError):
    """Discord 推播失敗。"""


def _escape(text: str) -> str:
    """跳脫會破壞 Discord Markdown 連結的字元。"""
    text = text.replace("[", "(").replace("]", ")")
    for char in ("\\", "*", "_", "~", "`", "|"):
        text = text.replace(char, "\\" + char)
    return text


def _tags(deal: dict) -> str:
    tags = ""
    if deal["channel"] == CH_ONLINE_ONLY:
        tags += " 🌐"
    elif deal["channel"] == CH_SAME_PRICE:
        tags += " 🏬"
    if deal["flag"] == FLAG_NEW_LOW:
        tags += " 🔥"
    return tags


def deal_line(deal: dict) -> str:
    link = f"[{_escape(deal['name'])}]({short_url(deal['code'])})"
    if deal["channel"] == CH_WAREHOUSE:
        period = period_text(deal["start"], deal["end"])
        return f"{link}・{period}" if period else link
    if deal["price"] is not None and deal["pct"]:
        line = f"**{pct_text(deal['pct'])}** {link} ~~{money(deal['original'])}~~ → **{money(deal['price'])}**"
    else:
        line = f"**折 {money(deal['discount'])}** {link}（多規格）"
    if deal["min_qty"] > 1:
        line += f"（買 {deal['min_qty']} 件）"
    if deal["end"]:
        line += f"・至 {md(deal['end'])}"
    return line + _tags(deal)


def _pack(lines: list[str], limit: int = _DESC_LIMIT) -> str:
    """在字數上限內盡量放入清單，放不下的以筆數帶過。"""
    kept: list[str] = []
    used = 0
    for index, line in enumerate(lines):
        if used + len(line) + 1 > limit:
            kept.append(f"…另有 {len(lines) - index} 項，詳見完整報表")
            break
        kept.append(line)
        used += len(line) + 1
    return "\n".join(kept)


def _by_discount(deals: list[dict]) -> list[dict]:
    return sorted(deals, key=lambda d: (d["pct"] or 0, d["discount"] or 0), reverse=True)


def _summary_embed(new: list[dict], all_deals: list[dict], first_run: bool, report_url: str) -> dict:
    online = [d for d in new if d["channel"] != CH_WAREHOUSE]
    warehouse = [d for d in new if d["channel"] == CH_WAREHOUSE]
    lows = [d for d in new if d["flag"] == FLAG_NEW_LOW]
    verb = "共" if first_run else "新增"

    lines = []
    if online:
        only = sum(d["channel"] == CH_ONLINE_ONLY for d in online)
        same = sum(d["channel"] == CH_SAME_PRICE for d in online)
        lines.append(f"🛍️ **線上特價** {verb} **{len(online)}** 項（網路獨家 {only}、線上賣場同價 {same}）")
    if warehouse:
        lines.append(f"🏬 **賣場特價** {verb} **{len(warehouse)}** 項（官網未公開賣場售價）")
    if lows:
        lines.append(f"🔥 **歷史新低** {len(lows)} 項")
    if not first_run:
        lines.append(f"📦 目前有效特價共 {len(all_deals)} 項")

    periods = Counter((d["start"], d["end"]) for d in new if d["end"])
    if periods:
        top = [f"{period_text(s, e)}（{n} 項）" for (s, e), n in periods.most_common(4)]
        lines.append("📅 檔期：" + "、".join(top))
    if report_url:
        lines.append(f"📄 [開啟完整彙整報表]({report_url})")

    embed = {
        "title": "🛒 好市多特價彙整" if first_run else f"🛒 好市多特價更新｜新增 {len(new)} 項",
        "description": "\n".join(lines),
        "color": COLOR_RED,
    }
    if report_url:
        embed["url"] = report_url
    categories = Counter(d["category"] for d in new).most_common(9)
    if len(categories) > 1:
        embed["fields"] = [
            {"name": name, "value": f"{count} 項", "inline": True} for name, count in categories
        ]
    return embed


def build_messages(
    all_deals: list[dict],
    first_run: bool,
    report_url: str = "",
    top_n: int = 20,
) -> list[dict]:
    """依新上架的特價組出要送出的訊息清單；沒有新特價時回傳空清單。"""
    new = [d for d in all_deals if d["is_new"]]
    if not new:
        return []

    embeds = [_summary_embed(new, all_deals, first_run, report_url)]

    ranked = _by_discount([d for d in new if d["pct"] and d["in_stock"]])[:top_n]
    if ranked:
        embeds.append({
            "title": f"💰 折扣幅度 Top {len(ranked)}",
            "description": _pack([deal_line(d) for d in ranked]),
            "color": COLOR_BLUE,
            "footer": {"text": _LEGEND},
        })

    lows = _by_discount([d for d in new if d["flag"] == FLAG_NEW_LOW])
    if lows:
        lines = [
            f"{deal_line(d)}（前低 {money(d['low_price'])}）" for d in lows
        ]
        embeds.append({
            "title": f"🔥 歷史新低 {len(lows)} 項",
            "description": _pack(lines),
            "color": COLOR_GREEN,
        })

    warehouse = sorted(
        (d for d in new if d["channel"] == CH_WAREHOUSE),
        key=lambda d: (d["category"], d["name"]),
    )
    if warehouse:
        embeds.append({
            "title": f"🏬 賣場特價 {len(warehouse)} 項",
            "description": _pack([deal_line(d) for d in warehouse]),
            "color": COLOR_BLUE,
            "footer": {"text": "賣場獨家商品，官網未公開售價與折扣金額，實際優惠以賣場標示為準"},
        })

    # 每個 embed 各自一則訊息，避免超過單則 6000 字上限
    return [
        {"username": USERNAME, "allowed_mentions": _NO_MENTIONS, "embeds": [embed]}
        for embed in embeds
    ]


def _request(webhook: str, payload: dict, attachment: tuple[str, bytes] | None) -> urllib.request.Request:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"User-Agent": "CostcoDealsBot/1.0"}
    if attachment is None:
        headers["Content-Type"] = "application/json"
    else:
        filename, content = attachment
        boundary = uuid.uuid4().hex
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body = b"".join([
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
            f"Content-Type: application/json\r\n\r\n".encode(),
            body,
            f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; "
            f"filename=\"{filename}\"\r\nContent-Type: text/html; charset=utf-8\r\n\r\n".encode(),
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ])
    separator = "&" if "?" in webhook else "?"
    return urllib.request.Request(f"{webhook}{separator}wait=true", data=body, headers=headers, method="POST")


def _post(webhook: str, payload: dict, attachment: tuple[str, bytes] | None = None) -> None:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(_request(webhook, payload, attachment), timeout=60):
                return
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            if error.code == 429:
                try:
                    wait = float(json.loads(detail).get("retry_after", 2))
                except ValueError:
                    wait = 2.0
                time.sleep(wait + 0.5)
            elif error.code >= 500 and attempt < 4:
                time.sleep(3)
            else:
                raise NotifyError(f"Discord 回應 {error.code}：{detail[:300]}") from None
        except (urllib.error.URLError, OSError) as error:
            if attempt == 4:
                raise NotifyError(f"無法連線到 Discord：{error}") from None
            time.sleep(3)
    raise NotifyError("Discord 推播重試多次仍失敗")


def send(webhook: str, messages: list[dict], attachment: tuple[str, bytes] | None = None) -> None:
    """依序送出訊息；附件（完整報表）附在第一則。"""
    for index, message in enumerate(messages):
        _post(webhook, message, attachment if index == 0 else None)
        time.sleep(0.7)


def send_text(webhook: str, text: str) -> None:
    _post(webhook, {"username": USERNAME, "allowed_mentions": _NO_MENTIONS, "content": text})
