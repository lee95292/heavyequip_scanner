# ty-heavyequipment.com

## 개요

- 사이트명: 태양중기매매상사
- Origin: `https://ty-heavyequipment.com`
- 사이트 내 매물 수: 약 `1,522`건
- 확인한 대표 매물 URL: `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18`, `https://ty-heavyequipment.com/taeyang_product_list/`
- 취급장비 정보: 굴착기/어태치부속, 덤프트럭/셀프로다, 지게차/하이랜더, 압롤/진게/물차, 카고/냉동/탑차, 크레인/카고크레인, 로더/도저/페이로더, 피니셔/롤러, 콤푸/드릴/항타기, 크락샤/배차플랜트, 기타건설기계, 트렉터/농기계
- 대표자/운영자 정보: 원본 CSV 기준: 태양중기매매상사, 대표자 민경래, 대표전화 1566-1329, 상담전화 010-5413-8949, 사업자등록번호 122-01-42006, 소재지 인천광역시 계양구.
- 연결된 원본 업체: 태양중기매매상사, 삼일중기
- 원본 CSV 대표전화: 1566-1329

## API 정보

- API 성격: JSON API가 아니라 `HTML 목록 엔드포인트`입니다. `requests + BeautifulSoup` 방식으로 목록 HTML을 받아 매물 행과 상세 URL을 파싱하는 구조입니다.
- 단일 API 엔드포인트: `https://ty-heavyequipment.com/taeyang_product_list/`
- HTTP 메서드: `GET` 중심. 일부 검색 폼은 `POST`로도 제출되지만, 목록 URL은 쿼리 파라미터 조합으로 재현 가능합니다.
- 카테고리/게시판 파라미터: `cat1`, `cat2`
- 페이지네이션 파라미터: `paged`
- 검색/필터 파라미터: `smaker`, `syear`, `eyear`, `stx`
- 상세 매물 식별자: `id`
- 기간 파라미터: 등록일 기준 기간 파라미터는 확인되지 않았습니다. `syear`, `eyear`는 장비 연식 범위로 보입니다.
- 예시 요청: `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&paged=2`

## 특이사항

- 목록과 상세가 같은 `/taeyang_product_list/` 엔드포인트를 사용하며, 상세는 `id` 파라미터로 구분됩니다.
- `taeyang_custom`은 페이지당 노출 수로 보이며 15/30/50/100 옵션이 확인됩니다.
- 사이트 내 스크립트/Ajax 단서는 있으나 매물 목록은 초기 HTML에 포함됩니다.
