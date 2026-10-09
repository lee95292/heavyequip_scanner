import datetime as dt
import json
import unittest
from unittest.mock import Mock, patch
from crawl import focus_scan as f
from test_focus_scan import FakeStore, NOW, factory, row, rule

class ResponseHistoryTests(unittest.TestCase):
    def test_whitelist_and_unknown_values(self):
        self.assertEqual(f.response_fields([{'model_name':'', 'price':None,'manufactured_ym':'미상','seller':'private'},None]),
                         [{'model_name':'','manufactured_ym':'미상','price':None}])
        self.assertEqual(f.response_fields([{'model_name':{},'price':0,'manufactured_ym':False}]),
                         [{'model_name':None,'manufactured_ym':None,'price':'0'}])

    def test_store_enforces_three_fields_and_empty_payload(self):
        for rows in [[dict(row(),raw={'secret':'private'})],[]]:
            with self.subTest(rows=bool(rows)),patch.object(f,'mysql_connect') as connect:
                cursor=connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
                cursor.lastrowid=42
                store=f.Store(Mock(database="test"));store.execute=Mock()
                store.log(None,'100105','response','parsed',response_rows=rows)
                sql,params=cursor.execute.call_args_list[1].args
                self.assertIn('focus_log_samples',sql);self.assertEqual(params[0],42)
                self.assertEqual(json.loads(params[1]),f.response_fields(rows))
                self.assertNotIn('private',params[1])

    @patch.object(f,'stamp',return_value=NOW)
    def test_keeps_all_fetched_pages_when_later_page_fails(self,_):
        store=FakeStore({'boundary_json':['old'],'last_success_at':NOW-dt.timedelta(minutes=10)})
        create,crawler=factory([[row('a')],[row('b')]],more=True)
        crawler.get_soup.side_effect=[object(),object(),RuntimeError('failed')]
        with self.assertRaises(RuntimeError):
            f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create)
        logs=[fields['response_rows'] for args,fields in store.logs if args[2]=='response']
        self.assertEqual(len(logs),2);self.assertEqual(len(logs[0]),1)
        self.assertFalse(store.saved)

    @patch.object(f,'stamp',return_value=NOW)
    def test_includes_old_and_boundary_rows(self,_):
        old=row('old',time='2020-01-01')
        store=FakeStore({'boundary_json':[f.identity(old)],'last_success_at':NOW-dt.timedelta(minutes=10)})
        create,_=factory([[old,row('older',time='2019-01-01')]])
        f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create)
        self.assertEqual(len(store.logs[0][1]['response_rows']),2)

    @patch.object(f,'stamp',return_value=NOW)
    def test_empty_page_has_explicit_zero_response(self,_):
        store=FakeStore();create,_=factory([[]])
        f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create)
        self.assertEqual(store.logs[0][1]['response_rows'],[])

    def test_exact_existing_seven_day_cleanup(self):
        store=f.Store(Mock(database="test"));store.execute=Mock();store.cleanup()
        for table in ('focus_log_samples','focus_logs','focus_seen'):
            self.assertIn(f'DELETE FROM {table} WHERE created_at < NOW() - INTERVAL 7 DAY LIMIT 10000',
                          [call.args[0] for call in store.execute.call_args_list])

if __name__=='__main__':unittest.main()
