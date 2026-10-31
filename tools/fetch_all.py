# -*- coding: utf-8 -*-
"""공개 데이터 내려받기 — 10주제의 원본을 raw/ 에 저장한다.

**전부 키도 로그인도 필요 없습니다.** 수업 중에 20명이 동시에 받아도 막히지
않는 곳만 골랐습니다.

한 번 받으면 raw/ 에 남으므로 다시 돌려도 새로 받지 않습니다.
(--force 를 주면 다시 받습니다)

실행 (저장소 최상위에서):
    python tools/fetch_all.py
    python tools/fetch_all.py --force
"""
from __future__ import annotations

import http.client
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# 윈도우 콘솔(cp949)은 한글 · 기호를 못 찍고 멈출 때가 있다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
# HTTP 헤더는 latin-1 만 담는다. 한글을 넣으면 UnicodeEncodeError 가 난다
UA = {"User-Agent": "gam-test-class/1.0 (data analysis class)"}
TIMEOUT = 90

SEOUL = (37.5665, 126.9780)

# 날씨는 **모델을 ERA5로 못 박는다** (&models=era5).
# 모델을 적지 않으면 Open-Meteo가 그때그때 '가장 알맞은 모델'(best_match)을 골라 섞어 준다.
# 그 구성이 바뀌면 같은 주소로 받아도 지난 값이 달라진다 — 2026-10에 실제로 2024년 서울
# 열대야가 15일에서 12일로 바뀌었다. 출처에 모델까지 적어야 다시 받아도 같은 값이 나온다.
ERA5 = "&models=era5"

# (나라, 도시, 위도, 경도, 영어 위키백과 문서) — 순서가 travel_weather.json 응답 목록의 순서다
TRAVEL_CITIES = [
    ("스페인", "바르셀로나", 41.38879, 2.15899, "Barcelona"),
    ("스페인", "마드리드", 40.4165, -3.70256, "Madrid"),
    ("스페인", "세비야", 37.38283, -5.97317, "Seville"),
    ("스페인", "발렌시아", 39.47391, -0.37966, "Valencia"),
    ("스페인", "말라가", 36.72016, -4.42034, "Málaga"),
    ("이탈리아", "로마", 41.89193, 12.51133, "Rome"),
    ("이탈리아", "밀라노", 45.46427, 9.18951, "Milan"),
    ("이탈리아", "나폴리", 40.85216, 14.26811, "Naples"),
    ("이탈리아", "피렌체", 43.77925, 11.24626, "Florence"),
    ("이탈리아", "토리노", 45.07049, 7.68682, "Turin"),
    ("독일", "베를린", 52.52437, 13.41053, "Berlin"),
    ("독일", "뮌헨", 48.13743, 11.57549, "Munich"),
    ("독일", "쾰른", 50.93333, 6.95, "Cologne"),
    ("독일", "함부르크", 53.55073, 9.99302, "Hamburg"),
    ("독일", "프랑크푸르트", 50.11552, 8.68417, "Frankfurt"),
    ("노르웨이", "오슬로", 59.91273, 10.74609, "Oslo"),
    ("노르웨이", "베르겐", 60.39299, 5.32415, "Bergen"),
    ("노르웨이", "트론헤임", 63.43049, 10.39506, "Trondheim"),
    ("노르웨이", "스타방에르", 58.97005, 5.73332, "Stavanger"),
    ("노르웨이", "올레순", 62.47225, 6.15492, "Ålesund"),
    ("스웨덴", "스톡홀름", 59.32938, 18.06871, "Stockholm"),
    ("스웨덴", "예테보리", 57.70716, 11.96679, "Gothenburg"),
    ("스웨덴", "말뫼", 55.60587, 13.00073, "Malmö"),
    ("스웨덴", "웁살라", 59.85882, 17.63889, "Uppsala"),
    ("스웨덴", "룬드", 55.70584, 13.19321, "Lund"),
    ("일본", "도쿄", 35.6895, 139.69171, "Tokyo"),
    ("일본", "오사카", 34.69379, 135.50107, "Osaka"),
    ("일본", "교토", 35.02107, 135.75385, "Kyoto"),
    ("일본", "히로시마", 34.4, 132.45, "Hiroshima"),
    ("일본", "요코하마", 35.43333, 139.65, "Yokohama"),
]

