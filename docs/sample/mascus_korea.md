# Mascus Korea 샘플 요청/응답

- 생성일: 2026-05-01 01:23:57 UTC+09:00
- 기준 문서: [../mascus.co.kr.md](../mascus.co.kr.md)
- 응답 유형: JSON
- 요청 URL: `https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets`

## 요청

```bash
curl -L \
  -X POST \
  'https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets' \
  -H 'Content-Type: application/json' \
  -H 'hostname: www.mascus.co.kr' \
  -H 'reqfor: env:browser:for:searchResults' \
  --data '{"catalogs": ["construction"], "countries": ["KR"], "pagesize": 2, "page": 1, "usercurrency": "KRW"}'
```

## 응답 샘플

- HTTP status: `200`
- 최종 URL: `https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets`
- Content-Type: `application/json; charset=utf-8`
- 원본 응답 크기: `10,738` bytes

```json
{
  "items": [
    {
      "productId": "{A5AE3E1E-D4F4-4133-94D0-ADA2FDF30421}",
      "brand": "Hyundai",
      "model": "HW 145",
      "yearOfManufacture": 2021,
      "catalogName": "construction",
      "categoryName": "wheelexcavators",
      "meterReadout": null,
      "meterReadoutUnit": null,
      "locationCountryCode": "KR",
      "locationCity": "-",
      "priceEURO": null,
      "priceOriginal": null,
      "priceOriginalUnit": "USD",
      "priceInUserCurrency": 0,
      "userCurrency": "KRW",
      "priceRentalDaily": null,
      "priceRentalWeekly": null,
      "priceRentalMonthly": null,
      "priceRentalDailyInUserCurrency": 0,
      "priceRentalWeeklyInUserCurrency": 0,
      "priceRentalMonthlyInUserCurrency": 0,
      "rentalCurrency": null,
      "rentalVatRate": 0,
      "auctionExternalLink": "",
      "mpeExternalLink": "",
      "imageUrl": "https://dnge9sb91helb.cloudfront.net/image/product/medium/a5ae3e1e/hyundai-hw-145,7558520d.jpg",
      "assetUrl": "/중고-건설장비/휠-굴삭기/hyundai-hw-145/lnlwewcw.html",
      "companyUrl": "/faiz-brothers-co-ltd/7be2c6a4,1,relevance,searchdealer.html",
      "companyCountry": "KR",
      "imageCount": 20,
      "videoCount": 0,
      "companyName": "Faiz Brothers Co. LTD",
      "companyId": "{7be2c6a4-c3f7-4817-9b8a-7b48847a87ce}",
      "featured": false,
      "highlighted": false,
      "latest24hAd": true,
      "rentalAd": false,
      "auctionAd": false,
      "mpeAd": false,
      "favoriteAd": false,
      "createDate": "2026-04-30T09:07:00",
      "sellerPhone": "+82 1091247348"
    },
    {
      "productId": "{F79CD654-59CB-4C13-A858-AA88D6A88751}",
      "brand": "Kobelco",
      "model": "RK 450",
      "yearOfManufacture": 1995,
      "catalogName": "construction",
      "categoryName": "roughterraincranes",
      "meterReadout": null,
      "meterReadoutUnit": null,
      "locationCountryCode": "KR",
      "locationCity": "-",
      "priceEURO": null,
      "priceOriginal": null,
      "priceOriginalUnit": "USD",
      "priceInUserCurrency": 0,
      "userCurrency": "KRW",
      "priceRentalDaily": null,
      "priceRentalWeekly": null,
      "priceRentalMonthly": null,
      "priceRentalDailyInUserCurrency": 0,
      "priceRentalWeeklyInUserCurrency": 0,
      "priceRentalMonthlyInUserCurrency": 0,
      "rentalCurrency": null,
      "rentalVatRate": 0,
      "auctionExternalLink": "",
      "mpeExternalLink": "",
      "imageUrl": "https://dnge9sb91helb.cloudfront.net/image/product/medium/f79cd654/kobelco-rk-450,ac0df5a2.jpg",
      "assetUrl": "/중고-건설장비/중고-r-t-크레인/kobelco-rk-450/qpkuoogm.html",
      "companyUrl": "/faiz-brothers-co-ltd/7be2c6a4,1,relevance,searchdealer.html",
      "companyCountry": "KR",
      "imageCount": 8,
      "videoCount": 0,
      "companyName": "Faiz Brothers Co. LTD",
      "companyId": "{7be2c6a4-c3f7-4817-9b8a-7b48847a87ce}",
      "featured": false,
      "highlighted": false,
      "latest24hAd": false,
      "rentalAd": false,
      "auctionAd": false,
      "mpeAd": false,
      "favoriteAd": false,
      "createDate": "2026-04-29T12:03:00",
      "sellerPhone": "+82 1091247348"
    }
  ],
  "facets": [
    {
      "facetName": "catalogname",
      "facetValues": [
        {
          "value": "construction",
          "count": 214,
          "from": 0,
          "to": 0,
          "indexable": false,
          "childFacets": [
            {
              "value": "cranesmain",
              "count": 93,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "roughterraincranes",
                  "count": 36,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "allterraincranes",
                  "count": 24,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "towercranes",
                  "count": 18,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "trackedcranes",
                  "count": 13,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "craneequipment",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "othercranes",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "excavators",
              "count": 56,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "crawlerexcavators",
                  "count": 40,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "wheelexcavators",
                  "count": 12,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "miniexcavators",
                  "count": 4,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "loaders",
              "count": 21,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "wheelloaders",
                  "count": 20,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "skidsteerloaders",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "drillingequipmentmain",
              "count": 14,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "drills",
                  "count": 10,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "heavydrills",
                  "count": 2,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "waterwellrigs",
                  "count": 2,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "platformsandcranes",
              "count": 11,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "truckplatforms",
                  "count": 6,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "scissorlifts",
                  "count": 3,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "articulatedboomlifts",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "telescopicboomlifts",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "concreteequipment",
              "count": 7,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "concretepumps",
                  "count": 6,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "concretedistributionbooms",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "dumpersmain",
              "count": 3,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "offhighwaytrucks",
                  "count": 2,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "dumpers",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "asphaltmachinesmain",
              "count": 2,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "asphaltcoldmillingmachines",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                },
                {
                  "value": "pavers",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "drillingrigs",
              "count": 2,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "crushers",
                  "count": 2,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "pilingequipmentmain",
              "count": 2,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "pilingrigs",
                  "count": 2,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "dozers",
              "count": 1,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "wheeldozers",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "roadconstruction",
              "count": 1,
              "from": 0,
              "to": 0,
              "indexable": false,
              "childFacets": [
                {
                  "value": "graders",
                  "count": 1,
                  "from": 0,
                  "to": 0,
                  "indexable": false
                }
              ]
            },
            {
              "value": "constructionothersmain",
              "count": 1,
              "from": 0,
              "to": 0,
              "indexable": false,

... [truncated, original 13,177 chars]
```

## 수집 메모

- 샘플 응답 크기를 줄이기 위해 `pagesize=2`로 요청합니다.
