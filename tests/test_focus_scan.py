import datetime as dt
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from crawl import focus_scan as f

NOW=dt.datetime(2026,10,7,12,0)
def rule(**kw):
    return dict(id=1,revision=1,enabled=1,interval_minutes=10,model_contains='EW145',email='test@example.invalid',
                price_min_manwon=1000,price_max_manwon=5000,year_min=2015,year_max=2025,**kw)
def row(pid='1',time='2026-10-07 11:55:00',**kw):
    return dict(pid=pid,model_name='EW145B',price='3,000만원',manufactured_ym='2020.05',category_code='100105',
                posted_at=time,detail_url='https://www.4396200.com/sub8_1_vvv.html?pid='+pid,**kw)

class FakeStore:
    def __init__(self,cursor=None):self.value=cursor;self.saved=[];self.logs=[];self.seen={};self.enabled=True
    def cursor(self,*_):return self.value
    def save_cursor(self,*args):self.saved.append(args)
    def log(self,*args,**kwargs):self.logs.append((args,kwargs))
    def current(self,*_):return self.enabled
    def known(self,r,k):return (r['id'],k) in self.seen
    def claim(self,r,k):
        if (r['id'],k) in self.seen:return False
        self.seen[(r['id'],k)]='sending';return True
    def delivery(self,r,k,status):self.seen[(r['id'],k)]=status
    def prepare_mail(self,*_):return True

def factory(pages,more=False,valid=True):
    crawler=Mock();crawler.session=Mock();crawler.list_url.side_effect=lambda c,p:f'https://www.4396200.com/sub8_1_s.html?cate_code={c}&page={p}'
    crawler.get_soup.return_value=object();crawler.listing_table.return_value=object() if valid else None
    crawler.parse_listing_page.side_effect=pages;crawler.has_next_page.return_value=more
    return Mock(return_value=crawler),crawler

