# 태양중기매매상사

- 확인 URL: `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18`
- 매물 수 추정: `1522`
- 응답 형식 판단: `HTML 목록 + JS/Ajax 단서`
- 기본 목록 엔드포인트: `https://ty-heavyequipment.com/taeyang_product_list/`
- 현재 Query: `{"cat1": ["18"]}`

## 요청 파라미터 요약

- 카테고리/게시판: `cat1, cat2`
- 페이지네이션: `paged`
- 검색/필터: `smaker, syear, eyear, stx`
- 상세 ID: `id`

## 관찰된 파라미터 빈도

- `cat1`: 176
- `cat2`: 148
- `id`: 33
- `taeyang_custom`: 12
- `smaker`: 12
- `syear`: 12
- `eyear`: 12
- `stx`: 12
- `paged`: 12
- `user_id`: 2
- `action`: 1

## 폼 분석

- Form 1: `GET` `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18`
  - fields: `taeyang_custom`
  - text: 15개씩 보기 30개씩 보기 50개씩 보기 100개씩 보기
- Form 2: `GET` `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18`
  - fields: `cat1`, `cat2`, `smaker`, `syear`, `eyear`, `stx`
  - text: 1차분류 펌프카/믹서트럭 굴착기/어태치부속 덤프트럭/셀프로다 지게차/하이랜더 압롤/진게/물차 카고/냉동/탑차 크레인/카고크레인 로더/도저/페이로더 피니셔/롤러 콤푸/드릴/항타기 크락샤/배차플랜트 기타건설기계 트렉터/농기계 2차분류 굴착기 1.3 ㎥ 이상 굴착기 1.0 ㎥ 이상 굴착기 0.4 ㎥ 이상 굴착기 0.3 ㎥ 이하 미니굴착기 굴착기타이어식 어태치먼트
- Form 3: `POST` `https://ty-heavyequipment.com/taeyang_product_list/banner_pop2.html`
  - fields: `proc`, `goods_pid`, `gubun`, `point`, `period`, `pay_point`, `redir`, `sel_period`
  - text: 프라임 - 포인트 결제 보유포인트 0 p 기간 선택해주세요 1일 (1,000p) 2일 (2,000p) 3일 (3,000p) 4일 (4,000p) 5일 (5,000p) 6일 (6,000p) 7일 (7,000p) 8일 (8,000p) 9일 (9,000p) 10일 (10,000p) 11일 (11,000p) 12일 (12,000p) 13일 (13,000p) 14일
- Form 4: `POST` `https://ty-heavyequipment.com/wp-login.php`
  - fields: `log`, `pwd`, `rememberme`
  - text: 아이디 비밀번호 아이디저장 로그인 카카오로 로그인 회원가입 | ID/비밀번호 찾기

## 주요 경로/샘플

- `/taeyang_product_list/`: 212 links
  - `콘텐츠로 건너뛰기` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18#content`
  - `전체매물보기` -> `https://ty-heavyequipment.com/taeyang_product_list/`
  - `전체매물보기` -> `https://ty-heavyequipment.com/taeyang_product_list/`
- `/registration/`: 3 links
  - `회원가입` -> `https://ty-heavyequipment.com/registration/`
  - `회원가입` -> `https://ty-heavyequipment.com/registration/`
  - `회원가입` -> `https://ty-heavyequipment.com/registration/`
- `/login/`: 3 links
  - `로그인` -> `https://ty-heavyequipment.com/login/`
  - `로그인` -> `https://ty-heavyequipment.com/login/`
  - `로그인` -> `https://ty-heavyequipment.com/login/`
- `/mypage-advertisement-guide/`: 3 links
  - `광고안내/문의` -> `https://ty-heavyequipment.com/mypage-advertisement-guide/`
  - `광고안내/문의` -> `https://ty-heavyequipment.com/mypage-advertisement-guide/`
  - `광고안내/문의` -> `https://ty-heavyequipment.com/mypage-advertisement-guide/`
- `/`: 2 links
  - `` -> `https://ty-heavyequipment.com/`
  - `` -> `https://ty-heavyequipment.com/`
