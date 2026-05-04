# mascus.co.kr

## 개요

- 사이트명: Mascus Korea
- Origin: `https://mascus.co.kr` (`www.mascus.co.kr`는 같은 사이트로 정규화)
- 사이트 내 매물 수: 국내 판매자(`countries=KR`) 건설장비 기준 약 `215`건. 국가 제한 없는 Mascus 건설장비 전체 카탈로그는 약 `244,000`건입니다.
- 확인한 대표 매물 URL: `https://www.mascus.co.kr/search?catalogs=construction&countries=KR`, `https://www.mascus.co.kr/중고-건설장비/굴삭기?countries=KR`
- 취급장비 정보: 건설장비, 굴삭기, 크레인, 고소작업대, 덤프, 로더, 도저, 도로건설장비, 발전기, 롤러, 드릴링 장비, 부품/어태치먼트, 농기계, 운송장비, 지게차/물류장비 등.
- 대표자/운영자 정보: Mascus는 Ritchie Bros. 계열 글로벌 중장비 거래 플랫폼입니다. Mascus Korea 공식 관리 기업은 CETEC/씨텍으로 확인되며, CETEC 표기 기준 대표자 배석호, 사업자번호 106-08-47804, Tel 02-6334-2480입니다.
- 국내 주요 카테고리 확인 수: 굴삭기 56건, 크레인 94건, 로더 21건, 덤프 3건.

## API 정보

- API 성격: `JSON API`입니다. 검색 HTML도 `__NEXT_DATA__`에 결과를 포함하지만, 실제 목록 갱신에는 아래 `SearchAssets` API가 사용됩니다.
- 단일 API 엔드포인트: `https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets`
- HTTP 메서드: `POST`
- 필수/권장 헤더: `Content-Type: application/json`, `hostname: www.mascus.co.kr`, `reqfor: env:browser:for:searchResults`
- 카테고리/게시판 파라미터: `catalogs`, `categories`, `subcategories`
- 페이지네이션 파라미터: `page`, `pagesize`
- 검색/필터 파라미터: `countries`, `companyregion`, `brands`, `models`, `freetext`, `price`, `meterreadouthours`, `engineoutput`, `accessorylist`, `withimage`, `withvideo`, `usercurrency`, `sortby`, `sortascending`
- 상세 매물 식별자: `productId`, `assetUrl`
- 기간 파라미터: `lastcreateddays`가 최근 등록 필터로 쓰입니다. UI에서 1/3/7/14/30일 옵션을 제공합니다. 연식 범위는 `yearofmanufacture` 계열 range 값으로 처리됩니다.
- 예시 요청:

```bash
curl -X POST 'https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets' \
  -H 'Content-Type: application/json' \
  -H 'hostname: www.mascus.co.kr' \
  -H 'reqfor: env:browser:for:searchResults' \
  --data '{"catalogs":["construction"],"countries":["KR"],"pagesize":40,"page":1,"usercurrency":"KRW"}'
```

## 특이사항

- API 엔드포인트 origin은 `mascus.co.kr`가 아니라 AWS API Gateway입니다. 사이트 기준 문서는 `mascus.co.kr`로 묶되, 실제 수집은 `SearchAssets`를 호출하는 것이 안정적입니다.
- `countries=KR`를 빼면 전 세계 Mascus 건설장비가 수집됩니다. 한국 매물만 필요하면 반드시 `countries: ["KR"]`를 넣어야 합니다.
- HTML 기반 백업 수집도 가능하지만 Next.js SSR 데이터와 무한스크롤 로직이 섞여 있어 JSON API가 더 좋습니다.