class FocusTests(unittest.TestCase):
    def test_contains_case_space(self):
        self.assertTrue(f.matches(rule(),{**row(),'model_name':' ew 145 B '}))
    def test_price_inclusive(self):
        for price in ['1,000만원','5,000만원']:self.assertTrue(f.matches(rule(),{**row(),'price':price}))
    def test_unknown_price_not_match(self):
        self.assertFalse(f.matches(rule(),{**row(),'price':'가격문의'}))
    def test_ranges(self):
        for values in [{'price':'999만원'},{'price':'5001만원'},{'manufactured_ym':'2014'},{'manufactured_ym':'미상'}]:self.assertFalse(f.matches(rule(),{**row(),**values}))
    def test_unbounded_unknown(self):
        r=rule();r.update(price_min_manwon=None,price_max_manwon=None,year_min=None,year_max=None)
        self.assertTrue(f.matches(r,{**row(),'price':'협의','manufactured_ym':'미상'}))
    def test_other_model(self):self.assertFalse(f.matches(rule(),{**row(),'model_name':'DX140'}))
    def test_exact_window(self):
        cutoff=NOW-dt.timedelta(minutes=10)
        for t,ok in [('2026-10-07 11:50:00',True),('2026-10-07 11:49:59',False),('2026-10-07 12:01:00',False)]:self.assertEqual(f.in_window(row(time=t),cutoff,NOW),ok)
    def test_date_precision_uses_raw(self):
        values=['']*11;values[10]='26.10.07'
        self.assertTrue(f.in_window(row(raw={'list_values':values}),NOW-dt.timedelta(minutes=10),NOW))
    def test_unknown_date_is_not_new(self):self.assertFalse(f.in_window(row(time=''),NOW-dt.timedelta(minutes=10),NOW))
    def test_midnight(self):self.assertTrue(f.in_window(row(time='2026-10-06 23:59:00'),dt.datetime(2026,10,6,23,55),dt.datetime(2026,10,7,0,5)))
    def test_identity_canonical(self):self.assertEqual(f.identity(row()),f.identity({**row(),'pid':None}))
    def test_url_allowlist(self):
        for url in ['http://www.4396200.com/','https://example.com/','https://www.4396200.com.evil.test/']:
            with self.assertRaises(ValueError):f.safe_path(url)
    def test_safe_log_query(self):self.assertNotIn('token',f.safe_path('https://www.4396200.com/sub8_1_s.html?cate_code=100105&token=private'))
    @patch.object(f,'stamp',return_value=NOW)
    def test_initial_baseline_no_mail(self,_):
        store=FakeStore();create,crawler=factory([[row()]])
        with patch.object(f,'deliver') as mail:self.assertEqual(f.scan_category(store,rule(),'100105',None,{},factory=create,rules=[rule()]),0);mail.assert_not_called()
        self.assertEqual(len(store.saved),1);self.assertEqual(len(store.saved[0][-1]),1);crawler.session.close.assert_called_once()
    @patch.object(f,'stamp',return_value=NOW)
    def test_stop_at_boundary_do_not_send_old_rows(self,_):
        store=FakeStore({'boundary_json':[f.identity(row('2'))],'last_success_at':NOW-dt.timedelta(minutes=10)})
        create,crawler=factory([[row('3'),row('2'),row('1')]],more=True)
        with patch.object(f,'deliver',return_value=True) as mail:self.assertEqual(f.scan_category(store,rule(),'100105',None,{},factory=create,rules=[rule()]),1);self.assertEqual(mail.call_args.args[2]['pid'],'3');self.assertEqual(mail.call_count,1)
        self.assertEqual(crawler.get_soup.call_count,1)
    @patch.object(f,'stamp',return_value=NOW)
    def test_old_rows_discarded(self,_):
        store=FakeStore({'boundary_json':['old'],'last_success_at':NOW-dt.timedelta(hours=2)})
        create,_=factory([[row(time='2026-10-07 11:00:00')]])
        with patch.object(f,'deliver') as mail:f.scan_category(store,rule(),'100105',None,{},factory=create,rules=[rule()]);mail.assert_not_called()
    @patch.object(f,'stamp',return_value=NOW)
    def test_invalid_html_does_not_advance(self,_):
        store=FakeStore();create,c=factory([[]],valid=False)
        with self.assertRaises(f.SourceResponseError):f.scan_category(store,rule(),'100105',None,{},factory=create,rules=[rule()])
        self.assertFalse(store.saved);c.session.close.assert_called_once()
    @patch.object(f,'stamp',return_value=NOW)
    def test_budget_no_false_success(self,_):
        store=FakeStore({'boundary_json':['old'],'last_success_at':NOW-dt.timedelta(minutes=10)});create,_=factory([[row()]]*3,more=True)
        with patch.object(f,'deliver',return_value=False),self.assertRaises(f.BudgetExceeded):f.scan_category(store,rule(),'100105',None,{},factory=create,rules=[rule()])
        self.assertFalse(store.saved)
    def test_dedupe(self):
        store=FakeStore()
        with patch.object(f.focus_mail,'send') as mail:
            self.assertTrue(f.deliver(store,rule(),row(),{}));self.assertFalse(f.deliver(store,rule(),row(),{}));self.assertEqual(mail.call_count,1)
    def test_ambiguous_no_retry(self):
        store=FakeStore()
        with patch.object(f.focus_mail,'send',side_effect=f.focus_mail.DeliveryFailure(False)) as mail:
            self.assertFalse(f.deliver(store,rule(),row(),{}));self.assertFalse(f.deliver(store,rule(),row(),{}));self.assertEqual(mail.call_count,1)
        self.assertEqual(store.seen[(1,f.identity(row()))],'uncertain')
    def test_three_safe_mail_attempts(self):
        store=FakeStore()
        with patch.object(f,'time') as clock,patch.object(f.focus_mail,'send',side_effect=f.focus_mail.DeliveryFailure(True)) as mail:
            self.assertFalse(f.deliver(store,rule(),row(),{}));self.assertEqual(mail.call_count,3)
    def test_pause_before_send(self):
        store=FakeStore();store.enabled=False
        with patch.object(f.focus_mail,'send') as mail:self.assertFalse(f.deliver(store,rule(),row(),{}));mail.assert_not_called()
    def test_no_legacy_write_code(self):
        source=Path(f.__file__).read_text()
        for token in ['upsert_records(', 'enqueue_crawl_task(', 'write_records(', 'write_record_chunk(']:self.assertNotIn(token,source)
    def test_cleanup_only_feature_tables(self):
        store=f.Store(None);store.execute=Mock();store.cleanup()
        sql=' '.join(c.args[0] for c in store.execute.call_args_list)
        self.assertIn('INTERVAL 7 DAY',sql);self.assertNotIn('DELETE FROM listings',sql);self.assertNotIn('crawl_tasks',sql)
        self.assertIn("status NOT IN ('sent','sending','uncertain')",sql)

    def test_receipt_snapshot_is_durable_before_smtp(self):
        store=FakeStore();store.prepare_mail=Mock(return_value=True)
        with patch.object(f.focus_mail,'send',side_effect=lambda *args:self.assertTrue(store.prepare_mail.called)):
            self.assertTrue(f.deliver(store,rule(),row(),{}))

    def test_permanent_receipt_blocks_replay_without_ephemeral_seen(self):
        store=f.Store(None);store.query=Mock(return_value={'status':'sent'})
        self.assertTrue(store.known(rule(),f.identity(row())))
        self.assertIn('focus_mail_history',store.query.call_args.args[0])
        store.query.assert_called_once()

    def test_receipt_contains_only_requested_listing_fields(self):
        store=f.Store(None);store.execute=Mock(return_value=1)
        self.assertTrue(store.prepare_mail(rule(),f.identity(row()),row()))
        sql,args=store.execute.call_args.args
        self.assertIn('condition_json',sql);self.assertEqual(args[2],'test@example.invalid')
        self.assertEqual(args[3],'EW145B');self.assertEqual(args[4],'3,000만원')
        self.assertNotIn('seller',sql);self.assertNotIn('contact',sql)


