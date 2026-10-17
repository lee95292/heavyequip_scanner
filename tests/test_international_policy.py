from __future__ import annotations

import unittest

from crawl.international.policy import InternationalPolicy, prepare_record
from crawl.international.source_http import machineryline_url, mascus_url


class InternationalCollectionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = InternationalPolicy(
            minimum_price_krw=10_000_000,
            exchange_rates_krw={"USD": 1400.0, "EUR": 1650.0},
            exchange_rate_date="2026-09-20",
        )

    def record(self, *, category="Crawler Excavators", price=10_000, currency="USD"):
        return {
            "category_name": category,
            "listing_name": "Volvo EC480LC crawler excavator",
            "description": "Tracked construction machine",
            "raw": {"currency": currency, "native_price": price, "source": {}},
        }

    def test_source_urls_apply_verified_price_and_newest_first_filters(self):
        machineryline = machineryline_url(2, 6061)
        self.assertIn("page=2", machineryline)
        self.assertIn("pr0=6061", machineryline)
        self.assertIn("scurr=EUR", machineryline)

        mascus = mascus_url("excavators", 3, 7143)
        self.assertIn("catalogs=construction&categories=excavators&price.min=7143", mascus)
        self.assertTrue(mascus.endswith("/3,createdate_desc,search.html"))

        forklifts = mascus_url("forklifttrucks", 1, 7143)
        self.assertIn("catalogs=materialhandling&categories=forklifttrucks", forklifts)

    def test_accepts_priced_construction_machine_and_persists_conversion_inputs(self):
        record, reason = prepare_record(self.record(), self.policy)
        self.assertIsNone(reason)
        self.assertEqual(record["price_krw"], 14_000_000)
        self.assertEqual(record["sale_currency"], "USD")
        self.assertEqual(record["sale_price"], 10_000.0)
        self.assertEqual(record["exchange_rate_krw"], 1400.0)
        self.assertEqual(record["exchange_rate_date"], "2026-09-20")

    def test_rejects_missing_or_below_minimum_price(self):
        _, missing_reason = prepare_record(self.record(price=None), self.policy)
        _, low_reason = prepare_record(self.record(price=7_000), self.policy)
        self.assertEqual(missing_reason, "missing_price")
        self.assertEqual(low_reason, "below_minimum_price")

    def test_rejects_parts_and_non_machine_categories(self):
        _, part_reason = prepare_record(self.record(category="Construction spare parts"), self.policy)
        _, generator_reason = prepare_record(self.record(category="Diesel generators"), self.policy)
        self.assertEqual(part_reason, "non_construction_machine")
        self.assertEqual(generator_reason, "non_construction_machine")

    def test_accepts_requested_machine_types(self):
        for category in ("Forklifts", "Road rollers", "Wheel loaders", "Backhoe loaders", "Dozers"):
            with self.subTest(category=category):
                record, reason = prepare_record(self.record(category=category), self.policy)
                self.assertIsNotNone(record)
                self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
