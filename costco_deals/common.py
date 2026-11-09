"""共用常數與格式化工具。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

SITE = "https://www.costco.com.tw"

# 台灣無日光節約時間，固定 UTC+8（避免 Windows 缺少 tzdata 的問題）
TW = timezone(timedelta(hours=8), "Asia/Taipei")

# 販售通路
CH_ONLINE = "online"            # 線上特價
CH_ONLINE_ONLY = "online_only"  # 網路獨家
CH_SAME_PRICE = "same_price"    # 線上賣場同價
CH_WAREHOUSE = "warehouse"      # 賣場特價（現場）

CHANNEL_LABELS = {
    CH_ONLINE: "線上特價",
    CH_ONLINE_ONLY: "網路獨家",
    CH_SAME_PRICE: "線上賣場同價",
    CH_WAREHOUSE: "賣場特價",
}


def now_tw() -> datetime:
    return datetime.now(TW)


def parse_iso(value: str | None) -> datetime | None:
    """將 API 的 UTC 時間字串轉為台灣時間。"""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TW)


def md(value: str | None) -> str:
    """月/日，例如 11/22。"""
    dt = parse_iso(value)
    return f"{dt.month}/{dt.day}" if dt else ""


def period_text(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{md(start)}–{md(end)}"
    if end:
        return f"至 {md(end)}"
    if start:
        return f"{md(start)} 起"
    return ""


def money(value: float | None) -> str:
    return "" if value is None else f"${value:,.0f}"


def pct_text(pct: float) -> str:
    """折扣百分比（四捨五入到整數），例如 -25%。"""
    return f"-{int(pct + 0.5)}%"


def short_url(code: str) -> str:
    """官網短網址，會自動轉址到完整商品頁。"""
    return f"{SITE}/p/{code}"