- `/%ea%b5%ac%ec%9d%b8%ea%b5%ac%ec%a7%81/`: 2 links
  - `구인구직` -> `https://ty-heavyequipment.com/%ea%b5%ac%ec%9d%b8%ea%b5%ac%ec%a7%81/`
  - `구인구직` -> `https://ty-heavyequipment.com/%ea%b5%ac%ec%9d%b8%ea%b5%ac%ec%a7%81/`
- `/%ec%a3%bc%ec%9a%94%ec%84%9c%eb%a5%98/`: 2 links
  - `주요서류` -> `https://ty-heavyequipment.com/%ec%a3%bc%ec%9a%94%ec%84%9c%eb%a5%98/`
  - `주요서류` -> `https://ty-heavyequipment.com/%ec%a3%bc%ec%9a%94%ec%84%9c%eb%a5%98/`
- `/%ec%82%ac%ec%9d%b4%ed%8a%b8qna/`: 2 links
  - `사이트Q&A` -> `https://ty-heavyequipment.com/%ec%82%ac%ec%9d%b4%ed%8a%b8qna/`
  - `사이트Q&A` -> `https://ty-heavyequipment.com/%ec%82%ac%ec%9d%b4%ed%8a%b8qna/`
- `/%ea%b3%b5%ec%a7%80%ec%82%ac%ed%95%ad/`: 2 links
  - `공지사항` -> `https://ty-heavyequipment.com/%ea%b3%b5%ec%a7%80%ec%82%ac%ed%95%ad/`
  - `공지사항` -> `https://ty-heavyequipment.com/%ea%b3%b5%ec%a7%80%ec%82%ac%ed%95%ad/`
- `/%ed%9a%8c%ec%82%ac%ec%86%8c%ea%b0%9c/`: 2 links
  - `회사소개` -> `https://ty-heavyequipment.com/%ed%9a%8c%ec%82%ac%ec%86%8c%ea%b0%9c/`
  - `회사소개` -> `https://ty-heavyequipment.com/%ed%9a%8c%ec%82%ac%ec%86%8c%ea%b0%9c/`

## 페이지네이션 샘플

- `2` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=2`
- `3` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=3`
- `4` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=4`
- `5` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=5`
- `6` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=6`
- `7` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=7`
- `8` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=8`
- `9` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=9`
- `10` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=10`
- `»` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=11`

## 카테고리 샘플

