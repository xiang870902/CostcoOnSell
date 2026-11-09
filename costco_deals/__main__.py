"""主流程：擷取 → 比對 → 產生報表 → 推播 → 儲存狀態。

用法：
    python -m costco_deals              正式執行（推播並更新 data/、docs/）
    python -m costco_deals --dry-run    只預覽，不推播也不寫入狀態（輸出到 out/）
    python -m costco_deals --test-push  送出一則測試訊息確認 Webhook 可用
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

from . import notify, store
from .common import CH_WAREHOUSE, now_tw
from .fetcher import FetchError, fetch_all
from .report import TEMPLATE_VERSION, build_report

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.toml"
STATE_FILE = ROOT / "data" / "state.json"
HISTORY_FILE = ROOT / "data" / "history.json"
REPORT_FILE = ROOT / "docs" / "index.html"
PREVIEW_DIR = ROOT / "out"

DEFAULTS = {"top_n": 20, "attach_report": True}


def load_config() -> dict:
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as file:
            config.update(tomllib.load(file))
    return config


def load_dotenv() -> None:
    """本機執行時從 .env 讀取環境變數（已存在的環境變數優先）。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="costco_deals", description="好市多特價彙整與 Discord 推播")
    parser.add_argument("--dry-run", action="store_true", help="只預覽：不推播、不寫入狀態，結果輸出到 out/")
    parser.add_argument("--test-push", action="store_true", help="送出一則測試訊息後結束")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    load_dotenv()
    config = load_config()
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    report_url = os.environ.get("REPORT_URL", "").strip()

    if args.test_push:
        if not webhook:
            print("錯誤：尚未設定 DISCORD_WEBHOOK_URL", file=sys.stderr)
            return 2
        notify.send_text(webhook, "✅ 好市多特價快報：Webhook 連線測試成功")
        print("測試訊息已送出")
        return 0

    if not args.dry_run and not webhook:
        print("錯誤：尚未設定 DISCORD_WEBHOOK_URL（可先用 --dry-run 預覽）", file=sys.stderr)
        return 2

    now = now_tw()
    try:
        deals, warnings = fetch_all()
    except FetchError as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"警告：{warning}", file=sys.stderr)

    state = store.load_json(STATE_FILE, {})
    history = store.load_json(HISTORY_FILE, {})
    first_run = store.mark_new(deals, state)
    store.apply_history(deals, history, now.strftime("%Y-%m-%d"))

    new = [d for d in deals if d["is_new"]]
    warehouse = sum(d["channel"] == CH_WAREHOUSE for d in deals)
    print(f"目前特價 {len(deals)} 項（線上 {len(deals) - warehouse}、賣場 {warehouse}）")
    print(f"新上架 {len(new)} 項、歷史新低 {sum(d['flag'] == store.FLAG_NEW_LOW for d in new)} 項")

    report_html = build_report(deals, now)
    messages = notify.build_messages(deals, first_run, report_url, config["top_n"])

    if args.dry_run:
        PREVIEW_DIR.mkdir(exist_ok=True)
        (PREVIEW_DIR / "report.html").write_text(report_html, encoding="utf-8", newline="\n")
        (PREVIEW_DIR / "messages.json").write_text(
            json.dumps(messages, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
        print(f"預覽模式：將送出 {len(messages)} 則訊息，內容已輸出到 {PREVIEW_DIR}")
        return 0

    if messages:
        attachment = None
        if config["attach_report"]:
            attachment = (f"costco-deals-{now:%Y%m%d}.html", report_html.encode("utf-8"))
        try:
            notify.send(webhook, messages, attachment)
        except notify.NotifyError as error:
            # 推播失敗時不儲存狀態，下次執行會重新通知
            print(f"錯誤：{error}", file=sys.stderr)
            return 1
        print(f"已推播 {len(messages)} 則訊息")
    else:
        print("沒有新上架的特價，不推播")

    digest = f"{store.fingerprint(deals)}:{TEMPLATE_VERSION}"
    if digest != state.get("fingerprint") or not REPORT_FILE.exists():
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(report_html, encoding="utf-8", newline="\n")
        state["fingerprint"] = digest
        state["updated"] = now.isoformat(timespec="seconds")
        store.update_seen(deals, state, now)
        store.save_state(STATE_FILE, state)
        store.save_history(HISTORY_FILE, history)
        print("已更新報表與狀態")
    return 0


if __name__ == "__main__":
    sys.exit(main())
