# 국제 사이트 요청 재현

모든 크롤링 요청은 `crawl/config.json`의 `international.http_proxy` 또는
`INTERNATIONAL_HTTP_PROXY`를 사용한다. 프록시 인증정보는 명령 이력이나 문서에 직접
기록하지 않는다.

## 운영 코드와 동일하게 재현

아래 명령은 DB 체크포인트와 요청 로그까지 남긴다. `--stream-key`는 재현할 때마다 새
값을 사용한다.

```bash
python3 -m crawl.international.runner \
  --mode daily \
  --site machinery_trader \
  --limit 1 \
  --sleep 0 \
  --stream-key reproduce:machinery_trader:YYYYMMDD-HHMMSS
```

`--site`에는 `machinery_trader`, `machineryline`, `ironplanet`, `rb_auction`,
`mascus_global`을 사용할 수 있다.

## curl로 HTTP 응답만 재현

```bash
read -s PROXY_URL
export PROXY_URL

curl --proxy "$PROXY_URL" --compressed -i \
  -A 'Mozilla/5.0 (compatible; HeavyEquipScanner/1.0; +https://scan.mglee.dev)' \
  -H 'Accept: text/html,application/xhtml+xml' \
  -H 'Accept-Language: en-US,en;q=0.8' \
  'https://www.machinerytrader.com/listings/search?page=1'
```

사이트별 목록 URL은 다음과 같다.

- Machinery Trader: `https://www.machinerytrader.com/listings/search?page=1`
- Machineryline: `https://machineryline.com/-/construction-equipment--c85?page=1`
- IronPlanet: `https://www.ironplanet.com/jsp/s/search.ips?ct=1&p_can=-1&sm=0&sort=ad%20desc&pstart=0`
- Ritchie Bros.: `https://www.rbauction.com/cp/construction?from=0`
- Mascus: `https://www.mascus.com/construction/excavators?page=1&sortby=createddesc`

2026-09-19 지정 프록시 기준 Machineryline과 Mascus는 HTTP 200, Machinery Trader와
Ritchie Bros.는 HTTP 403, IronPlanet은 자동접근 챌린지 HTTP 202가 재현된다.

응답을 공유할 때는 상태 코드, 응답 헤더, 본문 앞부분만 전달하고 프록시 URL의
`user:password@` 부분과 쿠키는 반드시 제거한다.
