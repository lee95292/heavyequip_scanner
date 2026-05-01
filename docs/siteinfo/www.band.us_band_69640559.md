# www.band.us/band/69640559

## 개요

- 사이트명: BAND 예시 밴드 - 중장비마켓 중고농기계마켓
- Origin: `https://www.band.us/band/69640559`
- Origin 산정 방식: Band는 플랫폼형 서비스이므로 예외적으로 밴드 ID가 포함된 `/band/69640559`까지를 하나의 origin/source로 봅니다.
- 확인한 대표 페이지: `https://www.band.us/band/69640559`
- 사이트 내 매물 수: 공개 HTML만으로는 확인 불가
- 취급장비 정보: 페이지 메타 설명 기준 중고 미니굴삭기, 중고 장비, 중고 농기계, 미니 캐리어덤프, 고소작업대, 궤도고소작업대, 전동지게차, 얀마/구보다/히타치/코벨코/코마스/두산/현대 미니굴삭기, 굴삭기 어태치먼트, 로더/휠로더 등.
- 대표자/운영자 정보: 공개 HTML 메타에서는 밴드 운영자/대표자 정보가 확인되지 않았습니다.

## API 정보

- API 성격: 공개 HTML은 밴드명/설명 메타만 내려오며, 게시글/매물 목록은 인증이 필요한 `JSON API` 영역입니다.
- 단일 API 엔드포인트: 캡처된 웹 요청 기준 `https://api-kr.band.us/v2.0.0/get_posts_and_announcements`
- HTTP 메서드: `GET`
- 필수 파라미터: `band_no=69640559`
- 페이지네이션/커서 후보: `ts`
- 검색/필터 파라미터: `resolution_type`, `order_by`
- 인증 정보: Open API `access_token`은 요청 안에 평문으로 보이지 않습니다. 웹 내부 API는 `band_session` 등 쿠키와 `akey`, `md` 같은 서명/클라이언트 헤더로 인증됩니다. 민감값은 저장하지 않고 환경변수 또는 로컬 비밀 파일로만 주입해야 합니다.
- 상세 매물 식별자: 응답의 게시글 식별 필드 확인 필요. 공식 Open API 기준은 `post_key`이고, 웹 내부 API 응답은 `post_no` 계열 필드가 포함될 수 있습니다.
- 기간 파라미터: 명시적인 시작/끝 기간 파라미터는 확인되지 않았습니다. `order_by=created_at_desc`와 `ts` 커서로 페이지를 넘기고, 응답의 작성 시각 필드 기준으로 수집 종료 조건을 거는 방식이 적합합니다.
- 예시 요청:

```text
https://api-kr.band.us/v2.0.0/get_posts_and_announcements?ts={TIMESTAMP_MS}&band_no=69640559&resolution_type=4&order_by=created_at_desc
```

## 특이사항

- `https://openapi.band.us/v2/band/posts?band_key=69640559` 요청은 OAuth 인증 없이는 `unauthorized`를 반환했습니다.
- `https://api-kr.band.us/v2.0.0/get_band?band_no=69640559` 등 웹 내부 API도 비로그인 상태에서는 `You are not authorized.`를 반환했습니다.
- 사용자가 준 숫자 `69640559`는 웹 URL의 `band_no`로 보이며, 공식 Open API 수집에는 별도의 `band_key`가 필요할 수 있습니다. 먼저 OAuth로 접근 가능한 밴드 목록을 받은 뒤 해당 밴드의 `band_key`를 매핑해야 합니다.
- 사용자가 제공한 인증 cURL에는 Open API용 `access_token` 파라미터가 없습니다. `akey`, `md`, `band_session`, `as`, `ai`, `BBC`, `di`는 액세스 토큰이라기보다 웹 세션/서명 인증 재료로 보이며, 만료/계정 종속 가능성이 높습니다.
- Band는 `band.us`라는 단일 도메인 아래 수많은 밴드가 공존합니다. 이 프로젝트에서는 플랫폼 예외 규칙으로 `www.band.us/band/69640559`까지를 origin으로 취급하고, 수집 인증 후에는 `band_no=69640559` 또는 OAuth로 얻는 `band_key`를 함께 저장해야 합니다.
