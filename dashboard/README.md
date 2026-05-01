# Dashboard

크롤러가 생성한 `crawl/data/parsed` JSON을 읽어서 중장비 매물을 보여주는 Node + React 대시보드입니다.

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

다른 수집 데이터 경로를 쓰려면 `CRAWL_DATA_DIR=/path/to/parsed npm run server`처럼 지정할 수 있습니다.
