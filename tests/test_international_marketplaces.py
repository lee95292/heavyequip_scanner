import datetime as dt
import json
import unittest
from unittest.mock import Mock, patch

from crawl.common import KST
from crawl.international.marketplaces import product_data, plant_list_data, fetch_plant, europe_list_data
from crawl.international.parsers import parse_listing_payload
from crawl.international.policy import InternationalPolicy, prepare_record
from crawl.international.source_http import parse_ironplanet_page, SourceAccessError


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.policy = InternationalPolicy(10000000,{'USD':1400,'AUD':930,'EUR':1650},'2026-09-20')
        self.iron = {'equipId':'14279643','description':'2009 Terex RH170 Tracked Excavator',
                     'price':'<span class="price"><span itemprop="price">AU $180,000</span></span>',
                     'currency':'AUD','convPrice':'US $120,000','auctionType':'<div>Buy Now</div>',
                     'usage':'63,138 hrs','flagPath':'AUS','eumeLocation':'Queensland',
                     'itemPageUri':'/for-sale/Excavators-2009-Terex-RH170-Tracked-Excavator-Queensland/14279643?h=one'}

    def test_iron_native_price_identity_and_no_fake_date(self):
        row=parse_listing_payload('ironplanet',self.iron)
        prepared,reason=prepare_record(row,self.policy)
        self.assertIsNone(reason)
        self.assertEqual(prepared['sale_price'],180000)
        self.assertEqual(prepared['sale_currency'],'AUD')
        self.assertEqual(prepared['price_krw'],167400000)
        self.assertEqual(prepared['raw']['operating_hours'],63138)
        self.assertIsNone(prepared['posted_at'])
        self.assertEqual(prepared['location'],'Queensland, AU')
        self.assertEqual(prepared['model_name'],'RH170')
        self.assertNotIn('?',prepared['detail_url'])
        self.assertEqual(row['content_hash'],parse_listing_payload('ironplanet',{**self.iron,'itemPageUri':self.iron['itemPageUri']+'changed'})['content_hash'])

    def test_source_model_tokens_remain_separate_from_dictionary(self):
        for title,maker,model in [('2019 Genie GTH-1056 Telehandler','Genie','GTH-1056'),
                                  ('2025 FM Gru 1140FA-US Tower Crane','FM Gru','1140FA-US'),
                                  ('2008 Potain IGO T85 13227 lb Tower Crane','Potain','IGO T85'),
                                  ('2021 Case CX145D SR Tracked Excavator','Case','CX145D SR')]:
            row=parse_listing_payload('ironplanet',{**self.iron,'description':title})
            self.assertEqual(row['manufacturer'],maker);self.assertEqual(row['model_name'],model)

    def test_iron_offer_bid_and_kilometers_are_not_asking_price_or_hours(self):
        row=parse_listing_payload('ironplanet',{**self.iron,'buyItNow':True,'auctionType':'Current High Offer','usage':'12000 km'})
        self.assertIsNone(row['raw']['operating_hours'])
        self.assertEqual(prepare_record(row,self.policy)[1],'not_asking_price')

    def test_iron_truck_mentions_crane_and_engine_does_not_pass_category(self):
        row=parse_listing_payload('ironplanet',{**self.iron,'description':'2023 DAF CF450 Truck w/Crane',
             'itemPageUri':'/for-sale/Trucks-2023-DAF-CF450/100','features':'crane engine loader'})
        self.assertEqual(prepare_record(row,self.policy)[1],'unconfirmed_machine_category')

    def test_iron_pagination_and_challenge_fail_closed(self):
        url='https://www.ironplanet.com/jsp/s/search.ips?pstart=0'
        html='quickviews.push('+json.dumps(self.iron)+');<a href="?pstart=60">Next</a>'
        self.assertTrue(parse_ironplanet_page(html,url).has_next)
        self.assertFalse(parse_ironplanet_page(html,url.replace('=0','=60')).has_next)
        with self.assertRaises(SourceAccessError):
            parse_ironplanet_page('<title>Just a moment</title>',url)

    def test_product_does_not_use_production_or_offer_expiration_as_posted_date(self):
        product={'@type':'Product','sku':'1401066','model':'SC213PD','brand':{'name':'DELCO'},
                 'category':'Compactors','productionDate':'2026-01-01',
                 'offers':{'price':'33140','priceCurrency':'EUR','priceValidUntil':'2028-09-20'}}
        parsed=product_data('<script type="application/ld+json">'+json.dumps({'@graph':[product]})+'</script>')
        row=parse_listing_payload('plant_equipment',parsed)
        self.assertIsNone(row['posted_at'])
        self.assertEqual(row['raw']['currency'],'EUR')
        self.assertEqual(row['raw']['native_price'],33140)

    def test_plant_uses_detail_offer_not_display_conversion_and_skips_ads_auctions(self):
        body=json.dumps({'listings':[{'type':'ad'},{'type':'listing','id':1,'price':100000,'currency':'USD',
             'listing_url':'/equipment-items/example','year':'2020','title':'CAT 320','country':'China','source':'site'}],
             'filters':{'pages_count':2,'current_page':1}})
        data=plant_list_data(body)
        cache=Mock();cache.get.side_effect=[{'url':'https://example.test','status':200,'data':data},
             {'data':{'id':'1','price':90000,'currency':'EUR','category':'Excavators','availability':'https://schema.org/InStock'}}]
        result=fetch_plant('construction',1,7143,cache)
        self.assertTrue(result.has_next)
        self.assertEqual(result.payloads[0]['currency'],'EUR')
        self.assertEqual(result.payloads[0]['price'],90000)
        self.assertEqual(result.payloads[0]['listDisplayPrice'],100000)

    def test_europe_rental_auction_excluded_and_actual_pagination(self):
        card='<div class="vehicle" data-vehicule="1" data-price="90,000 EUR" data-href="/x"><div data-json=\'{"sale":true,"bid":false}\'></div><h2 class="card-title">Case WX168</h2></div>'
        data=europe_list_data(card+'<div class="btn-next-pagination" data-next="2"></div>')
        self.assertEqual(data['nextPage'],2);self.assertEqual(len(data['items']),1)
        self.assertEqual(europe_list_data(card.replace('"bid":false','"bid":true'))['items'],[])


if __name__=='__main__': unittest.main()