SOURCES: list[tuple[str, str, str]] = [
    # (저장 파일명, 설명, URL)
    ("seoul_weather.json",
     "서울 일별 기온·강수 1950~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=1950-01-01&end_date=2024-12-31"
     "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
     "&timezone=Asia%2FSeoul" + ERA5),

    ("seoul_snow.json",
     "서울 일별 강설량·최저기온 1990~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=1990-01-01&end_date=2024-12-31"
     "&daily=snowfall_sum,temperature_2m_min"
     "&timezone=Asia%2FSeoul" + ERA5),

    ("seoul_air.json",
     "서울 시간별 미세먼지 2023~2024 (Open-Meteo Air Quality · CAMS)",
     "https://air-quality-api.open-meteo.com/v1/air-quality"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=2023-01-01&end_date=2024-12-31"
     "&hourly=pm10,pm2_5&timezone=Asia%2FSeoul"),

    ("working_hours.csv",
     "연간 노동시간 (Our World in Data)",
     "https://ourworldindata.org/grapher/annual-working-hours-per-worker.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("life_expectancy.csv",
     "기대수명 (Our World in Data)",
     "https://ourworldindata.org/grapher/life-expectancy.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("wb_fertility.json",
     "합계출산율 전세계 (World Bank SP.DYN.TFRT.IN)",
     "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.TFRT.IN"
     "?format=json&per_page=20000&date=1960:2023"),

    ("wb_pop_kor.json",
     "한국 인구·고령화 (World Bank)",
     "https://api.worldbank.org/v2/country/KOR/indicator/"
     "SP.POP.TOTL;SP.POP.65UP.TO.ZS;SP.URB.TOTL.IN.ZS"
     "?format=json&per_page=2000&source=2"),

    ("wb_internet.json",
     "인터넷 사용률 전세계 (World Bank IT.NET.USER.ZS)",
     "https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS"
     "?format=json&per_page=20000&date=1990:2023"),

    ("usdkrw.json",
     "원달러 환율 1999~ (Frankfurter · ECB)",
     "https://api.frankfurter.dev/v1/1999-01-04..2024-12-31"
     "?base=USD&symbols=KRW"),

    # 유로 1단위당 원화·엔화·달러. 원화 대비 엔화·달러는 같은 날 두 값을 나눠서 구한다
    ("ecb_krw_jpy_usd.csv",
     "유로 대비 원화·엔화·달러 1999~2024 (ECB Data Portal · 일별 기준환율)",
     "https://data-api.ecb.europa.eu/service/data/EXR/D.KRW+JPY+USD.EUR.SP00.A"
     "?format=csvdata&startPeriod=1999-01-04&endPeriod=2024-12-31"),

    # 같은 표의 최근 기간 — 위 파일은 그대로 두고 따로 받는다 (원화로 본 세 통화 1번 문항)
    ("ecb_krw_jpy_usd_2021_2026.csv",
     "유로 대비 원화·엔화·달러 2021-01~2026-09 (ECB Data Portal · 일별 기준환율)",
     "https://data-api.ecb.europa.eu/service/data/EXR/D.KRW+JPY+USD.EUR.SP00.A"
     "?format=csvdata&startPeriod=2021-01-01&endPeriod=2026-09-30"),

    ("wb_countries.json",
     "World Bank 국가 목록 — 대륙·소득군 같은 집계치를 걸러내는 데 씁니다",
     "https://api.worldbank.org/v2/country?format=json&per_page=400"),

    *[(f"city_{cid}.json", f"{cn} 일별 기온·강수 1991~2020 (Open-Meteo Archive · ERA5 고정)",
       "https://archive-api.open-meteo.com/v1/archive"
       f"?latitude={lat}&longitude={lon}"
       "&start_date=1991-01-01&end_date=2020-12-31"
       "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
       f"&timezone=auto" + ERA5)
      for cid, cn, lat, lon in (
          ("seoul", "서울", 37.5665, 126.9780),
          ("tokyo", "도쿄", 35.6895, 139.6917),
          ("london", "런던", 51.5072, -0.1276),
          ("singapore", "싱가포르", 1.3521, 103.8198),
      )],

    # 여행지 30곳 — 나라별 GeoNames 인구 상위 15곳 중 영어 위키백과 2023-10~2026-09
    # 조회수 상위 5곳. 좌표는 GeoNames 값. 한 번에 여러 지점을 부르면 응답은 지점별 목록이다
    ("travel_weather.json",
     "여행지 30곳 일별 기온·강수 2023-10~2026-09 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     "?latitude=" + ",".join(str(c[2]) for c in TRAVEL_CITIES)
     + "&longitude=" + ",".join(str(c[3]) for c in TRAVEL_CITIES)
     + "&start_date=2023-10-01&end_date=2026-09-30"
     "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
     "&timezone=auto" + ERA5),

    # 여행지 30곳의 영어 위키백과 월별 조회수 (Wikimedia Pageviews · 사람만, 봇 제외).
    # 방문자 수가 아니라 '문서를 읽은 횟수' 다. 문서 하나에 한 번씩 부른다
    *[(f"travel_views_{i:02d}.json", f"{c[1]} 영어 위키백과 월별 조회수 2023-10~2026-09 (Wikimedia)",
       "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
       + urllib.parse.quote(c[4], safe="") + "/monthly/2023100100/2026093000")
      for i, c in enumerate(TRAVEL_CITIES)],

    ("quakes.geojson",
     "규모 5.5 이상 지진 2000~2024 (USGS) — 2만건 상한에 걸리지 않는 기준",
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2024-12-31"
     "&minmagnitude=5.5&orderby=time&limit=20000"),

    ("quakes_korea.geojson",
     "한반도 주변 지진 2000~2024 (USGS · 규모 3.0 이상)",
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2024-12-31"
     "&minmagnitude=3.0&minlatitude=33&maxlatitude=39.5"
     "&minlongitude=124&maxlongitude=132&limit=20000"),
]


