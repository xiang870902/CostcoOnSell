"""核心邏輯測試：python -m unittest discover -s tests"""
import unittest
from datetime import datetime

from costco_deals import notify, store
from costco_deals.common import CH_ONLINE, CH_ONLINE_ONLY, CH_SAME_PRICE, CH_WAREHOUSE, TW
from costco_deals.fetcher import normalize
from costco_deals.report import build_report

START = "2026-11-04T16:00:00.000Z"
END = "2026-11-11T15:59:59.999Z"


def api_product(code="165005", price=1079.0, base=1349.0, discount=270.0, decals=(), **extra):
    product = {
        "code": code,
        "name": "滿意寶寶 紙尿褲 [XXL] 120片",
        "englishName": "MamyPoko Diaper",
        "url": f"/Household-Baby-Toys/Baby/p/{code}",
        "couponDiscount": {
            "discountValue": discount,
            "discountStartDate": START,
            "discountEndDate": END,
            "minQtyDiscount": 0,
        },
        "images": [{"format": "product", "url": "/medias/a.jpg"}],
        "stock": {"stockLevelStatus": "inStock"},
        "decalData": [{"key": "1", "value": {"url": f"/mediapermalink/{d}"}} for d in decals],
    }
    if price is not None:
        product["price"] = {"value": price}
    if base is not None:
        product["basePrice"] = {"value": base}
    product.update(extra)
    return product


def deal(**kwargs):
    item = normalize(api_product(**kwargs))
    item.update(is_new=True, flag="", low_price=None, low_date="")
    return item


class NormalizeTest(unittest.TestCase):
    def test_price_and_percent(self):
        item = normalize(api_product())
        self.assertEqual((item["price"], item["original"], item["discount"]), (1079.0, 1349.0, 270.0))
        self.assertEqual(item["pct"], 20.0)
        self.assertEqual(item["category"], "日用、婦幼、玩具")
        self.assertEqual(item["image"], "https://www.costco.com.tw/medias/a.jpg")

    def test_original_falls_back_to_price_plus_discount(self):
        self.assertEqual(normalize(api_product(base=None))["original"], 1349.0)

    def test_rating_and_reviews_are_coerced_to_numbers(self):
        item = normalize(api_product(averageRating="4.5", numberOfReviews="12"))
        self.assertEqual((item["rating"], item["reviews"]), (4.5, 12))
        with self.assertRaises(ValueError):
            normalize(api_product(numberOfReviews="<img src=x onerror=alert(1)>"))

    def test_multi_variant_has_no_price(self):
        item = normalize(api_product(price=None, base=None))
        self.assertIsNone(item["price"])
        self.assertIsNone(item["pct"])
        self.assertEqual(item["discount"], 270.0)

    def test_channel_from_decals(self):
        self.assertEqual(normalize(api_product())["channel"], CH_ONLINE)
        self.assertEqual(normalize(api_product(decals=["decal_onlineExclusive"]))["channel"], CH_ONLINE_ONLY)
        self.assertEqual(normalize(api_product(decals=["decal_SAMEPRICE"]))["channel"], CH_SAME_PRICE)


class StoreTest(unittest.TestCase):
    def test_first_run_then_only_changes_are_new(self):
        state = {}
        deals = [deal()]
        self.assertTrue(store.mark_new(deals, state))
        self.assertTrue(deals[0]["is_new"])
        store.update_seen(deals, state, datetime(2026, 11, 9, tzinfo=TW))

        same = [deal()]
        self.assertFalse(store.mark_new(same, state))
        self.assertFalse(same[0]["is_new"])

        repriced = [deal(price=999.0, discount=350.0)]
        store.mark_new(repriced, state)
        self.assertTrue(repriced[0]["is_new"])

    def test_seen_kept_briefly_after_end_then_pruned(self):
        state = {}
        store.update_seen([deal()], state, datetime(2026, 11, 9, tzinfo=TW))
        store.update_seen([], state, datetime(2026, 11, 13, tzinfo=TW))
        self.assertEqual(len(state["seen"]), 1)
        store.update_seen([], state, datetime(2026, 11, 20, tzinfo=TW))
        self.assertEqual(state["seen"], {})

    def test_history_flags(self):
        history = {}
        first = [deal()]
        store.apply_history(first, history, "2026-11-09")
        self.assertEqual(first[0]["flag"], "")

        # 同一檔期重複執行不會新增紀錄
        again = [deal()]
        store.apply_history(again, history, "2026-11-10")
        self.assertEqual(len(history["165005"]["o"]), 1)

        lower = [deal(price=999.0, discount=350.0)]
        lower[0]["start"] = "2026-12-01T16:00:00.000Z"
        store.apply_history(lower, history, "2026-12-02")
        self.assertEqual(lower[0]["flag"], store.FLAG_NEW_LOW)
        self.assertEqual((lower[0]["low_price"], lower[0]["low_date"]), (1079, "2026-11-09"))

        # 標記在同一檔期內維持不變
        lower_again = [deal(price=999.0, discount=350.0)]
        lower_again[0]["start"] = "2026-12-01T16:00:00.000Z"
        store.apply_history(lower_again, history, "2026-12-05")
        self.assertEqual(lower_again[0]["flag"], store.FLAG_NEW_LOW)

        tie = [deal(price=999.0, discount=350.0)]
        tie[0]["start"] = "2027-01-01T16:00:00.000Z"
        store.apply_history(tie, history, "2027-01-02")
        self.assertEqual(tie[0]["flag"], store.FLAG_TIE_LOW)


class NotifyTest(unittest.TestCase):
    def test_no_new_deals_means_no_messages(self):
        item = deal()
        item["is_new"] = False
        self.assertEqual(notify.build_messages([item], False), [])

    def test_line_escapes_brackets_and_uses_short_url(self):
        line = notify.deal_line(deal())
        self.assertIn("**-20%**", line)
        self.assertIn("(XXL)", line)
        self.assertIn("(https://www.costco.com.tw/p/165005)", line)
        self.assertIn("至 11/11", line)

    def test_warehouse_line_has_no_price(self):
        item = deal(price=None, base=None, discount=None)
        item["channel"] = CH_WAREHOUSE
        line = notify.deal_line(item)
        self.assertNotIn("$", line)
        self.assertIn("11/5–11/11", line)

    def test_messages_respect_discord_limits(self):
        deals = []
        for index in range(400):
            item = deal(code=str(100000 + index), price=1000.0 + index, base=2000.0 + index, discount=1000.0)
            deals.append(item)
        messages = notify.build_messages(deals, True, "https://example.com/", top_n=60)
        self.assertEqual(len(messages), 2)
        for message in messages:
            self.assertEqual(len(message["embeds"]), 1)
            self.assertEqual(message["allowed_mentions"], {"parse": []})
            total = 0
            for embed in message["embeds"]:
                self.assertLessEqual(len(embed.get("description", "")), 4096)
                self.assertLessEqual(len(embed["title"]), 256)
                total += len(embed["title"]) + len(embed.get("description", ""))
                total += len((embed.get("footer") or {}).get("text", ""))
                total += sum(len(f["name"]) + len(f["value"]) for f in embed.get("fields", []))
            self.assertLessEqual(total, 6000)


class ReportTest(unittest.TestCase):
    def test_report_embeds_data_safely(self):
        item = deal()
        item["name"] = "測試</script><b>商品"
        html = build_report([item], datetime(2026, 11, 9, 8, 30, tzinfo=TW))
        self.assertIn("2026-11-09 08:30", html)
        self.assertNotIn("</script><b>", html)
        self.assertNotIn("__DATA__", html)


if __name__ == "__main__":
    unittest.main()
