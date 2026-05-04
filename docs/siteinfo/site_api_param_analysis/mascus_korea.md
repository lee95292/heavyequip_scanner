# Mascus Korea API 요청 파라미터 분석

## 요약

- Origin: `https://mascus.co.kr`
- 매물 수: 국내 판매자 건설장비 `215`건, 국가 제한 없는 건설장비 전체 `244,000`건
- 응답 유형: `JSON API`
- 단일 엔드포인트: `https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets`

## 요청

```bash
curl -X POST 'https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets' \
  -H 'Content-Type: application/json' \
  -H 'hostname: www.mascus.co.kr' \
  -H 'reqfor: env:browser:for:searchResults' \
  --data '{"catalogs":["construction"],"countries":["KR"],"pagesize":40,"page":1,"usercurrency":"KRW"}'
```

## 파라미터

- 카테고리: `catalogs`, `categories`, `subcategories`
- 페이지: `page`, `pagesize`
- 검색/필터: `countries`, `companyregion`, `brands`, `models`, `freetext`, `price`, `meterreadouthours`, `engineoutput`, `accessorylist`, `withimage`, `withvideo`, `usercurrency`, `sortby`, `sortascending`
- 기간: `lastcreateddays`
- 연식: `yearofmanufacture`
- 상세 식별: `productId`, `assetUrl`

## 특이사항

- 한국 매물만 수집하려면 `countries: ["KR"]` 필터가 필수입니다.
- `lastcreateddays`는 최근 등록 필터이고, 등록일 시작/끝 날짜 범위 파라미터는 확인되지 않았습니다.
