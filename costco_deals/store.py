"""狀態與價格歷史的讀寫，以及「新上架」「歷史低價」的判斷。

data/state.json   已通知過的特價（商品＋檔期＋價格），用來判斷哪些是新上架。
data/history.json 每項商品歷次特價的價格紀錄，用來標記歷史低價。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from .common import parse_iso

FLAG_NEW_LOW = "new_low"  # 低於過去所有紀錄
FLAG_TIE_LOW = "tie_low"  # 與過去最低價相同

# 檔期結束後仍保留紀錄的天數，避免商品暫時下架又上架時重複通知
_KEEP_DAYS = 3


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(state, file, ensure_ascii=False, indent=1, sort_keys=True)
        file.write("\n")


def save_history(path: Path, history: dict) -> None:
    """一項商品一行，讓 git 差異容易閱讀。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{json.dumps(code)}: {json.dumps(entry, ensure_ascii=False, separators=(',', ':'))}"
        for code, entry in sorted(history.items())
    ]
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("{\n" + ",\n".join(lines) + "\n}\n")


def _number(value: float):
    return int(value) if float(value).is_integer() else value


def deal_key(deal: dict) -> str:
    """同一商品換檔期或改價，都視為新的特價。"""
    price = "" if deal["price"] is None else _number(deal["price"])
    return f"{deal['code']}|{deal['start'] or ''}|{price}"


def mark_new(deals: list[dict], state: dict) -> bool:
    """標記每筆特價是否為新上架。回傳是否為首次執行（尚無任何紀錄）。"""
    seen = state.get("seen")
    for deal in deals:
        deal["is_new"] = seen is None or deal_key(deal) not in seen
    return seen is None


def update_seen(deals: list[dict], state: dict, now: datetime) -> None:
    active = {deal_key(d): d["end"] or "" for d in deals}
    cutoff = now - timedelta(days=_KEEP_DAYS)
    kept = {
        key: end
        for key, end in (state.get("seen") or {}).items()
        if key not in active and end and parse_iso(end) >= cutoff
    }
    kept.update(active)
    state["seen"] = kept


def apply_history(deals: list[dict], history: dict, today: str) -> None:
    """更新價格歷史，並在每筆特價上標記歷史低價資訊。

    紀錄格式：[首次看到的日期, 特價, 原價, 檔期起始日, 標記]
    """
    for deal in deals:
        deal["flag"] = ""
        deal["low_price"] = None
        deal["low_date"] = ""
        if deal["price"] is None:
            continue
        price = _number(deal["price"])
        period = (deal["start"] or "")[:10]
        entry = history.setdefault(deal["code"], {"n": deal["name"], "o": []})
        entry["n"] = deal["name"]
        records = entry["o"]

        if records and records[-1][1] == price and records[-1][3] == period:
            previous = records[:-1]
            flag = records[-1][4]
        else:
            previous = list(records)
            flag = ""
            if previous:
                lowest = min(r[1] for r in previous)
                if price < lowest:
                    flag = FLAG_NEW_LOW
                elif price == lowest:
                    flag = FLAG_TIE_LOW
            original = None if deal["original"] is None else _number(deal["original"])
            records.append([today, price, original, period, flag])

        deal["flag"] = flag
        if previous:
            low = min(previous, key=lambda r: r[1])
            deal["low_price"], deal["low_date"] = low[1], low[0]


def fingerprint(deals: list[dict]) -> str:
    """目前特價內容的摘要，用來判斷報表是否需要重新產生。"""
    rows = sorted(
        (d["code"], d["price"], d["start"], d["end"], d["in_stock"], d["flag"], d["channel"])
        for d in deals
    )
    return hashlib.sha1(json.dumps(rows).encode("utf-8")).hexdigest()
