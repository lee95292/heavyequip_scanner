# 지게차코리아 공용매물

- 확인 URL: `http://jigecha.kr/kwa-sell_jigecha`
- 매물 수 추정: `7392`
- 응답 형식 판단: `HTML 목록 + JS/Ajax 단서`
- 기본 목록 엔드포인트: `http://jigecha.kr/kwa-sell_jigecha`
- 현재 Query: `{}`

## 요청 파라미터 요약

- 카테고리/게시판: `SCH_category_4, SCH_category_1, SCH_category_3`
- 페이지네이션: `PB_1483420906`
- 검색/필터: `SCH_sido, search_value, SCH_category_4, SCH_category_1, SCH_category_3, SCH_gugun, SCH_open_date_1_year, SCH_open_date_1_month, SCH_open_date_1_DSF, SCH_open_date_2_year, SCH_open_date_2_month, SCH_open_date_2_DSF, SCH_etc_3_min, SCH_etc_3_max`
- 상세 ID: `path_suffix_id`

## 관찰된 파라미터 빈도

- `category_1`: 30
- `SCH_sido`: 16
- `PB_1483420906`: 12
- `prev_url`: 3
- `design_file`: 3
- `SCH_category_4`: 2
- `SI_F_open_date`: 2
- `SI_F_category_3`: 2
- `SI_F_category_4`: 2
- `SI_F_subject`: 2
- `SI_F_etc_3`: 2
- `OTSKIN`: 1
- `pc`: 1

## 폼 분석

- Form 1: `POST` `http://jigecha.kr/kwa-sch_total`
  - fields: `board`, `flag`, `http_referer`, `after_db_script`, `after_db_msg`, `Q_STRING`, `P_SELF`, `VG_live_code`, `page_dfg`, `search_value`
  - text: 검색 폼
- Form 2: `POST` `http://jigecha.kr/member/login_process.php`
  - fields: `after_db_script`, `after_db_msg`, `flag`, `Q_STRING`, `proc_mode`, `P_SELF`, `VG_live_code`, `page_dfg`, `user_id`, `user_passwd`, `submit_OK`, `save_user_id`, `save_user_passwd`
  - text: MEMBER LOGIN 아이디 비밀번호 아이디 저장 비밀번호 저장 회원가입 아이디/비밀번호찾기 소셜 네트워크 를 통한 간편 로그인
- Form 3: `POST` `http://jigecha.kr/board/article_write.php`
  - fields: `board`, `flag`, `http_referer`, `after_db_script`, `after_db_msg`, `is_cpy_article`, `cp_article_num`, `cp_article_file`, `Q_STRING`, `P_SELF`, `VG_live_code`, `page_dfg`, `writer_name`, `phone_2`, `category_1`, `comment_1`, `passwd`, `chk_person`, `insiter_agree_315`, `submit_OK`, `subject`, `is_private`, `category_6`, `T_insiter_join_agree`
  - text: 무료상담신청 신차/구매상담 임대/렌탈상담 지게차타이어상담 지게차배터리상담 대리점상담 개인정보처리방침동의 개인정보처리방침 보기 1599-9194 월~금요일 : 09:00~ 18:00 주말,공휴일 휴무
- Form 4: `POST` `http://jigecha.kr/kwa-sell_jigecha`
  - fields: `board`, `flag`, `http_referer`, `after_db_script`, `after_db_msg`, `Q_STRING`, `P_SELF`, `VG_live_code`, `page_dfg`, `SCH_category_1`, `onectg_tmp_category_1`, `SCH_category_4`, `SCH_category_3`, `SCH_sido`, `SCH_gugun`, `SCH_open_date_1_year`, `SCH_open_date_1_month`, `SCH_open_date_1_DSF`, `SCH_open_date_2_year`, `SCH_open_date_2_month`, `SCH_open_date_2_DSF`, `SCH_etc_3_min`, `SCH_etc_3_max`, `search_value`, `submit_OK`
  - text: 중고지게차 가격비교 서비스 디젤식지게차 전동식지게차 제조회사 :: 제조사 :: 타이탄 CROWN KOMATSU Maximal MITSUBISHI NICHIYU NISSAN SHINKO SUMITOMO TCM TOYOTA BYD 대우 동명 삼성 수성 클라크 현대 삼익하이코 두산 캐터필러 EP NYK 한라 기타 (주)홍진기업 국제농기계 Skyjack HANGC

## 주요 경로/샘플

- `/kwa-sell_jigecha`: 49 links
  - `지게차코리아 즐겨찾기` -> `http://jigecha.kr/kwa-sell_jigecha#;`
  - `중고지게차매매` -> `http://jigecha.kr/kwa-sell_jigecha`
  - `전동중고지게차 최저가 판매` -> `http://jigecha.kr/kwa-sell_jigecha`
- `/kwa-parts`: 11 links
  - `부품` -> `http://jigecha.kr/kwa-parts`
  - `TOYOTA부품` -> `http://jigecha.kr/kwa-parts?category_1=A`
  - `NICHIYU부품` -> `http://jigecha.kr/kwa-parts?category_1=B`
- `/kwa-jigecha_rental`: 8 links
  - `지게차임대/렌탈` -> `http://jigecha.kr/kwa-jigecha_rental`
  - `디젤식` -> `http://jigecha.kr/kwa-jigecha_rental?category_1=A`
  - `전동좌식` -> `http://jigecha.kr/kwa-jigecha_rental?category_1=C`
- `/kwa-tire`: 7 links
  - `타이어` -> `http://jigecha.kr/kwa-tire`
  - `솔리드` -> `http://jigecha.kr/kwa-tire?category_1=A`
  - `공기타이어` -> `http://jigecha.kr/kwa-tire?category_1=B`
