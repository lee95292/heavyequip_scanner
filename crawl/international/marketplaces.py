"""Verified public marketplace surfaces; no guessed private endpoints."""
from __future__ import annotations

import json
import re
import time
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from crawl.common import clean_text, mysql_connect
from crawl.international.source_http import FetchResult, SourceAccessError, fetch_text
from crawl.international.sync import build_request_fingerprint


class PayloadCache:
    """Durable parsed-response cache for list + detail requests within one stream.

    Keep small extracted objects, never megabytes of HTML or authentication data.
    A failed downstream parse/transaction reuses the successful HTTP response.
    Site-level MySQL collector locks serialize writers.
    """
    def __init__(self, config, site, stream, delay=1.5):
        self.config, self.site, self.stream, self.delay = config, site, stream, delay
        with mysql_connect(config, config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute('''CREATE TABLE IF NOT EXISTS source_payload_cache (
                    site_slug VARCHAR(100) NOT NULL, request_fingerprint CHAR(64) NOT NULL,
                    url TEXT NOT NULL, payload_json JSON NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(site_slug,request_fingerprint)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')

    def get(self, url, extract):
        fingerprint = build_request_fingerprint('GET', url, namespace=self.stream)
        with mysql_connect(self.config,self.config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT payload_json FROM source_payload_cache WHERE site_slug=%s AND request_fingerprint=%s',
                               (self.site,fingerprint))
                row = cursor.fetchone()
        if row:
            return json.loads(row['payload_json'])
        status, final_url, body = fetch_text(url)
        result = {'status':status,'url':final_url,'data':extract(body)}
        with mysql_connect(self.config,self.config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO source_payload_cache(site_slug,request_fingerprint,url,payload_json) VALUES(%s,%s,%s,%s)',
                               (self.site,fingerprint,url,json.dumps(result,ensure_ascii=False)))
        time.sleep(max(0,self.delay))
        return result


def product_data(body):
    soup = BeautifulSoup(body,'html.parser')
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.string or script.get_text())
        except ValueError:
            continue
        nodes = value if isinstance(value,list) else value.get('@graph',[value])
        for node in nodes:
            if node.get('@type') != 'Product':
                continue
            offer = node.get('offers') or {}
            if not isinstance(offer,dict):
                raise SourceAccessError('ambiguous Product offers; refusing price guess')
            return {'id':node.get('sku'),'title':node.get('name'),'model':node.get('model'),
                    'manufacturer':(node.get('brand') or {}).get('name'),
                    'category':node.get('category'),'description':node.get('description'),
                    'price':offer.get('price'),'currency':offer.get('priceCurrency'),
                    'url':node.get('url') or offer.get('url'),
                    'year':str(node.get('productionDate') or '')[:4] or None,
                    'createdAt':node.get('datePublished'),
                    'sellerName':(offer.get('seller') or {}).get('name'),
                    'availability':offer.get('availability'),
                    'image':node.get('image'),'priceBasis':'source_offer',
                    'country':((offer.get('seller') or {}).get('address') or {}).get('addressCountry')}
    raise SourceAccessError('Product JSON-LD missing; checkpoint retained')


def plant_url(_segment, page, minimum_usd):
    return 'https://www.plantandequipment.com/api/web/v1/search?' + urlencode({
        'industry[]':4,'price_min':minimum_usd,'locale':'en','listings':'premium',
        'page':page,'currency':'USD','sortby':'posted_at_desc'})


def plant_list_data(body):
    try:
        data = json.loads(body)
        items = data['listings']
        pages = int(data['filters']['pages_count'])
        current = int(data['filters']['current_page'])
        if not isinstance(items,list):
            raise TypeError('listings is not an array')
        return {'items':[item for item in items if item.get('type')=='listing'],
                'page':current,'pages':pages}
    except (KeyError,ValueError,TypeError) as error:
        raise SourceAccessError('Plant & Equipment search JSON shape changed') from error


def fetch_plant(segment, page, minimum_usd, cache):
    url = plant_url(segment,page,minimum_usd)
    response = cache.get(url,plant_list_data)
    data = response['data']
    if data['page'] != page:
        raise SourceAccessError('Plant & Equipment ignored requested page')
    result = []
    for item in data['items']:
        # Auction cards/ads can be promoted into classifieds: never import them.
        if not item.get('price') or item.get('source')=='live_auction' or item.get('is_make_offer'):
            continue
        detail = urljoin('https://www.plantandequipment.com',item.get('listing_url') or '')
        if not detail.startswith('https://www.plantandequipment.com/equipment-items/'):
            raise SourceAccessError('unexpected Plant & Equipment detail URL')
        product = cache.get(detail,product_data)['data']
        if str(product.get('id')) != str(item['id']):
            raise SourceAccessError('Plant & Equipment product identity mismatch')
        if product.get('availability') != 'https://schema.org/InStock':
            continue
        result.append({**product, 'year':item.get('year'), 'title':item.get('title'),
                       'location':item.get('country'),'hours':item.get('used_amount') if item.get('used_unit')=='hour' else None,
                       'crawlUrl':url, 'listDisplayPrice':item.get('price'),
                       'listDisplayCurrency':item.get('currency')})
    return FetchResult(response['url'],response['status'],result,page < data['pages'])


EUROPE_CATEGORIES = {
    'excavator':'/used-excavator/2-1/excavator-ads.html',
    'loader':'/used-loader/2-3/loader-ads.html',
    'backhoe':'/used-backhoe-loaders/2-2/backhoe-loaders-ads.html',
}


def europe_url(category,page):
    return 'https://www.europe-construction-equipment.com'+EUROPE_CATEGORIES[category]+'?'+urlencode({'pr':1,'p':page})


def europe_list_data(body):
    soup = BeautifulSoup(body,'html.parser')
    cards = soup.select('.vehicle[data-vehicule]')
    if not cards:
        raise SourceAccessError('Europe Construction Equipment listing markup missing')
    items = []
    for card in cards:
        info = card.select_one('[data-json]')
        try:
            sale = json.loads(info['data-json']) if info else {}
        except ValueError as error:
            raise SourceAccessError('Europe listing sale metadata changed') from error
        if not sale.get('sale') or sale.get('bid') or not card.get('data-price'):
            continue
        title = card.select_one('.card-title')
        location = card.select_one('.geolocalisation')
        items.append({'id':card['data-vehicule'],'url':card.get('data-href'),
                      'title':clean_text(title.get_text(' ')) if title else None,
                      'location':clean_text(location.get_text(' ')) if location else None})
    next_page = soup.select_one('.btn-next-pagination[data-next]:not(.disabled)')
    return {'items':items,'nextPage':int(next_page.get('data-next') or 0) if next_page else 0}


def fetch_europe(segment,page,cache):
    url = europe_url(segment,page)
    response = cache.get(url,europe_list_data)
    result = []
    for item in response['data']['items']:
        detail = urljoin('https://www.europe-construction-equipment.com',item['url'])
        if not detail.startswith('https://www.europe-construction-equipment.com/'):
            raise SourceAccessError('unexpected Europe detail URL')
        product = cache.get(detail,product_data)['data']
        if str(product.get('id')) != str(item['id']):
            raise SourceAccessError('Europe product identity mismatch')
        if product.get('availability') != 'https://schema.org/InStock':
            continue
        result.append({**product,'title':item.get('title') or product.get('title'),
                       'location':item.get('location'),'crawlUrl':url})
    return FetchResult(response['url'],response['status'],result,response['data']['nextPage'] > page)
