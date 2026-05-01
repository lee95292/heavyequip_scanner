# 삼성중기매매상사

- 확인 URL: `https://www.3dump.co.kr/bbs/board.php?bo_table=m01_01&ca_id=20b0`
- 매물 수 추정: `118`
- 응답 형식 판단: `HTML 목록 + JS/Ajax 단서`
- 기본 목록 엔드포인트: `https://www.3dump.co.kr/bbs/board.php`
- 현재 Query: `{"bo_table": ["m01_01"], "ca_id": ["20b0"]}`

## 요청 파라미터 요약

- 카테고리/게시판: `ca_id, bo_table`
- 페이지네이션: `p`
- 검색/필터: `sKeyword, sop, stx`
- 상세 ID: `wr_id`

## 관찰된 파라미터 빈도

- `ca_id`: 942
- `bo_table`: 860
- `wr_id`: 708
- `hid`: 6
- `url`: 1
- `ci`: 1
- `type`: 1

## 폼 분석

- Form 1: `POST` `https://www.3dump.co.kr/bbs/board_list_update.php`
  - fields: `bo_table`, `sw`
  - text: 분류 사진 구분 제작사 모델명 연식 상태 예상가격 위치 작성자 등록일자 조회수 일반매물 팝니다 현대 HX400A붐대 제작사 : 현대 연식 : 22.07 예상가격 : 1,100만원 위치 : 경북 2026.04.06 6 22.07 A+ 1,100만원 경북 박미희 04.06 6 일반매물 팝니다 기타 텐파일드라이버 제작사 : 기타 연식 : 25.02 예상가격 : 
- Form 2: `GET` `https://www.3dump.co.kr/bbs/board.php`
  - fields: `bo_table`, `ca_id`, `p`, `sCate1`, `sCate2`, `sCate3`, `chk_1`, `chk_2`, `chk_3`, `sKeyword`
  - text: 제작사 현대 강토 경원 고흥 광림 국산 국제 금호 기아 닛산 대광 대농 대모 대신 대우 대운 대원ENG 대한 동남 동양 동일 두산 두성 두인중공업 미쓰비시 바지선 벤츠 볼보 부광 삼성 삼영 선별기 수산 수양 스미또모 아메리칸 아시아 얀마 에버다임 연합정밀 영원 옥진 외제 유림 유원 유타니 전진 지산 진명 카토 캐타필라 코마스 코벨코 태성 한국 한길 한라 한
- Form 3: `GET` `https://www.3dump.co.kr/bbs/board.php?bo_table=m01_01&ca_id=20b0`
  - fields: `url`, `sop`, `stx`
  - text: 게시물 상품 후기 문의 태그 또는 그리고
- Form 4: `POST` `https://www.3dump.co.kr/bbs/login_check.php`
  - fields: `url`, `mb_id`, `mb_password`, `auto_login`
  - text: Login 자동로그인 및 로그인 상태 유지

## 주요 경로/샘플

- `/bbs/board.php`: 855 links
  - `장비매매업체` -> `https://www.3dump.co.kr/bbs/board.php?bo_table=m02_01`
  - `판매/구매문의` -> `https://www.3dump.co.kr/bbs/board.php?bo_table=m03_01`
  - `일감주고받기` -> `https://www.3dump.co.kr/bbs/board.php?bo_table=m04_01`
- `/shop/list.php`: 116 links
  - `믹서트럭/펌프카` -> `https://www.3dump.co.kr/shop/list.php?ca_id=2010`
  - `믹서트럭` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201010`
  - `펌프카` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201020`
- `/bbs/page.php`: 6 links
  - `회사소개` -> `https://www.3dump.co.kr/bbs/page.php?hid=intro`
  - `회사소개` -> `https://www.3dump.co.kr/bbs/page.php?hid=intro`
  - `회사소개` -> `https://www.3dump.co.kr/bbs/page.php?hid=intro`
- ``: 5 links
  - `` -> `https://www.3dump.co.kr`
  - `삼성중기매매상사` -> `https://www.3dump.co.kr`
  - `` -> `https://www.3dump.co.kr`
- `/bbs/write.php`: 5 links
  - `매물등록` -> `https://www.3dump.co.kr/bbs/write.php?bo_table=m01_01`
  - `매물등록` -> `https://www.3dump.co.kr/bbs/write.php?bo_table=m01_01`
  - `매물등록` -> `https://www.3dump.co.kr/bbs/write.php?bo_table=m01_01`
- `/bbs/register.php`: 3 links
  - `회원가입` -> `https://www.3dump.co.kr/bbs/register.php`
  - `회원가입` -> `https://www.3dump.co.kr/bbs/register.php`
  - `회원가입` -> `https://www.3dump.co.kr/bbs/register.php`