- `/kwa-logistics`: 7 links
  - `물류장비` -> `http://jigecha.kr/kwa-logistics`
  - `전동스태커` -> `http://jigecha.kr/kwa-logistics?category_1=A`
  - `파렛트트럭` -> `http://jigecha.kr/kwa-logistics?category_1=B`
- `/kwa-sell_new`: 5 links
  - `신차판매` -> `http://jigecha.kr/kwa-sell_new`
  - `전동좌식 지게차` -> `http://jigecha.kr/kwa-sell_new?category_1=C`
  - `입식(MIMA) 지게차` -> `http://jigecha.kr/kwa-sell_new?category_1=D`
- `/kwa-jigecha_consult_w`: 5 links
  - `` -> `http://jigecha.kr/kwa-jigecha_consult_w?category_1=A`
  - `` -> `http://jigecha.kr/kwa-jigecha_consult_w?category_1=B`
  - `` -> `http://jigecha.kr/kwa-jigecha_consult_w?category_1=C`
- `/kwa-sell_jigecha_v-8508`: 4 links
  - `` -> `http://jigecha.kr/kwa-sell_jigecha_v-8508`
  - `도요다 전동입식..` -> `http://jigecha.kr/kwa-sell_jigecha_v-8508`
  - `` -> `http://jigecha.kr/kwa-sell_jigecha_v-8508`
- `/kwa-sell_jigecha_v-8507`: 4 links
  - `` -> `http://jigecha.kr/kwa-sell_jigecha_v-8507`
  - `도요다 전동입식..` -> `http://jigecha.kr/kwa-sell_jigecha_v-8507`
  - `` -> `http://jigecha.kr/kwa-sell_jigecha_v-8507`
- `/kwa-sell_jigecha_v-8493`: 4 links
  - `` -> `http://jigecha.kr/kwa-sell_jigecha_v-8493`
  - `현대 3.3톤 디젤..` -> `http://jigecha.kr/kwa-sell_jigecha_v-8493`
  - `` -> `http://jigecha.kr/kwa-sell_jigecha_v-8493`

## 페이지네이션 샘플

- `2` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=2`
- `3` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=3`
- `4` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=4`
- `5` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=5`
- `6` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=6`
- `7` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=7`
- `8` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=8`
- `9` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=9`
- `10` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=10`
- `` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=2`

## 카테고리 샘플

- `디젤식지게차` -> `http://jigecha.kr/kwa-sell_jigecha?SCH_category_4=A`
- `전동식지게차` -> `http://jigecha.kr/kwa-sell_jigecha?SCH_category_4=C+D`

## 스크립트/API 단서

- 외부 스크립트 수: `8`
- 인라인 스크립트 수: `1`
- `http://jigecha.kr/ + box_title;$.getScript(script_src);} else {var reset_obj = eval(`
- `http://jigecha.kr/ + vars.v.chi, vars.v.frm).val(vars.v.vh + vars.obj_chg.val());/ 마지막 선택상자 아니더라도 다음이 없는 경우 값 설정}});});function TCBOARD_board_LIST_indexIheaderDoTtphp14675_submit(obj, button_type) {errfld = `
- `http://jigecha.kr/) {if (form.target == `
- `http://jigecha.kr/);return false;}}function TCBOARD_sell_jigecha_LIST_index219_submit(obj, button_type) {errfld = `
- `http://jigecha.kr/, 28, 0);function SYSTEM_vote_article(obj, form, board, serial_num, target, q_str, r_url, chg_values, after_script, after_msg, frm_attr, alert_msg) {if (alert_msg == `
- `http://jigecha.kr/, board, serial_num, target, chg_values, q_str, after_script, after_msg, frm_attr, `
- `http://jigecha.kr/;submit_direct_ajax(obj, `
- `http://jigecha.kr/]);if (form.target == `
- `http://jigecha.kr/get`
- `http://jigecha.kr/kwa-sell_jigecha#loading_img`
- `http://jigecha.kr/search_item`
- `http://jigecha.kr/search_operator`
- `http://jigecha.kr/search_value`
- `http://jigecha.kr/select[-cll-id=ctg_link_TCBOARD_sell_jigecha_LIST_index219_category_1]`
- `http://jigecha.kr/};/ 새로고침 후에도 ajax 로딩 영역을 유지하기 위한 변수var post_to_get_qs = `

## 검증 요청 샘플

- `200` `text/html; charset=utf-8` `83706` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=2`
- `200` `text/html; charset=utf-8` `79752` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=3`
- `200` `text/html; charset=utf-8` `79745` -> `http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=4`
- `200` `text/html; charset=utf-8` `81057` -> `http://jigecha.kr/kwa-sell_jigecha?SCH_category_4=A`
- `200` `text/html; charset=utf-8` `96433` -> `http://jigecha.kr/kwa-sell_jigecha?SCH_category_4=C+D`

## 크롤링 메모

- 우선순위: 목록 URL의 query 파라미터를 조합해 페이지 단위 HTML을 수집한 뒤 상세 링크를 따라가는 방식.
- JSON API로 바로 응답하는 패턴은 현재 확인 페이지 기준 미검출. 스크립트 단서는 대부분 UI/검색 보조 또는 범용 AJAX로 보이며, 실제 매물 목록은 초기 HTML에 포함됩니다.
- 필수 추출 필드 후보: 상세URL, 제목/모델명, 제조사, 연식, 가격, 지역, 판매상/연락처, 등록일, 조회수, 카테고리, 거래상태.
