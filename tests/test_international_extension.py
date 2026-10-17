import datetime as dt
import os
import unittest
import uuid
from dataclasses import replace
from unittest.mock import patch

from crawl.common import KST, ensure_database, load_mysql_config, mysql_connect
from crawl.international.policy import InternationalPolicy
from crawl.international.runner import _run_page
from crawl.international.source_http import FetchResult, _MachinerylineParser
from crawl.international.sync import prepare_extension, sync_progress
from crawl.international.marketplaces import PayloadCache


class PaginationTests(unittest.TestCase):
    def test_machineryline_uses_actual_next_link(self):
        parser = _MachinerylineParser()
        parser.feed('<a class="pgn-item pgn-next" href="?page=3">Next</a>')
        self.assertTrue(parser.has_next)
        self.assertFalse(_MachinerylineParser().has_next)


@unittest.skipUnless(os.environ.get("SCANNER_TEST_MYSQL") == "1", "opt-in local MySQL integration")
class ExtensionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original = load_mysql_config()
        if original.host not in ("127.0.0.1", "localhost"):
            raise RuntimeError("integration tests require local MySQL")
        cls.config = replace(original, database="heavyequip_scanner_extension_test_20260920")
        ensure_database(cls.config)

    def setUp(self):
        self.stream = "test:" + uuid.uuid4().hex
        self.policy = InternationalPolicy(10000000, {"USD":1400.0}, "2026-09-20")
        self.cutoff = dt.datetime(2025,9,20,tzinfo=KST)

    def payload(self, name, price=20000, date="2026-09-10"):
        return {"id":self.stream+name,"model":"320","brand":"CAT","title":"CAT 320 Excavator",
                "categoryName":"Excavators","priceOriginal":price,"priceOriginalUnit":"USD",
                "createDate":date,"assetUrl":"https://example.test/"+self.stream+name}

    def run_page(self, page, payloads, *, remaining=8000, new_only=False, stream=None):
        fetcher = unittest.mock.Mock(return_value=FetchResult("https://example.test",200,payloads,True))
        result = _run_page(self.config,site_slug="mascus_global",url=f"https://example.test/{self.stream}/{page}",
                          cursor=f"excavators:{page}",stream_key=stream or self.stream,cutoff=self.cutoff,
                          remaining=remaining,policy=self.policy,fetcher=fetcher,only_new_listings=new_only)
        return result, fetcher

    def test_resume_does_not_resend_and_extension_cap_is_idempotent(self):
        result,_=self.run_page(1,[self.payload("A")],remaining=1)
        self.assertEqual(result,(1,False,False))
        plan=prepare_extension(self.config,"mascus_global",self.stream,"more-v1",8000,"2025-09-20 00:00:00")
        again=prepare_extension(self.config,"mascus_global",self.stream,"more-v1",8000,"2025-09-21 00:00:00")
        self.assertEqual(plan["target_count"],8001)
        self.assertEqual(again["target_count"],8001)
        result,fetcher=self.run_page(1,[self.payload("A")])
        self.assertEqual(result,(0,True,True));fetcher.assert_not_called()

    def test_extension_counts_only_new_database_rows(self):
        self.run_page(1,[self.payload("A")])
        result,_=self.run_page(2,[self.payload("A"),self.payload("B")],new_only=True,stream=self.stream+":extension")
        self.assertEqual(result[0],1)

    def test_recent_rejected_price_does_not_trigger_old_promotion_cutoff(self):
        result,_=self.run_page(1,[self.payload("recent",price=1),self.payload("old",date="2020-01-01")])
        self.assertEqual(result,(0,True,False))

    def test_failed_checkpoint_rolls_back_listing_insert(self):
        with patch("crawl.international.runner.complete_request", return_value=False):
            with self.assertRaises(RuntimeError):
                self.run_page(1,[self.payload("rollback")])
        with mysql_connect(self.config,self.config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS n FROM listings WHERE pid=%s",(self.stream+"rollback",))
                self.assertEqual(cursor.fetchone()["n"],0)

    def test_undated_exception_is_explicit_and_restart_safe(self):
        payload=self.payload('undated',date=None)
        fetcher=unittest.mock.Mock(return_value=FetchResult('https://example.test',200,[payload],False))
        kwargs=dict(config=self.config,site_slug='mascus_global',url='https://example.test/'+self.stream,
                    cursor='page:1',stream_key=self.stream,cutoff=self.cutoff,remaining=8000,
                    policy=self.policy,fetcher=fetcher,allow_undated=True)
        self.assertEqual(_run_page(**kwargs),(1,False,False))
        self.assertEqual(_run_page(**kwargs),(0,False,True))
        self.assertEqual(fetcher.call_count,1)
        with mysql_connect(self.config,self.config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT posted_at,posted_date,crawled_at FROM listings WHERE pid=%s',(payload['id'],))
                row=cursor.fetchone();self.assertIsNone(row['posted_at']);self.assertIsNone(row['posted_date'])
                self.assertIsNotNone(row['crawled_at'])

    def test_default_still_excludes_undated(self):
        result,_=self.run_page(1,[self.payload('no-date',date=None)])
        self.assertEqual(result[0],0)

    def test_detail_cache_survives_recreated_collector_without_request(self):
        cache=PayloadCache(self.config,'plant_equipment',self.stream,0)
        with patch('crawl.international.marketplaces.fetch_text',return_value=(200,'https://example.test','{"id":42}')) as request:
            import json
            self.assertEqual(cache.get('https://example.test',json.loads)['data']['id'],42)
            resumed=PayloadCache(self.config,'plant_equipment',self.stream,0)
            self.assertEqual(resumed.get('https://example.test',json.loads)['data']['id'],42)
            self.assertEqual(request.call_count,1)


if __name__ == "__main__":
    unittest.main()
