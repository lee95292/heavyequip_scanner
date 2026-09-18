from __future__ import annotations

import unittest

from crawl.international.catalog import load_source_catalog
from crawl.international.source_http import _MachinerylineParser
from crawl.international.parsers import parse_listing_payload
from crawl.international.sync import build_request_fingerprint, plan_initial_backfill


class InternationalSourceTests(unittest.TestCase):
    def test_catalog_contains_priority_sources_and_enables_verified_collectors(self):
        catalog = load_source_catalog()
        self.assertTrue(catalog["requestPolicy"]["enabled"])
        slugs = {source["slug"] for source in catalog["sources"]}
        self.assertTrue({"machinery_trader", "machineryline", "ironplanet"} <= slugs)
        enabled = {source["slug"] for source in catalog["sources"] if source["readiness"] == "collection_enabled"}
        self.assertEqual(enabled, {"machineryline", "mascus_global"})

    def test_request_fingerprint_is_stable_across_parameter_order(self):
        first = build_request_fingerprint("GET", "https://example.test/list", params={"page": 1, "sort": "new"})
        second = build_request_fingerprint("get", "https://example.test/list", params={"sort": "new", "page": 1})
        self.assertEqual(first, second)

    def test_initial_backfill_is_newest_first_and_page_specific(self):
        first = plan_initial_backfill("machineryline", 1)
        second = plan_initial_backfill("machineryline", 2)
        self.assertEqual(first.params["order"], "posted_desc")
        self.assertNotEqual(first.request_fingerprint, second.request_fingerprint)

    def test_machinery_trader_parser_preserves_native_currency(self):
        record = parse_listing_payload(
            "machinery_trader",
            {
                "listingId": 251043507,
                "title": "2021 SANY SR285R",
                "make": "SANY",
                "model": "SR285R",
                "year": 2021,
                "displayPrice": "USD $120,000",
                "hours": "3,200 hrs",
                "updatedAt": "2026-08-03 20:48:00",
                "location": "Changsha, Hunan, China",
                "url": "/listing/for-sale/251043507/example",
            },
        )
        self.assertEqual(record["pid"], "251043507")
        self.assertEqual(record["raw"]["currency"], "USD")
        self.assertEqual(record["raw"]["native_price"], 120000)
        self.assertEqual(record["raw"]["operating_hours"], 3200)
        self.assertIsNone(record["price_krw"])

        updated = parse_listing_payload(
            "machinery_trader",
            {"listingId": 251043507, "displayPrice": "USD $110,000"},
        )
        self.assertEqual(record["content_hash"], updated["content_hash"])

    def test_ironplanet_parser_keeps_auction_semantics(self):
        record = parse_listing_payload(
            "ironplanet",
            {
                "itemId": "IP-42",
                "name": "2023 Volvo EC550EL Tracked Excavator",
                "currentPrice": "US $150,000",
                "meter": "3,104 hrs",
                "buyingFormat": "Auction",
                "ironCladAssurance": True,
                "auctionEndAt": "2026-09-20T10:00:00-04:00",
                "url": "/for-sale/Excavators-IP-42",
            },
        )
        self.assertEqual(record["raw"]["sale_type"], "Auction")
        self.assertTrue(record["raw"]["ironclad_assurance"])
        self.assertEqual(record["raw"]["native_price"], 150000)

    def test_machineryline_html_parser_derives_posted_time_from_source_id(self):
        parser = _MachinerylineParser()
        parser.feed(
            '<div class="sales-list-item" data-code="26091500065017281500" '
            'data-name="Terex HC80" data-brand="Terex">'
            '<a class="sales-item-title-link" href="/listing">Terex HC80</a>'
            '<span class="price-value">$135,000</span></div>'
        )
        self.assertEqual(len(parser.payloads), 1)
        self.assertTrue(parser.payloads[0]["createdAt"].startswith("2026-09-15T00:06:50"))

    def test_mascus_parser_maps_structured_listing_fields(self):
        record = parse_listing_payload(
            "mascus_global",
            {
                "productId": "{ABC}", "brand": "CAT", "model": "920",
                "yearOfManufacture": 2020, "categoryName": "wheelloaders",
                "priceOriginal": 62000, "priceOriginalUnit": "USD",
                "meterReadout": 7070, "locationCity": "Windsor, CO",
                "locationCountryCode": "US", "companyName": "Dealer",
                "createDate": "2026-09-18T10:29:04", "assetUrl": "/construction/item.html",
            },
        )
        self.assertEqual(record["pid"], "{ABC}")
        self.assertEqual(record["raw"]["currency"], "USD")
        self.assertEqual(record["raw"]["operating_hours"], 7070)
        self.assertEqual(record["seller"], "Dealer")


if __name__ == "__main__":
    unittest.main()
