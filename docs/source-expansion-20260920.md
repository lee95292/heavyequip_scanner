# 국제 소스 확장 · 2026-09-20

## 적용 정책

- IronPlanet: 사용자 승인으로 등록일 미상 현재 게시 매물 수집. 건설기계, 공개 Buy Now 판매가격, 원화 1천만원 이상, 사이트당 최대 8천건. 현재 최고 제안/입찰가는 제외한다.
- `posted_at`/`posted_date`는 미상으로 보존한다. `crawled_at`은 실제 수집 시각이다. 연식·검사일·경매 종료일로 등록일을 만들지 않는다.
- 등록일 미상 매물은 가격/국가/모델 분포에 포함할 수 있고, 최근 등록 수/월별 등록 추이에는 항상 제외된다. 분석 화면에서 미상 포함 여부를 선택한다.
- Plant & Equipment, Europe Construction Equipment: 등록일 미상 현재 게시 매물 수집을 사용자 승인으로 활성화. 건설기계·판매가격 있음·원화 1천만원 이상, 초기 사이트별 최대 8천건. 등록일은 미상으로 보존하고 경매/임대/부품은 제외한다. 카탈로그 `allowUndated=true`, `readiness=collection_enabled`로 명시한다.
- 매일 05:00 KST 서버 워커 유지. 접근 거부는 반복 재시도하지 않고 다음 정기 실행에서 확인한다. DB/구현 오류는 기존 체크포인트로 재시도한다.

## 확인한 요청

모두 HTTPS/443, GET. 실제 수집은 config의 지정 HTTP 프록시만 사용하며 직접 접속 fallback은 없다. 자격증명은 문서/배포물에 포함하지 않는다.

| 사이트 | 확인한 표면 | 현재 검증 |
| --- | --- | --- |
| IronPlanet | `/marketplace-mpe-construction`, HTML `quickviews.push(JSON)` | 첫 목록 200/60건. `/jsp/s/search.ips?ct=1&ms=M&sm=0&p_us=-1&pstart=0&prows=60` 가격 필터는 202. 별도 JSON XHR 미관찰 |
| Plant & Equipment | `/api/web/v1/search?industry[]=4&price_min=7200&locale=en&listings=premium&page=1&currency=USD&sortby=posted_at_desc` | 브라우저 XHR 및 프록시 200. minimum은 실행 환율에 따라 계산. 목록 표시가격 대신 상세 Product Offer의 통화/가격 사용 |
| Europe Construction Equipment | `/used-excavator/2-1/excavator-ads.html?pr=1&p=1` | 프록시 200. 목록 HTML 매매 유형 및 상세 Product JSON-LD. `pr=1` 가격 있음, 정확한 1천만원 조건은 변환 후 재검증 |
| Truck1 | `/construction-machinery/excavators` | 브라우저 ALTCHA, 지정 프록시 HTTP 202. 수집 미지원/차단 표시 |

## 재시작과 보존

- 기존 `source_request_log` fingerprint, `source_sync_item`, 사이트별 MySQL lock, 원자적 upsert/완료 체크포인트를 유지한다.
- 상세 보강이 필요한 신규 사이트는 `source_payload_cache`에 HTML 대신 작은 파싱 객체를 저장한다. 페이지 처리 실패 후 재시작해도 성공한 목록/상세 HTTP 요청은 캐시를 사용한다. 동일 사이트 내 고유 매물 ID로 중복 제거하며, 사이트 간 동일 장비를 임의로 합치지 않는다.
- 일일 스트림은 날짜별로 분리하여 가격 갱신 요청은 허용한다. 이전 데이터/국내 매물/정규화 사전/월별 환율 배치는 삭제하거나 초기화하지 않는다.
- 두 신규 사이트의 초기 수집 스트림 키는 `inventory:plant_equipment-approved-20260920`, `inventory:europe_construction-approved-20260920`으로 고정한다. 재실행 시 동일 키를 사용한다. 등록일이 실제 제공되는 매물에는 기존 날짜 정책이 유지된다.
- 신규 HTML 파서 의존성: `beautifulsoup4` (로컬/원격 설치 확인).

## 테스트

활성화 전 로컬 MySQL 포함 Python 48건, 분석 Node 7건 통과. 등록일 미상 예외와 기본 거부, 실제 수집 시각, 재실행 무요청, 상세 캐시 재사용, 체크포인트 실패 rollback, native/display 통화 분리, 입찰가 제외, unknown-date 차트 분리를 검증했다. 활성화 변경에는 승인된 세 사이트의 등록일 미상 정책과 일일 수집 대상 포함 회귀 테스트를 추가했다.

배포 직후 IronPlanet 첫 목록에서 조건에 맞는 17건 저장 확인. 두 번째 목록은 HTTP 202 차단으로 중단됐다. 사이트 원문 모델 토큰은 `model_name`에 보존하며, 공식 사전과 일치하지 않으면 `model_norm`에 임의로 채우지 않는다. 현재 17건의 정규화 모델 일치는 0건이다.