def get(url: str, dest: Path, tries: int = 4) -> int:
    """받는다. 잠깐의 실패면 기다렸다가 다시 시도한다.

    공개 API 는 대부분 호출 제한이 있고(429), 큰 파일은 받다가 끊기기도 한다
    (IncompleteRead · 시간 초과). 한 번 실패했다고 포기하지 말고, 간격을 늘려 가며
    다시 부른다. 주소가 틀린 것(404 같은)은 다시 불러도 소용없으니 바로 알린다.
    """
    wait = 5
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            dest.write_bytes(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or i == tries - 1:
                raise
            why = str(e.code)
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == tries - 1:
                raise
            why = type(e).__name__
        print(f"          {why} — {wait}초 뒤 다시 시도합니다 ({i+1}/{tries-1})")
        time.sleep(wait)
        wait *= 2
    raise RuntimeError("도달 불가")


def main() -> int:
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    fail = 0
    for name, desc, url in SOURCES:
        dest = RAW / name
        if dest.exists() and not force:
            print(f"  건너뜀  {name:<22} 이미 있음 ({dest.stat().st_size/1024:,.0f}KB)")
            continue
        t0 = time.time()
        try:
            n = get(url, dest)
            print(f"  받음    {name:<22} {n/1024:>7,.0f}KB  {time.time()-t0:.1f}s  {desc}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            print(f"  실패    {name:<22} {e}")
            fail += 1
        time.sleep(0.4)          # 상대 서버에 예의를 지킨다

    print()
    print(f"총 {len(SOURCES)}건 / 실패 {fail}건 · 저장 위치 {RAW}")
    if fail:
        print("실패한 것은 잠시 뒤 다시 실행하면 대개 받아집니다.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
