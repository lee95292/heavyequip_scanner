from __future__ import annotations

import unittest

import datetime as dt
from decimal import Decimal

from crawl.common import MODEL_NORM_MAP, enrich_record, find_model_matches, model_manufacturer, model_norm, model_variant_relations
from crawl.fx_monthly import next_due_run as next_fx_due_run
from crawl.fx_rates import parse_ecb_xml, sale_price_fields
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

    def test_blocked_sources_record_browser_request_format_and_proxy_result(self):
        sources = {source["slug"]: source for source in load_source_catalog()["sources"]}
        self.assertIn("/listings/search", sources["machinery_trader"]["listingUrl"])
        self.assertIn("HTTP 403", sources["machinery_trader"]["proxyProbe"])
        self.assertIn("pstart=N", sources["ironplanet"]["pagination"])
        self.assertIn("HTTP 202", sources["ironplanet"]["proxyProbe"])
        self.assertIn("from=N", sources["rb_auction"]["pagination"])
        self.assertIn("HTTP 403", sources["rb_auction"]["proxyProbe"])

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

        missing_year = parse_listing_payload(
            "mascus_global",
            {"productId": "{MISSING-YEAR}", "yearOfManufacture": 0},
        )
        self.assertIsNone(missing_year["manufactured_ym"])

    def test_official_model_catalog_fills_canonical_model_and_manufacturer(self):
        self.assertGreaterEqual(len(MODEL_NORM_MAP), 900)
        self.assertLess(len(MODEL_NORM_MAP), 1500)
        record = enrich_record({
            "listing_name": "2025 Hyundai HX130A LCR tracked excavator",
            "model_name": None,
            "manufacturer": None,
        })
        self.assertEqual(record["model_name"], "HX130A LCR")
        self.assertEqual(record["model_norm"], "HX130A LCR")
        self.assertEqual(record["manufacturer"], "Hyundai")

    def test_only_trusted_models_are_normalized(self):
        self.assertIsNone(model_norm("10저소음뿌레카"))
        self.assertIsNone(model_norm("08반자동멀티크"))
        self.assertEqual(model_norm("320"), "320")
        self.assertIsNone(model_norm("2025 CAT 320 excavator"))
        self.assertEqual(model_norm("2025 Volvo EC380EL excavator"), "EC380EL")

    def test_untrusted_source_model_is_kept_only_in_raw_payload(self):
        record = enrich_record({
            "listing_name": "10저소음뿌레카 판매",
            "model_name": "10저소음뿌레카",
            "raw": {},
        })
        self.assertIsNone(record["model_name"])
        self.assertIsNone(record["model_norm"])
        self.assertEqual(record["raw"]["source_model_name"], "10저소음뿌레카")

    def test_full_text_model_matching_deduplicates_and_prefers_detailed_variant(self):
        matches = find_model_matches((
            "Volvo EC480DL crawler; compatible with EC480 and EC480DL",
            "EC480DL",
        ))
        self.assertEqual(matches[0], "EC480DL")
        self.assertEqual(matches.count("EC480DL"), 1)
        self.assertIn("EC480", matches)

    def test_model_variant_relations_include_volvo_parent_chain(self):
        relations = set(model_variant_relations())
        self.assertIn(("EC480", "EC480D"), relations)
        self.assertIn(("EC480D", "EC480DL"), relations)
        self.assertEqual(model_manufacturer("EC480"), "Volvo")

    def test_ecb_cross_rates_are_converted_to_krw(self):
        snapshot = parse_ecb_xml("""
            <Envelope><Cube><Cube time="2026-09-18">
              <Cube currency="USD" rate="1.25"/>
              <Cube currency="KRW" rate="1500"/>
            </Cube></Cube></Envelope>
        """)
        self.assertEqual(snapshot.rates_krw["USD"], Decimal("1200"))
        fields = sale_price_fields({
            "source_site": "Machineryline",
            "price": "USD 10,000",
            "raw": {"currency": "USD", "native_price": 10000},
        }, snapshot)
        self.assertEqual(fields["sale_currency"], "USD")
        self.assertEqual(fields["sale_fx_rate_krw"], 1200.0)
        self.assertEqual(fields["price_krw"], 12_000_000)

        domestic = sale_price_fields({"source_site": "그린중기", "price": "2,500만원"}, None)
        self.assertEqual(domestic["sale_currency"], "KRW")
        self.assertEqual(domestic["sale_fx_rate_krw"], 1.0)
        self.assertEqual(domestic["price_krw"], 25_000_000)

    def test_monthly_fx_worker_runs_immediately_once_per_month(self):
        now = dt.datetime(2026, 9, 19, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
        self.assertEqual(next_fx_due_run(now, 1, (5, 30), ""), now)
        self.assertEqual(
            next_fx_due_run(now, 1, (5, 30), "2026-09"),
            dt.datetime(2026, 10, 1, 5, 30, tzinfo=now.tzinfo),
        )


if __name__ == "__main__":
    unittest.main()