- `/`: 2 links
  - `BBS` -> `https://www.3dump.co.kr/?ci=1`
  - `` -> `http://www.3dump.co.kr/`
- `/shop/cart.php`: 2 links
  - `` -> `https://www.3dump.co.kr/shop/cart.php`
  - `장바구니` -> `https://www.3dump.co.kr/shop/cart.php`
- `/bbs/password_lost.php`: 2 links
  - `정보찾기` -> `https://www.3dump.co.kr/bbs/password_lost.php`
  - `아이디/비밀번호 찾기` -> `https://www.3dump.co.kr/bbs/password_lost.php`
- `/bbs/login.php`: 1 links
  - `로그인` -> `https://www.3dump.co.kr/bbs/login.php?url=%2Fbbs%2Fboard.php%3Fbo_table%3Dm01_01%26ca_id%3D20b0`

## 페이지네이션 샘플

- 페이지네이션 링크 미검출

## 카테고리 샘플

- `매물등록` -> `https://www.3dump.co.kr/bbs/write.php?bo_table=m01_01`
- `믹서트럭/펌프카` -> `https://www.3dump.co.kr/shop/list.php?ca_id=2010`
- `믹서트럭` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201010`
- `펌프카` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201020`
- `숏크리트/몰리/포터블` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201030`
- `덤프트럭/추레라` -> `https://www.3dump.co.kr/shop/list.php?ca_id=2020`
- `24톤 이상` -> `https://www.3dump.co.kr/shop/list.php?ca_id=202010`
- `16톤 이하` -> `https://www.3dump.co.kr/shop/list.php?ca_id=202020`
- `10톤 이하` -> `https://www.3dump.co.kr/shop/list.php?ca_id=202030`
- `트레일러` -> `https://www.3dump.co.kr/shop/list.php?ca_id=202040`
- `추레라` -> `https://www.3dump.co.kr/shop/list.php?ca_id=202050`
- `셀프로더` -> `https://www.3dump.co.kr/shop/list.php?ca_id=202060`

## 스크립트/API 단서

- 외부 스크립트 수: `16`
- 인라인 스크립트 수: `9`
- `https://www.3dump.co.kr/bbs/ && navigator.userAgent.search(`
- `https://www.3dump.co.kr/bbs/).width() + 21;if( $windowSize > 992 && $windowSize < 1250 ){$targetMenu.css({`
- `https://www.3dump.co.kr/bbs/);return false;}var f = document.getElementById(`
- `https://www.3dump.co.kr/bbs/);var $targetSize = $(`
- `https://www.3dump.co.kr/bbs/,function(){main.startAuto();});  });$(document).ready(function(){var $windowSize = $(window).width();var $targetMenu = $(`
- `https://www.3dump.co.kr/bbs/: $targetSize});}});$(window).resize(function(){var $windowSize = $(window).width();var $targetMenu = $(`
- `https://www.3dump.co.kr/bbs/: $targetSize});}});/*var agent = navigator.userAgent.toLowerCase();$(`
- `https://www.3dump.co.kr/bbs/board.php?bo_table=m01_01&ca_id=20b0#search-list`
- `https://www.3dump.co.kr/bbs/label.target_label`
- `https://www.3dump.co.kr/thema/Fivesense-basic/widget/miso-sidebar`

## 검증 요청 샘플

- `200` `text/html; charset=utf-8` `145422` -> `https://www.3dump.co.kr/bbs/write.php?bo_table=m01_01`
- `200` `text/html; charset=utf-8` `127775` -> `https://www.3dump.co.kr/shop/list.php?ca_id=2010`
- `200` `text/html; charset=utf-8` `128817` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201010`
- `200` `text/html; charset=utf-8` `130622` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201020`
- `200` `text/html; charset=utf-8` `130762` -> `https://www.3dump.co.kr/shop/list.php?ca_id=201030`

## 크롤링 메모

- 우선순위: 목록 URL의 query 파라미터를 조합해 페이지 단위 HTML을 수집한 뒤 상세 링크를 따라가는 방식.
- JSON API로 바로 응답하는 패턴은 현재 확인 페이지 기준 미검출. 스크립트 단서는 대부분 UI/검색 보조 또는 범용 AJAX로 보이며, 실제 매물 목록은 초기 HTML에 포함됩니다.
- 필수 추출 필드 후보: 상세URL, 제목/모델명, 제조사, 연식, 가격, 지역, 판매상/연락처, 등록일, 조회수, 카테고리, 거래상태.