class FanoutTests(unittest.TestCase):
    @patch.object(f,'stamp',return_value=NOW)
    def test_one_page_fifty_independent_recipients(self,_):
        alerts=[dict(rule(),id=i) for i in range(1,51)]
        scan=dict(rule(),_scan=True)
        store=FakeStore({'boundary_json':[f.identity(row('old'))],'last_success_at':NOW-dt.timedelta(minutes=10)})
        create,crawler=factory([[row('new'),row('old')]],more=True)
        with patch.object(f.focus_mail,'send') as mail:
            self.assertEqual(f.scan_category(store,scan,'100105',None,{},factory=create,rules=alerts),50)
            self.assertEqual(mail.call_count,50)
            for alert in alerts:self.assertFalse(f.deliver(store,alert,row('new'),{},scan=scan))
            self.assertEqual(mail.call_count,50)
        self.assertEqual(crawler.get_soup.call_count,1)
        self.assertEqual(len(store.saved),1)
        self.assertIsNone(store.logs[-1][0][0])

    @patch.object(f,'stamp',return_value=NOW)
    def test_disabled_unmatched_and_failure_isolated(self,_):
        alerts=[rule(),dict(rule(),id=2),dict(rule(),id=3,enabled=0),dict(rule(),id=4,model_contains='DX140')]
        store=FakeStore({'boundary_json':['old'],'last_success_at':NOW-dt.timedelta(minutes=10)})
        create,crawler=factory([[row()]])
        with patch.object(f,'deliver',side_effect=[RuntimeError('first mail failed'),True]) as mail:
            self.assertEqual(f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create,rules=alerts),1)
            self.assertEqual(mail.call_count,2)
        self.assertEqual(crawler.get_soup.call_count,1)
        self.assertEqual([args[0] for args, fields in store.logs if args[2]=='mail'],[1])

    @patch.object(f,'stamp',return_value=NOW)
    def test_no_alerts_still_scans(self,_):
        store=FakeStore();create,crawler=factory([[row()]])
        f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create,rules=[])
        crawler.get_soup.assert_called_once()
        self.assertEqual(len(store.saved),1)

    @patch.object(f,'stamp',return_value=NOW)
    def test_all_response_triples_before_filtering(self,_):
        rows=[dict(row(str(i)),model_name='장비'+str(i),manufactured_ym='20.05',raw={'secret':'no'},seller='no') for i in range(9)]
        store=FakeStore();create,_=factory([rows])
        f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create)
        payload=store.logs[0][1]['response_rows']
        self.assertEqual(len(payload),9)
        self.assertEqual(payload[8],{'model_name':'장비8','manufactured_ym':'20.05','price':'3,000만원'})
        self.assertEqual(store.logs[0][0][2:4],('response','parsed'))
        self.assertNotIn('secret',str(payload));self.assertNotIn('detail_url',str(payload))

    def test_rule_edit_does_not_invalidate_scan(self):
        store=f.Store(None)
        store.query=Mock(side_effect=[{'enabled':1,'revision':4},{'enabled':1,'revision':2}])
        self.assertTrue(store.current({'id':1,'revision':4,'_scan':True}))
        self.assertFalse(store.current({'id':1,'revision':1}))
        self.assertIn('focus_scan_config',store.query.call_args_list[0].args[0])
        self.assertIn('focus_rules',store.query.call_args_list[1].args[0])

    def test_tick_queries_only_one_shared_schedule(self):
        store=Mock()
        scan=dict(rule(),_scan=True,categories_json=['100105'])
        store.query.side_effect=[[scan],[rule(),dict(rule(),id=2)]]
        store.execute.return_value=1
        with patch.object(f.focus_mail,'mail_ready',return_value=True),patch.object(f,'scan_category') as crawl,patch.object(f.time,'sleep'):
            f.tick(store,None,{})
        crawl.assert_called_once()
        self.assertEqual(len(crawl.call_args.kwargs['rules']),2)
        self.assertIn('focus_scan_config',store.query.call_args_list[0].args[0])
        self.assertNotIn('next_run_at',store.query.call_args_list[1].args[0])

