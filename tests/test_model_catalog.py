import unittest

from crawl.common import model_norm, record_model_norm
from crawl.model_catalog import CAT_ENTRIES


class CatModelTests(unittest.TestCase):
    def test_every_official_model_has_prefixed_canonical_and_alias(self):
        self.assertGreaterEqual(len(CAT_ENTRIES), 380)
        for entry in CAT_ENTRIES:
            with self.subTest(model=entry["canonical"]):
                self.assertEqual(model_norm(entry["canonical"]), entry["canonical"])
                self.assertEqual(model_norm(entry["alias"], "Caterpillar"), entry["canonical"])

    def test_brands_and_specific_variants(self):
        for raw in ("CAT320", "Cat 320", "Caterpillar 320", "캐터필라 320"):
            self.assertEqual(model_norm(raw), "CAT320")
        self.assertEqual(model_norm("CAT 320 GC"), "CAT320GC")
        self.assertEqual(model_norm("Caterpillar 320D2 L"), "CAT320D2L")
        self.assertEqual(model_norm("Caterpillar D6R"), "CATD6R")
        self.assertEqual(model_norm("336GC", "CAT"), "CAT336GC")

    def test_no_cross_word_or_other_manufacturer_numeric_matches(self):
        self.assertEqual(model_norm("2021 Caterpillar 349 Excavator"), "CAT349")
        self.assertNotEqual(model_norm("349 Excavator"), "349E")
        self.assertIsNone(model_norm("320 hours Excavator"))
        self.assertIsNone(model_norm("320", "Volvo"))
        self.assertIsNone(model_norm("10저소음뿌레카"))
        self.assertIsNone(model_norm("EXCAVATOR"))
        self.assertEqual(model_norm("2024 Volvo EC480EL tracked excavator"), "EC480EL")

    def test_record_refines_same_family_without_description_contamination(self):
        self.assertEqual(record_model_norm({"manufacturer":"CAT","model_name":"320","listing_name":"CAT 320 GC Excavator"}),"CAT320GC")
        self.assertEqual(record_model_norm({"manufacturer":"CAT","model_name":"320","listing_name":"CAT 320 Excavator","description":"compatible with 349E"}),"CAT320")

    def test_cat_prefix_does_not_leak_to_other_catalog_families(self):
        self.assertEqual(model_norm("LG956F", "Caterpillar"), "LG956F")
        self.assertEqual(model_norm("CA30D", "Caterpillar"), "CA30D")
        self.assertIsNone(model_norm("MLT 741 120 H LSU", "Manitou"))
        self.assertEqual(model_norm("Caterpillar D6R"), "CATD6R")


if __name__ == "__main__":
    unittest.main()
