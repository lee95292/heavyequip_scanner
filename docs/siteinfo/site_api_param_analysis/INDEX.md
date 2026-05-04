# 중장비 매물 사이트 API/요청 파라미터 분석

|순위|사이트|매물수 추정|응답|기본 엔드포인트|파일|
|---:|---|---:|---|---|---|
|1|4396200.com 그린중기 공용매물|7700|HTML 목록 + JS/Ajax 단서|`https://www.4396200.com/sub8_1_s.html`|[4396200_green_heavy.md](4396200_green_heavy.md) / [4396200_green_heavy.json](4396200_green_heavy.json)|
|2|지게차코리아 공용매물|7392|HTML 목록 + JS/Ajax 단서|`http://jigecha.kr/kwa-sell_jigecha`|[jigecha_korea.md](jigecha_korea.md) / [jigecha_korea.json](jigecha_korea.json)|
|3|태양중기매매상사|1522|HTML 목록 + JS/Ajax 단서|`https://ty-heavyequipment.com/taeyang_product_list/`|[ty_heavyequipment.md](ty_heavyequipment.md) / [ty_heavyequipment.json](ty_heavyequipment.json)|
|4|서울중기매매상사|179|HTML 목록 + JS/Ajax 단서|`https://www.2963566.com/bbs/board.php`|[2963566_seoul.md](2963566_seoul.md) / [2963566_seoul.json](2963566_seoul.json)|
|5|삼성중기매매상사|118|HTML 목록 + JS/Ajax 단서|`https://www.3dump.co.kr/bbs/board.php`|[3dump_samsung.md](3dump_samsung.md) / [3dump_samsung.json](3dump_samsung.json)|
|6|선우중장비매매상사|101|HTML 목록 + JS/Ajax 단서|`http://www.4833.com/Machine/RecomList.asp`|[4833_sunwoo.md](4833_sunwoo.md) / [4833_sunwoo.json](4833_sunwoo.json)|
|7|퍼펙트82중장비|100|HTML 목록 + JS/Ajax 단서|`https://www.perfect82.com/fnew100`|[perfect82.md](perfect82.md) / [perfect82.json](perfect82.json)|

기준: `heavy_equipment_unique_sites_sorted_2026-04-29.csv`에서 매물 수 추정 100건 이상 사이트.

## 추가 요청 사이트

|사이트|매물수 추정|응답|기본 엔드포인트|파일|
|---|---:|---|---|---|
|Mascus Korea|215(KR) / 244000(global)|JSON API|`https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets`|[mascus_korea.md](mascus_korea.md) / [mascus_korea.json](mascus_korea.json)|
|중기114|300|HTML 목록|`https://중기114.com/product`|[junggi114.md](junggi114.md) / [junggi114.json](junggi114.json)|
|BAND `www.band.us/band/69640559`|미확인|HTML 메타 + 인증 필요 JSON API|`https://api-kr.band.us/v2.0.0/get_posts_and_announcements`|[band_69640559.md](band_69640559.md) / [band_69640559.json](band_69640559.json)|
