# 중기114 API 요청 파라미터 분석

## 요약

- Origin: `https://xn--114-vg9le98h.com`
- Canonical: `https://중기114.com`
- 매물 수 추정: `/product` 1-13페이지 중복 제거 기준 약 `300`건
- 응답 유형: `HTML 목록`
- 단일 엔드포인트: `https://중기114.com/product`

## 요청

```text
https://중기114.com/product?page=2
https://중기114.com/?mid=product&is_search=true&category=238&extra_vars4=20200101&extra_vars4-2=20241231&extra_vars6=얀마&page=1
```

## 파라미터

- 카테고리: `mid=product`, `category`
- 페이지: `page`
- 검색/필터: `is_search`, `extra_vars4`, `extra_vars4-2`, `extra_vars5`, `extra_vars6`, `extra_vars8`, `extra_vars10`
- 연식 범위: `extra_vars4`, `extra_vars4-2`
- 상세 식별: `/product/{document_srl}`

## 특이사항

- `extra_vars4`, `extra_vars4-2`는 등록일이 아니라 장비 연식 범위입니다.
- 고정 매물/추천 매물 반복이 있으므로 전체 수집 카운트는 URL id 기준으로 dedupe해야 합니다.
