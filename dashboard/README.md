# Dashboard

`crawl/config.json`의 MySQL 접속정보를 사용해 `heavyequip_scanner.listings` 레코드를 보여주는 Node + React 대시보드입니다.

## 실행

```bash
cd dashboard
npm install
npm run dev
```

- React: `http://localhost:5173`
- API: `http://localhost:5050/api/listings`

빌드된 파일을 Node 서버 하나로 띄우려면 아래처럼 실행합니다.

```bash
npm run build
npm start
```

- Dashboard: `http://localhost:5050`

## PM2 일일 크롤링

`ecosystem.config.cjs`는 대시보드, 가격 예측 API, 일일 크롤링 워커를 함께 실행합니다.

```bash
pm2 start ecosystem.config.cjs
pm2 startup
pm2 save
```

일일 워커는 기본적으로 매일 KST `02:00`에 최근 1일 목록을 추가하고, 이전 실행에서 남은
재시도 가능 `pending` 작업도 이어서 처리합니다. 작업이 세 번째로 실패하면 `failed`로
종료되어 이후 실행 대상에서 제외됩니다. 예약 시각 뒤에 서버가 재시작되더라도 당일 성공
기록이 없으면 즉시 보충 실행하고, 사이트 차단 등으로 실행이 일시 중단되면 15분 뒤 다시
이어갑니다.

- `CRAWL_DAILY_AT`: KST 실행 시각, 기본값 `02:00`
- `CRAWL_DAILY_MODE`: 크롤링 범위, 기본값 `1d`
- `CRAWL_DAILY_SLEEP`: 요청 간 기본 대기, 기본값 `1.5`
- `CRAWL_DAILY_RETRY_SECONDS`: 미완료 실행 재시도 간격, 기본값 `900`
- `CRAWL_DAILY_STATE_PATH`: 마지막 성공일을 기록할 파일 경로
- `CRAWL_DAILY_LOCK_PATH`: 중복 실행 방지 잠금 파일 경로
- `CRAWL_DAILY_RUN_ON_START`: `true`면 PM2 시작 직후 한 번 실행
- `CRAWL_CONFIG_PATH`: 크롤링 설정 파일 경로
- `CRAWL_PYTHON_BIN`: 크롤러를 실행할 Python 인터프리터 경로

스케줄을 기다리지 않고 한 번 검증하려면 저장소 루트에서 실행합니다.
PM2 일일 워커가 이미 실행 중이면 중복 크롤링을 막기 위해 이 명령은 종료됩니다.

```bash
python3 crawl/daily.py --run-once
```

## 가격 예측

상단의 `가격 예측` 탭에서 모델명을 검색해 suggestion을 선택하고 연식을 입력하면 최신
LightGBM 모델의 예상 게시가격을 확인할 수 있습니다. suggestion에는 학습 데이터의 대표
제조사·카테고리가 함께 들어 있어 `category_name`을 포함한 one-hot feature가 웹 예측에도
적용됩니다. 표시되는 하한·상한은 모델명+연식 입력 조건으로 별도 측정한 web-serving test
MAE를 가감한 참고 범위이며 통계적 신뢰구간은 아닙니다.

PM2 구성은 Python API를 외부에 직접 노출하지 않고 `127.0.0.1:5060`에만 실행합니다. Dashboard
Node API가 로그인 인증을 확인한 다음 로컬 예측 API를 프록시합니다. 실행 전에 prediction
의존성과 승격된 모델 bundle이 필요합니다.

Apple Silicon Mac에서는 x86_64 패키지가 섞인 전역 Python을 피하도록 저장소 루트의
`prediction/.venv`를 사용합니다. PM2는 이 경로가 있으면 자동으로 선택합니다.

```bash
export PATH="$PWD/prediction/.venv/bin:$PATH"
python3 -m prediction.service  # 저장소 루트에서 단독 점검할 때
```

- `PREDICTION_PYTHON_BIN`: 예측 API용 Python 인터프리터. 미지정 시
  `prediction/.venv/bin/python`이 있으면 우선 사용하고, 없으면 `python3` 사용
- `PREDICTION_API_PORT`: 로컬 예측 API 포트, 기본값 `5060`
- `PREDICTION_API_URL`: Dashboard가 호출할 예측 API URL
- `PREDICTION_ARTIFACT_ROOT`: 승격된 가격 모델의 artifact 루트

다른 설정 파일을 쓰려면 `CRAWL_CONFIG_PATH=/path/to/config.json npm run server`처럼 지정할 수 있습니다.

## 로그인

대시보드는 `crawl/config.json`의 `dashboard.password` 또는 `DASHBOARD_PASSWORD` 환경변수로 비밀번호를 설정합니다.
설정이 없으면 개발용 기본값 `heavyequip`을 사용합니다.

```json
{
  "dashboard": {
    "password": "원하는-비밀번호"
  }
}
```

브라우저에서 한 번 로그인하면 localStorage에 비밀번호와 만료시각을 저장해 1일 동안 자동 로그인합니다.

## 국제 사이트 분석

`국제 사이트 분석` 탭은 Machinery Trader, Machineryline, IronPlanet, Ritchie Bros.,
Mascus Global의 공식 목록 진입점과 응답 형식·정렬·페이지네이션·정규화 대상 필드를
한 화면에서 비교합니다. 이 단계에서는 외부 수집 요청이 비활성화되어 있으며, MySQL DB가
아직 없어도 분석 카탈로그는 표시됩니다.

우선순위 3개 사이트의 캡처 응답은 `crawl.international.parsers.parse_listing_payload()`로
기존 `listings` 형식에 정규화합니다. 원문 판매통화와 금액은 `sale_currency`,
`sale_amount`에 보존하고, 마지막으로 성공한 ECB 기준환율을 `sale_fx_rate_krw`,
`sale_fx_rate_date`에 기록합니다. 계산된 원화값은 `price_krw`에 저장합니다.
환율 수집 실패 시 마지막 캐시를 사용하며 크롤링을 중단하지 않습니다.

`heavyequip-fx-monthly` 워커는 매월 1일 05:30 KST에 ECB 환율을 한 번 갱신한 뒤 전체
매물의 환율과 원화 계산값을 다시 계산합니다. 수동 실행은 다음과 같습니다.

```bash
python3 crawl/fx_monthly.py --run-once
```

초기 백필은 등록일 최신순의 1페이지부터 과거 방향으로 진행하도록 설계했습니다.
`source_sync_state`가 다음 cursor/page를 저장하고, `source_request_log` 및 `crawl_tasks`의
결정적 `request_fingerprint`가 완료된 요청의 재전송을 막습니다. 실제 네트워크 실행기는
사이트별 응답 캡처와 이용조건 검토가 끝난 다음 활성화해야 합니다.

차단 응답을 같은 프록시와 헤더로 재현하는 방법은
`docs/international_request_reproduction.md`에 정리했습니다.
