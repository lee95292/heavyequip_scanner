# jigecha.kr

## 개요

- 사이트명: 지게차코리아 공용매물
- Origin: `http://jigecha.kr`
- 사이트 내 매물 수: 약 `7,392`건
- 확인한 대표 매물 URL: `http://jigecha.kr/kwa-sell_jigecha`, `http://www.jigecha.kr/kwa-sell_jigecha`
- 취급장비 정보: 중고 지게차 중심. 디젤식, 전동좌식, 전동입식, 톤수/제조사/지역별 지게차, 지게차 타이어, 배터리, 신차, 물류장비, 부품 메뉴 확인.
- 대표자/운영자 정보: 플랫폼 운영사 대표자 정보는 원본 CSV에서 분리 확인되지 않았습니다. 연결된 업체 행에는 광성중기매매상사, 금일중기매매상사, 대구중기매매상사, 대왕중기매매상사, 두산건기매매상사 등이 포함됩니다.
- 연결된 원본 업체: 광성중기매매상사, 금일중기매매상사, 대구중기매매상사, 대왕중기매매상사, 두산건기매매상사, 성도건설기계매매상사, 창성중기매매상사, 충남건설기계매매상사, 현대중장비매매상사
- 원본 CSV 대표전화: 062-944-7230, 031-848-9957, 054-976-8989, 031-355-5202, 055-338-0441, 054-262-9030, 032-561-5227, 041-546-7890, 061-724-5885

## API 정보

- API 성격: JSON API가 아니라 `HTML 목록 엔드포인트`입니다. `requests + BeautifulSoup` 방식으로 목록 HTML을 받아 매물 행과 상세 URL을 파싱하는 구조입니다.
- 단일 API 엔드포인트: `http://jigecha.kr/kwa-sell_jigecha`
- HTTP 메서드: `GET` 중심. 일부 검색 폼은 `POST`로도 제출되지만, 목록 URL은 쿼리 파라미터 조합으로 재현 가능합니다.
- 카테고리/게시판 파라미터: `SCH_category_4`, `SCH_category_1`, `SCH_category_3`
- 페이지네이션 파라미터: `PB_1483420906`
- 검색/필터 파라미터: `SCH_sido`, `search_value`, `SCH_category_4`, `SCH_category_1`, `SCH_category_3`, `SCH_gugun`, `SCH_open_date_1_year`, `SCH_open_date_1_month`, `SCH_open_date_1_DSF`, `SCH_open_date_2_year`, `SCH_open_date_2_month`, `SCH_open_date_2_DSF`, `SCH_etc_3_min`, `SCH_etc_3_max`
- 상세 매물 식별자: `path_suffix_id`
- 기간 파라미터: `SCH_open_date_1_year/month`, `SCH_open_date_2_year/month`가 기간/연식 범위 필터로 쓰입니다. 등록일 전용 파라미터인지는 추가 검증이 필요합니다.
- 예시 요청: `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=2`

## 특이사항

- 상세 매물은 query id가 아니라 `/kwa-sell_jigecha_v-{id}` 경로 패턴으로 연결됩니다.
- 같은 지게차코리아 엔진이 여러 서브도메인에 배포되어 있으므로, 이 문서는 해당 origin만 대상으로 합니다.
- 단일 엔드포인트에서 목록은 가져올 수 있지만 검색 폼은 hidden 필드(`board`, `flag`, `Q_STRING`, `P_SELF`, `VG_live_code`)를 함께 보내는 구조라 POST 검색 재현 시 세션/hidden 값 보존이 필요할 수 있습니다.