class GreenManufacturingYearTests(unittest.TestCase):
    def test_raw_green_two_and_four_digit_formats(self):
        for value, expected in [('11.05',2011),('14.10',2014),('15.06',2015),('22.07',2022),('2015.06',2015),('2015',2015)]:
            with self.subTest(value=value):
                self.assertEqual(f.green_manufactured_year(value),expected)

    def test_explicit_fixed_century_policy(self):
        # Manufacturing years use 00-49 => 2000-2049, 50-99 => 1950-1999.
        for value, expected in [('00.01',2000),('49.12',2049),('50.01',1950),('90.12',1990),('99.01',1999)]:
            with self.subTest(value=value):
                self.assertEqual(f.green_manufactured_year(value),expected)

    def test_unknown_and_malformed_do_not_match_bounded_rule(self):
        for value in [None,'','미상','협의','15','15.00','15.13','2015.13','2015.06.01','abc15.06','115.06','20150.06']:
            with self.subTest(value=value):
                self.assertIsNone(f.green_manufactured_year(value))
                self.assertFalse(f.matches(rule(),dict(row(),manufactured_ym=value)))

    def test_inclusive_year_limits_and_outside_values(self):
        for value, expected in [('15.01',True),('25.12',True),('2015.01',True),('2025.12',True),('14.12',False),('26.01',False)]:
            with self.subTest(value=value):
                self.assertEqual(f.matches(rule(),dict(row(),manufactured_ym=value)),expected)

    def test_stored_production_dx_examples(self):
        alert=dict(rule(),model_contains='DX',price_max_manwon=10000,year_min=1950,year_max=2020)
        for model, price, year in [('DX220LCA','5,000만원','11.05'),('DX140R','2,500만원','14.10'),('DX220LCA','6,500만원','15.06')]:
            with self.subTest(model=model,year=year):
                self.assertTrue(f.matches(alert,dict(row(),model_name=model,price=price,manufactured_ym=year)))

    def test_unknown_year_stays_allowed_without_year_limits(self):
        alert=dict(rule(),year_min=None,year_max=None)
        self.assertTrue(f.matches(alert,dict(row(),manufactured_ym='미상')))

    @patch.object(f,'stamp',return_value=NOW)
    def test_raw_list_year_reaches_mocked_mail_and_dedupes(self,_):
        fresh=dict(row('new'),manufactured_ym='20.05')
        old=row('old')
        store=FakeStore({'boundary_json':[f.identity(old)],'last_success_at':NOW-dt.timedelta(minutes=10)})
        create,crawler=factory([[fresh,old],[fresh,old]],more=True)
        with patch.object(f.focus_mail,'send') as mail:
            self.assertEqual(f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create,rules=[rule()]),1)
            self.assertEqual(f.scan_category(store,dict(rule(),_scan=True),'100105',None,{},factory=create,rules=[rule()]),0)
            mail.assert_called_once()
        self.assertEqual(store.seen[(1,f.identity(fresh))],'sent')
        self.assertEqual(crawler.get_soup.call_count,2)

if __name__=='__main__':unittest.main()