- `콘텐츠로 건너뛰기` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18#content`
- `펌프카/믹서트럭` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17`
- `믹서트럭` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17&cat2=23`
- `펌프카` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17&cat2=24`
- `기타차량` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17&cat2=25`
- `부속품` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17&cat2=26`
- `굴착기/어태치부속` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18`
- `굴착기 1.3 ㎥ 이상` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&cat2=27`
- `굴착기 1.0 ㎥ 이상` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&cat2=28`
- `굴착기 0.4 ㎥ 이상` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&cat2=29`
- `굴착기 0.3 ㎥ 이하` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&cat2=30`
- `미니굴착기` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&cat2=31`

## 스크립트/API 단서

- 외부 스크립트 수: `65`
- 인라인 스크립트 수: `35`
- `https://ty-heavyequipment.com/?wc-ajax=%%endpoint%%`
- `https://ty-heavyequipment.com/taeyang_product_list/  };  / Initialize Firebase  const app = initializeApp(firebaseConfig);  const analytics = getAnalytics(app);{`
- `https://ty-heavyequipment.com/taeyang_product_list/ );}lazyloadBackgroundObserver.unobserve( entry.target );}});}, { rootMargin: `
- `https://ty-heavyequipment.com/taeyang_product_list/ } );lazyloadBackgrounds.forEach( ( lazyloadBackground ) => {lazyloadBackgroundObserver.observe( lazyloadBackground );} );};const events = [`
- `https://ty-heavyequipment.com/taeyang_product_list/)) {                skipSpinner = true;            }        });        / 페이지 이동 시 스피너 표시        window.addEventListener(`
- `https://ty-heavyequipment.com/taeyang_product_list/).slick(sliderSettings);    }    / DOMContentLoaded 후 초기화    $(document).ready(function() {        initializeSlickSlider();    });    / 강제 리사이즈 처리    $(window).on(`
- `https://ty-heavyequipment.com/taeyang_product_list/);            / 탭 콘텐츠 표시            tabContents.forEach(function(content) {              content.classList.remove(`
- `https://ty-heavyequipment.com/taeyang_product_list/);            / 탭 활성화 클래스 토글            tabs.forEach(function(t) {              t.classList.remove(`
- `https://ty-heavyequipment.com/taeyang_product_list/);            if (!el) return;            var href = el.getAttribute(`
- `https://ty-heavyequipment.com/taeyang_product_list/);            if (subMenu) {              e.preventDefault(); / 링크 이동 방지              subMenu.classList.toggle(`
- `https://ty-heavyequipment.com/taeyang_product_list/);            }        });        / 페이지 로드(또는 bfcache 복원) 시 스피너 제거        window.addEventListener(`
- `https://ty-heavyequipment.com/taeyang_product_list/);            });            document.getElementById(tabId).classList.add(`
- `https://ty-heavyequipment.com/taeyang_product_list/);            });            this.classList.add(`
- `https://ty-heavyequipment.com/taeyang_product_list/);        gnbDp1Links.forEach(function(link) {          link.addEventListener(`
- `https://ty-heavyequipment.com/taeyang_product_list/);        menuToggle.addEventListener(`
- `https://ty-heavyequipment.com/taeyang_product_list/);        tabs.forEach(function(tab) {          tab.addEventListener(`
- `https://ty-heavyequipment.com/taeyang_product_list/);        var menu = document.getElementById(`
- `https://ty-heavyequipment.com/taeyang_product_list/);        var skipSpinner = false;        / tel:, mailto: 등 클릭 시 스피너 무시        document.addEventListener(`
- `https://ty-heavyequipment.com/taeyang_product_list/);    }, 500);});jQuery(document).ready(function($) {        var soldoutListingId = null;        / 판매완료 버튼 클릭 → 모달 열기        $(document).on(`
- `https://ty-heavyequipment.com/taeyang_product_list/, function() {            if (!soldoutListingId) return;            $.ajax({                url: ajax_actions_object.ajax_url,                type: `
- `https://ty-heavyequipment.com/taeyang_product_list/, function() {            if (spinner && !skipSpinner) {                spinner.classList.add(`
- `https://ty-heavyequipment.com/taeyang_product_list/, function() {            var tabId = this.getAttribute(`
- `https://ty-heavyequipment.com/taeyang_product_list/, function() {          menu.classList.toggle(`
- `https://ty-heavyequipment.com/taeyang_product_list/, function() {        var menuToggle = document.getElementById(`
- `https://ty-heavyequipment.com/taeyang_product_list/, function(e) {            var el = e.target.closest(`

## 검증 요청 샘플

- `200` `text/html; charset=UTF-8` `207508` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=2`
- `200` `text/html; charset=UTF-8` `205298` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=3`
- `200` `text/html; charset=UTF-8` `202415` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&cat2&smaker&syear&eyear&stx&paged=4`
- `200` `text/html; charset=UTF-8` `202598` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=18#content`
- `200` `text/html; charset=UTF-8` `283955` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17`
- `200` `text/html; charset=UTF-8` `161027` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17&cat2=23`
- `200` `text/html; charset=UTF-8` `279420` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17&cat2=24`
- `200` `text/html; charset=UTF-8` `149786` -> `https://ty-heavyequipment.com/taeyang_product_list/?cat1=17&cat2=25`

## 크롤링 메모

- 우선순위: 목록 URL의 query 파라미터를 조합해 페이지 단위 HTML을 수집한 뒤 상세 링크를 따라가는 방식.
- JSON API로 바로 응답하는 패턴은 현재 확인 페이지 기준 미검출. 스크립트 단서는 대부분 UI/검색 보조 또는 범용 AJAX로 보이며, 실제 매물 목록은 초기 HTML에 포함됩니다.
- 필수 추출 필드 후보: 상세URL, 제목/모델명, 제조사, 연식, 가격, 지역, 판매상/연락처, 등록일, 조회수, 카테고리, 거래상태.
