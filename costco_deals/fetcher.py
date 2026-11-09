"""從好市多台灣官網的公開搜尋介面擷取特價商品。

資料來源：
- 線上特價：「優惠商品」分類（hot-buys），含原價、特價、折扣金額與期間。
- 賣場特價：「賣場獨家商品」分類（WH*）中帶有優惠期間者。
  官網不公開賣場售價，因此只有品名與優惠期間。
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .common import (
    CH_ONLINE,
    CH_ONLINE_ONLY,
    CH_SAME_PRICE,
    CH_WAREHOUSE,
    SITE,
)

API = f"{SITE}/rest/v2/taiwan/products/search"
PAGE_SIZE = 100
PAUSE_SECONDS = 0.4

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept-Encoding": "gzip",
}

_FIELDS = (
    "products(code,name,englishName,url,price(value),basePrice(value),"
    "couponDiscount(discountValue,discountStartDate,discountEndDate,minQtyDiscount),"
    "images(format,url),averageRating,numberOfReviews,stock(stockLevelStatus),decalData),"
    "pagination(FULL)"
)

# 線上商品網址第一段 → 分類名稱
_CATEGORY_NAMES = {
    "Food-Dining": "食品飲料",
    "Health-Beauty": "保健美容",
    "Household-Baby-Toys": "日用、婦幼、玩具",
    "Furniture-Kitchen": "家具、寢具、餐廚",
    "Clothing-Accessories": "服飾配件",
    "Televisions-Appliances": "電視、家電",
    "Digital-Mobile": "3C 數位",
    "Sports-Lifestyle": "運動休閒",
    "Jewelry-Gold": "珠寶黃金",
    "Office-School": "辦公文具",
    "Business-Delivery": "商業配送",
    "Lawn-Garden": "戶外園藝",
}
_OTHER = "其他"


class FetchError(RuntimeError):
    """資料擷取失敗（網路錯誤、被阻擋或回傳內容異常）。"""


def _get_json(params: dict, retries: int = 4) -> dict:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as error:
            last_error = error
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
    raise FetchError(f"無法取得好市多資料（{params.get('category')}）：{last_error}")


def _search(category: str) -> list[dict]:
    """取回指定分類的全部商品（自動翻頁）。"""
    products: dict[str, dict] = {}
    page, total_pages, total = 0, 1, 0
    while page < total_pages:
        data = _get_json({
            "category": category,
            "currentPage": page,
            "pageSize": PAGE_SIZE,
            "lang": "zh_TW",
            "curr": "TWD",
            "fields": _FIELDS,
        })
        pagination = data.get("pagination") or {}
        total_pages = pagination.get("totalPages", 0)
        total = pagination.get("totalResults", 0)
        for product in data.get("products") or []:
            products[product["code"]] = product
        page += 1
        if page < total_pages:
            time.sleep(PAUSE_SECONDS)
    if total and len(products) < total * 0.9:
        raise FetchError(f"分類 {category} 資料不完整：應有 {total} 筆，僅取得 {len(products)} 筆")
    return list(products.values())


def _decals(product: dict) -> set[str]:
    names = set()
    for decal in product.get("decalData") or []:
        url = (decal.get("value") or {}).get("url") or ""
        if url:
            names.add(url.rsplit("/", 1)[-1])
    return names


def _image(product: dict) -> str:
    images = product.get("images") or []
    for wanted in ("product", "results", "thumbnail"):
        for image in images:
            if image.get("format") == wanted and image.get("url"):
                return SITE + image["url"]
    return ""


def normalize(product: dict, channel: str | None = None, category: str | None = None) -> dict:
    """將 API 商品轉為內部使用的精簡格式。"""
    coupon = product.get("couponDiscount") or {}
    decals = _decals(product)
    path = product.get("url") or ""

    price = (product.get("price") or {}).get("value")
    base = (product.get("basePrice") or {}).get("value")
    discount = coupon.get("discountValue") or None
    # price 為折扣後售價；多規格商品在列表上不提供售價
    original = base or (price + discount if price is not None and discount else None)
    pct = round(discount / original * 100, 1) if discount and original else None

    if channel is None:
        if "decal_onlineExclusive" in decals:
            channel = CH_ONLINE_ONLY
        elif "decal_SAMEPRICE" in decals:
            channel = CH_SAME_PRICE
        else:
            channel = CH_ONLINE
    if category is None:
        category = _CATEGORY_NAMES.get(path.strip("/").split("/")[0], _OTHER)

    return {
        "code": str(product["code"]),
        "name": (product.get("name") or "").strip(),
        "en": (product.get("englishName") or "").strip(),
        "path": path,
        "channel": channel,
        "category": category,
        "price": price,
        "original": original,
        "discount": discount,
        "pct": pct,
        "start": coupon.get("discountStartDate"),
        "end": coupon.get("discountEndDate"),
        "min_qty": int(coupon.get("minQtyDiscount") or 0),
        "image": _image(product),
        "rating": product.get("averageRating") or 0,
        "reviews": product.get("numberOfReviews") or 0,
        "in_stock": (product.get("stock") or {}).get("stockLevelStatus") != "outOfStock",
        "lower_price": "decal_LowerPrice" in decals,
    }


def fetch_online_deals() -> list[dict]:
    """線上特價：優惠商品分類中實際帶有折扣金額的商品。"""
    products = _search("hot-buys")
    deals = [
        normalize(p)
        for p in products
        if (p.get("couponDiscount") or {}).get("discountValue")
    ]
    if not deals:
        raise FetchError("優惠商品分類未取得任何折扣商品，可能是官網介面變更")
    return deals


def fetch_warehouse_deals() -> list[dict]:
    """賣場特價：賣場獨家商品中帶有優惠期間者。"""
    root = _get_json({
        "category": "WH",
        "lang": "zh_TW",
        "curr": "TWD",
        "fields": "subCategories(code,name)",
    })
    deals: dict[str, dict] = {}
    for sub in root.get("subCategories") or []:
        code = sub.get("code") or ""
        if not code.startswith("WH"):
            continue
        category = (sub.get("name") or "").removeprefix("賣場-").strip() or _OTHER
        for product in _search(code):
            coupon = product.get("couponDiscount") or {}
            if coupon.get("discountStartDate") or coupon.get("discountEndDate"):
                deals[str(product["code"])] = normalize(product, CH_WAREHOUSE, category)
        time.sleep(PAUSE_SECONDS)
    return list(deals.values())


def fetch_all() -> tuple[list[dict], list[str]]:
    """取回所有特價商品。回傳（商品清單, 警告訊息）。

    線上特價為主要資料，失敗即中止；賣場特價為輔助資料，失敗時僅警告。
    """
    warnings: list[str] = []
    deals = fetch_online_deals()
    try:
        online_codes = {d["code"] for d in deals}
        deals += [d for d in fetch_warehouse_deals() if d["code"] not in online_codes]
    except FetchError as error:
        warnings.append(f"賣場特價擷取失敗，本次僅含線上特價：{error}")
    return deals, warnings
