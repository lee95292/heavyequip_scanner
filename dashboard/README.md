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
