# 국가·모델 시장 탐색

실제 수요를 측정하는 구매 문의·판매 완료 데이터는 현재 없다. 매물 수는 공급량이며
대시보드는 국가별 조사 후보를 찾는 **대리지표**만 제공한다.

- 국가·모델·사이트·카테고리·등록 기간·연식·최소 표본 필터
- 국가 및 모델별 매물 수, 최근 30일 신규 등록, 국가×모델 매물 수/국가 내 점유율 히트맵
- 국가별 모델 순위: 매물 수, 최근 등록, 점유율, 집중도, 가격 중앙값, 타국 동일 모델 가격차
- 집중도 = 국가 내 해당 모델 비중 / 전체 정규화 표본에서 해당 모델 비중
- 가격차는 해당 국가를 제외한 타국 동일 모델 중앙값과 비교. 양쪽 모두 최소 표본 충족 시만 표시
- 동일 모델의 국가별 중앙값/사분위 범위, 등록월별 현재 보유 매물 분포, 근거 원문 링크
- 판매가격·상태·가동시간·물류/세금이 통제된 수익률이 아님. 미확인 모델/국가/등록일 제외 수를 노출

## CAT 모델

`docs/const/cat_models.json`에 Caterpillar 공식 제품 페이지·공식 부품 호환 목록에서 확인한
388개 코드를 출처와 함께 저장한다. `CAT320`, `CAT320GC`, `CAT308CRVAB`처럼 CAT 접두어를
사용하고 소수점은 보존한다. 기존 CSV는 별도로 유지하며 기존 CAT 구형 코드의 제조사 문맥도
보존한다. 공백을 전부 지워 문자열을 붙이지 않고 토큰 경계를 확인해 `349 Excavator`가
`349E`가 되지 않게 한다. 숫자 모델의 제목 매칭은 CAT 제조사/브랜드 문맥이 있어야 한다.
공식 부품 호환 목록의 구형 굴삭기·휠로더·도저·백호 세부 코드도 포함한다.
CAT 브랜드가 기록되어 있어도 타사 모델 계열에는 CAT 접두어를 붙이지 않는다.

## 추가 백필

```
python3 -m crawl.international.runner --mode backfill --site mascus_global \
  --days 365 --extend-by 8000 --expansion-key market-expansion-20260920 --sleep 1.5
```

Machineryline은 `--site machineryline`로 별도 실행할 수 있다. 기존
`backfill:construction-priced-v1` 요청 기록을 그대로 사용한다. 확장 실행 키는 재시작해도
바꾸지 않는다. `source_sync_extensions`가 시작 수량과 목표를 고정하고, 이미 DB에 있는
매물은 추가 8천 건에 포함하지 않는다. 매물/수집 항목/요청 완료/진행 카운터는 하나의
DB 트랜잭션으로 커밋한다. 사이트별 MySQL advisory lock이 일일 작업과의 동시 실행을 막는다.
국제 사이트 분석에서 전체 저장 건수와 별도로 이번 추가 수집 건수 / 8,000건을 표시한다.

Mascus 429/502/503/504 및 네트워크 오류는 페이지당 최대 3회 재시도하며, 실패한 분기는
완료로 표시하지 않는다. 가격 거절 매물만 나온 페이지를 날짜 한계로 오인하지 않는다.
Machineryline은 실제 `pgn-next` 링크로 마지막 페이지를 판단한다.

## IronPlanet 재검토 (2026-09-20)

- 원격 서버의 지정 프록시에서 `GET https://www.ironplanet.com/marketplace-mpe-construction` HTTP 200.
- 목록은 별도 JSON XHR가 아닌 HTML 안의 `quickviews.push({...})` JSON 60건으로 제공됐다.
- 관찰한 페이지네이션: `GET /jsp/s/search.ips?ct=1&ms=M&pstart=60&prows=60`.
- 관찰한 정렬: `sort=bm asc`, `p asc`, `p desc`, `d asc`, `ad asc`, `ad desc`, `yr desc`.
- `equipId`, `description`, `price`, `currency`, `flagPath`, `usage`, `itemPageUri`, `auctionType` 등은 확인.
- `registrationNu`는 장비 등록번호이며 등록일이 아님. `yr desc`는 제조연식, `ad`는 경매 일정.
- 목록 60건 및 상세 표본에 원본 등록일이 없어 최근 1년 정책 검증 불가. 현재 자동 수집은 보류.
- 관측일이나 경매 종료일을 등록일로 만들어 채우지 않는다. 향후 등록일 근거 또는 별도 정책 승인이 필요.
