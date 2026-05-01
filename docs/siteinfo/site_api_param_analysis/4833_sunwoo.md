# 선우중장비매매상사

- 확인 URL: `http://www.4833.com/Machine/RecomList.asp?MType=18`
- 매물 수 추정: `101`
- 응답 형식 판단: `HTML 목록 + JS/Ajax 단서`
- 기본 목록 엔드포인트: `http://www.4833.com/Machine/RecomList.asp`
- 현재 Query: `{"MType": ["18"]}`

## 요청 파라미터 요약

- 카테고리/게시판: `MType`
- 페이지네이션: `Page, page`
- 검색/필터: `MSort, MModel`
- 상세 ID: `Idx`

## 관찰된 파라미터 빈도

- `MType`: 254
- `MSort`: 228
- `MMaker`: 82
- `MModel`: 82
- `Page`: 80
- `Idx`: 80
- `page`: 2

## 폼 분석

- Form 1: `GET` `http://www.4833.com/Machine/RecomList.asp?MType=18`
  - fields: `MType`, `MSort`, `MMaker`, `MModel`
  - text: 장비종류 장비구분 제작사 모델명 전체 굴삭기 로우더 운반차.추래라.셀프로다.살수차 덤프트럭 지게차.고소작업차 불도저 레미콘 콘크리트장비 크레인 도로포장장비 특수장비 작업장치/부속 기타 전체 전체 두산 (DOOSAN) 볼보 (VOLVO) 현대 (HYUNDAI) 삼성 (SAMSUNG) 대우 (DAEWOO) 한라 (HALLA) 얀마(YANMAR) 캐타필라 (CA

## 주요 경로/샘플

- `/Machine/RecomList.asp`: 87 links
  - `전체보기 (101)` -> `http://www.4833.com/Machine/RecomList.asp`
  - `굴삭기 (56)` -> `http://www.4833.com/Machine/RecomList.asp?MType=18`
  - `로우더 (2)` -> `http://www.4833.com/Machine/RecomList.asp?MType=22`
- `/Machine/UserList.asp`: 87 links
  - `전체보기 (420506)` -> `http://www.4833.com/Machine/UserList.asp`
  - `굴삭기 (45928)` -> `http://www.4833.com/Machine/UserList.asp?MType=18`
  - `로우더 (5625)` -> `http://www.4833.com/Machine/UserList.asp?MType=22`
- `/Machine/recomView.asp`: 80 links
  - `` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
  - `굴삭기 0.4~0.9㎥이하 06 ㎥` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
  - `현대 (HYUNDAI) HX145CR` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
- `/Machine/recomList.asp`: 3 links
  - `` -> `http://www.4833.com/Machine/recomList.asp`
  - `2` -> `http://www.4833.com/Machine/recomList.asp?page=2&MType=18&MSort=&MMaker=&MModel=`
  - `3` -> `http://www.4833.com/Machine/recomList.asp?page=3&MType=18&MSort=&MMaker=&MModel=`
- `/Board/FindCarList.asp`: 1 links
  - `찾는매물리스트` -> `http://www.4833.com/Board/FindCarList.asp`
- `/Board/FindEmpList.asp`: 1 links
  - `구인리스트` -> `http://www.4833.com/Board/FindEmpList.asp`
- `/Board/FindJobList.asp`: 1 links
  - `구직리스트` -> `http://www.4833.com/Board/FindJobList.asp`
- `/Board/NewsList.asp`: 1 links
  - `중장비 뉴스` -> `http://www.4833.com/Board/NewsList.asp`
- `/Board/FreeList.asp`: 1 links
  - `자유게시판` -> `http://www.4833.com/Board/FreeList.asp`

## 페이지네이션 샘플

- `` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
- `굴삭기 0.4~0.9㎥이하 06 ㎥` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
- `현대 (HYUNDAI) HX145CR` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
- `2016.5 A++` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
- `` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445219&MType=18&MSort=&MMaker=&MModel=`
- `굴삭기 0.3㎥이하 03 ㎥` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445219&MType=18&MSort=&MMaker=&MModel=`
- `구보다(KUBOTA) KX060-5` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445219&MType=18&MSort=&MMaker=&MModel=`
- `2022 10 A++` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445219&MType=18&MSort=&MMaker=&MModel=`
- `` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445217&MType=18&MSort=&MMaker=&MModel=`
- `굴삭기 0.3㎥이하 03 ㎥` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445217&MType=18&MSort=&MMaker=&MModel=`

## 카테고리 샘플

- `굴삭기 (56)` -> `http://www.4833.com/Machine/RecomList.asp?MType=18`
- `로우더 (2)` -> `http://www.4833.com/Machine/RecomList.asp?MType=22`
- `운반차.추래라.셀프로다.살수차 (13)` -> `http://www.4833.com/Machine/RecomList.asp?MType=23`
- `덤프트럭 (7)` -> `http://www.4833.com/Machine/RecomList.asp?MType=19`
- `지게차.고소작업차 (1)` -> `http://www.4833.com/Machine/RecomList.asp?MType=21`
- `불도저 (0)` -> `http://www.4833.com/Machine/RecomList.asp?MType=108`
- `레미콘 (0)` -> `http://www.4833.com/Machine/RecomList.asp?MType=20`
- `콘크리트장비 (0)` -> `http://www.4833.com/Machine/RecomList.asp?MType=117`
- `크레인 (0)` -> `http://www.4833.com/Machine/RecomList.asp?MType=122`
- `도로포장장비 (2)` -> `http://www.4833.com/Machine/RecomList.asp?MType=109`
- `특수장비 (2)` -> `http://www.4833.com/Machine/RecomList.asp?MType=91`
- `작업장치/부속 (17)` -> `http://www.4833.com/Machine/RecomList.asp?MType=24`

## 스크립트/API 단서

- 외부 스크립트 수: `3`
- 인라인 스크립트 수: `2`
- `http://www.4833.com/Machine/;}/--><!--var groups= document.SearchFrm.MType.options.lengthvar group=new Array(groups)for (i=0; i<groups; i++)group[i]=new Array()/그룹1group[0][0]=new Option(`

## 검증 요청 샘플

- `200` `text/html; Charset=utf-8` `54645` -> `http://www.4833.com/Machine/recomView.asp?Page=1&Idx=445220&MType=18&MSort=&MMaker=&MModel=`
- `200` `text/html; Charset=utf-8` `73773` -> `http://www.4833.com/Machine/RecomList.asp?MType=18`
- `200` `text/html; Charset=utf-8` `57723` -> `http://www.4833.com/Machine/RecomList.asp?MType=22`
- `200` `text/html; Charset=utf-8` `67906` -> `http://www.4833.com/Machine/RecomList.asp?MType=23`
- `200` `text/html; Charset=utf-8` `62143` -> `http://www.4833.com/Machine/RecomList.asp?MType=19`
- `200` `text/html; Charset=utf-8` `56886` -> `http://www.4833.com/Machine/RecomList.asp?MType=21`

## 크롤링 메모

- 우선순위: 목록 URL의 query 파라미터를 조합해 페이지 단위 HTML을 수집한 뒤 상세 링크를 따라가는 방식.
- JSON API로 바로 응답하는 패턴은 현재 확인 페이지 기준 미검출. 스크립트 단서는 대부분 UI/검색 보조 또는 범용 AJAX로 보이며, 실제 매물 목록은 초기 HTML에 포함됩니다.
- 필수 추출 필드 후보: 상세URL, 제목/모델명, 제조사, 연식, 가격, 지역, 판매상/연락처, 등록일, 조회수, 카테고리, 거래상태.
