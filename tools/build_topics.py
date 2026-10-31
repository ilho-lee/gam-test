# -*- coding: utf-8 -*-
"""공개 데이터 → 주제별 문항.

**모든 숫자는 raw/ 의 원본에서 계산합니다.** 지어낸 값이 하나도 없어야 합니다.
결과는 앱이 읽는 topics/*.json 과, 사람이 읽는 tools/정답지.md 로 나갑니다.

정답지와 이 스크립트는 .vercelignore 에 들어 있어 **배포되지 않습니다.**
공개 URL 에 정답지가 올라가면 게임이 성립하지 않습니다.

실행 (저장소 최상위에서):
    python tools/build_topics.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import datetime as dt
from collections import Counter
from pathlib import Path
from statistics import mean

# 윈도우 콘솔(cp949)은 이모지 · 기호를 못 찍고 멈춘다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent                                # 저장소 최상위 = 배포되는 곳
RAW = APP / "data" / "raw"
OUT = APP / "topics"

TOPICS: list[dict] = []


def load_json(name):
    return json.load(io.open(RAW / name, encoding="utf-8"))


def load_csv(name):
    return list(csv.DictReader(io.open(RAW / name, encoding="utf-8")))


def topic(tid, emoji, title, blurb, source, source_url, questions, caveat="", n=5):
    """caveat = 이 데이터를 믿을 때의 한계. 앱 화면에도 그대로 나간다.

    출처가 다르면 같은 '서울 기온'도 값이 다르다. 그 사실을 감추지 않는다.
    n = 이 주제의 문항 수. 기본은 5 이고, 일부러 다르게 둔 주제만 적는다.
    """
    TOPICS.append({"id": tid, "emoji": emoji, "title": title, "blurb": blurb,
                   "source": source, "source_url": source_url,
                   "caveat": caveat, "questions": questions, "n": n})


def slider(qid, text, answer, unit, lo, hi, step, basis, why):
    return {"id": qid, "type": "slider", "text": text, "unit": unit,
            "min": lo, "max": hi, "step": step,
            "answer": round(float(answer), 1), "basis": basis, "why": why}


def choice(qid, text, options, answer, basis, why):
    assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
    return {"id": qid, "type": "choice", "text": text, "options": options,
            "answer": answer, "basis": basis, "why": why}


# ── 1. 원화로 본 세 통화 ─────────────────────────────────────────
# 원본은 '유로 1단위당 각 통화' 이고 한 줄이 '하루의 한 통화' 다.
# 날짜로 묶은 뒤, 세 통화 값이 모두 있는 날만 쓴다 (빈 값 = 고시 없는 휴일).
# 원화 기준 값은 같은 날 두 값을 나눠서 구한다: 100엔 = KRW / JPY × 100
_fx = {}
_fx_rows = load_csv("ecb_krw_jpy_usd.csv")
for r in _fx_rows:
    if r["OBS_VALUE"]:
        _fx.setdefault(r["TIME_PERIOD"], {})[r["CURRENCY"]] = float(r["OBS_VALUE"])
# 고시 시각도 손으로 적지 않는다 — 원본 제목 칸 '…, 2.15 pm (C.E.T.)' 에서 읽는다
_fx_hm = _fx_rows[0]["TITLE_COMPL"].rsplit(", ", 1)[1].split()[0]
_fx_h, _fx_m = (int(x) for x in _fx_hm.split("."))
fx_time = f"{_fx_h + 12 if 'pm' in _fx_rows[0]['TITLE_COMPL'] else _fx_h}시 {_fx_m}분"
fx_blank = sum(1 for r in _fx_rows if r["CURRENCY"] == "KRW" and not r["OBS_VALUE"])
FX3 = sorted((d, v) for d, v in _fx.items() if len(v) == 3)
fx_first, fx_last = FX3[0][0], FX3[-1][0]
KRW_PER = {"엔화": lambda v: v["KRW"] / v["JPY"] * 100,     # 100엔
           "달러": lambda v: v["KRW"] / v["USD"],
           "유로": lambda v: v["KRW"]}
UNIT = {"엔화": "100엔", "달러": "1달러", "유로": "1유로"}

jpy_month = {}
for d, v in FX3:
    jpy_month.setdefault(d[:7], []).append(KRW_PER["엔화"](v))
jpy_month = {k: mean(v) for k, v in jpy_month.items()}
jpy_low = min(jpy_month, key=jpy_month.get)
JPY_BANDS = [("1999~2004년", 1999, 2004), ("2005~2009년", 2005, 2009),
             ("2010~2019년", 2010, 2019), ("2020~2024년", 2020, 2024)]
jpy_low_band = next(b for b, a, z in JPY_BANDS if a <= int(jpy_low[:4]) <= z)

eur_avg = mean(KRW_PER["유로"](v) for _, v in FX3)


def fx_year(name, y):
    return mean(KRW_PER[name](v) for d, v in FX3 if d[:4] == str(y))


fx_rise = {c: fx_year(c, 2024) / fx_year(c, 1999) - 1 for c in KRW_PER}
fx_top = max(fx_rise, key=fx_rise.get)
jpy_under = sum(1 for _, v in FX3 if KRW_PER["엔화"](v) < 1000)
jpy_under_pct = jpy_under / len(FX3) * 100
# 원본의 USD 는 '1유로당 달러'. 1보다 작으면 1달러가 1유로보다 비싸다
usd_year = {}
for d, v in FX3:
    usd_year.setdefault(int(d[:4]), []).append(v["USD"])
usd_dear = sorted(y for y, v in usd_year.items() if mean(v) < 1)

topic(
    "krw-three", "💱", "원화로 본 세 통화",
    "1999년부터 2024년까지, 원화로 본 엔화·달러·유로",
    "ECB Data Portal (유럽중앙은행 일별 기준환율)", "https://data.ecb.europa.eu/",
    [
        choice("k1", "1999~2024년, 100엔이 원화로 가장 쌌던 달은 언제쯤일까요?",
               [b for b, _, _ in JPY_BANDS], jpy_low_band,
               f"{fx_first}~{fx_last} 거래일마다 원화 값을 엔화 값으로 나눠 100엔당 원화를 "
               f"구하고 달별로 평균하면 가장 낮은 달은 {jpy_low[:4]}년 {int(jpy_low[5:])}월 "
               f"{jpy_month[jpy_low]:,.1f}원입니다",
               "'엔저'는 최근 일로 기억되지만, 원화로 본 엔화가 가장 쌌던 때는 "
               "따로 있습니다."),
        slider("k2", "1999~2024년 평균, 1유로는 몇 원이었을까요?",
               eur_avg, "원", 900, 1800, 25,
               f"{fx_first}~{fx_last} 거래일 {len(FX3):,}일의 1유로당 원화 값을 평균하면 "
               f"{eur_avg:,.1f}원입니다",
               "유로는 자주 보는 통화가 아니라서, 달러에 비해 감이 크게 "
               "흔들립니다."),
        choice("k3", "세 통화 중 1999년 대비 2024년에 원화로 가장 많이 오른 통화는?",
               ["엔화", "달러", "유로"], fx_top,
               "1999년과 2024년의 거래일 평균 원화 값을 비교하면 "
               + " · ".join(f"{c} {UNIT[c]} {fx_year(c, 1999):,.0f}원 → "
                            f"{fx_year(c, 2024):,.0f}원({fx_rise[c] * 100:+.1f}%)"
                            for c in KRW_PER) + "입니다",
               "뉴스에 자주 나오는 통화가 가장 많이 움직인 통화라는 보장은 없습니다."),
        slider("k4", "1999~2024년, 100엔이 1,000원보다 쌌던 날은 전체의 몇 %일까요?",
               jpy_under_pct, "%", 0, 100, 5,
               f"{fx_first}~{fx_last} 거래일 {len(FX3):,}일 중 100엔당 원화(원화 값 ÷ 엔화 값 "
               f"× 100)가 1,000원 미만인 날은 {jpy_under:,}일입니다",
               "'100엔 = 1,000원'이라는 기준점이 머릿속에 박혀 있어서, 그 아래였던 "
               "날의 비율은 감이 잘 안 옵니다."),
        slider("k5", "1999~2024년 중 1달러가 1유로보다 비쌌던 해는 몇 번일까요?",
               len(usd_dear), "번", 0, 10, 1,
               f"{fx_first[:4]}~{fx_last[:4]}년 해마다 1유로당 달러 값을 거래일 평균해 "
               f"1보다 작은 해를 세면 {len(usd_dear)}번"
               + (f"({', '.join(f'{y}년' for y in usd_dear)})" if usd_dear else "")
               + "입니다",
               "'유로가 달러보다 비싸다'는 인상이 강해서, 반대였던 시기는 잘 "
               "떠오르지 않습니다."),
    ],
    caveat=f"이 숫자는 서울 외환시장 종가가 아니라 유럽중앙은행이 중부유럽 시간 {fx_time}에 "
           "한 번 정해 '참고용'으로만 내는 유로 기준 환율이고, 원화로 본 엔화·달러는 시장에서 "
           "직접 거래된 값이 아니라 같은 날 두 값을 나눠 만든 값이며, 날짜도 한국 거래일이 "
           f"아닌 유럽중앙은행 고시일이라(한국 공휴일은 들어 있고 유럽 휴일 {fx_blank}일은 "
           "비어 있음) 뉴스나 은행에서 본 숫자와 다를 수 있습니다.")

# ── 2. 유럽과 일본의 여행지 ──────────────────────────────────────
# 도시 30곳은 fetch_all.py 의 TRAVEL_CITIES 를 그대로 쓴다 (두 곳에 따로 적지 않는다).
# travel_weather.json 은 그 순서대로 지점별 목록이고, travel_views_NN.json 은 NN 번째 도시다.
# 문항 수는 4개 — 환율·한국인 방문자·안전도 문항은 키 없는 출처가 없거나 겹쳐서 뺐다.
sys.path.insert(0, str(HERE))
from fetch_all import TRAVEL_CITIES  # noqa: E402

_tw = load_json("travel_weather.json")
TRAVEL = []
for i, (cc, city, _lat, _lon, _art) in enumerate(TRAVEL_CITIES):
    _d = _tw[i]["daily"]
    _v = load_json(f"travel_views_{i:02d}.json")["items"]
    TRAVEL.append({"cc": cc, "city": city, "grid": (_tw[i]["latitude"], _tw[i]["longitude"]),
                   "days": [{"d": t, "hi": hi, "lo": lo, "rain": r}
                            for t, hi, lo, r in zip(_d["time"], _d["temperature_2m_max"],
                                                    _d["temperature_2m_min"],
                                                    _d["precipitation_sum"])],
                   "views": sum(x["views"] for x in _v), "months": len(_v)})
tr_first, tr_last = TRAVEL[0]["days"][0]["d"], TRAVEL[0]["days"][-1]["d"]
TR_COUNTRIES = list(dict.fromkeys(c["cc"] for c in TRAVEL))

# 1) 7월 평균 최고기온 — 2024·2025년 7월. 보기는 가장 낮은 4곳을 도시 목록 순서로
JUL_YEARS = ("2024", "2025")
jul_hi = {c["city"]: mean(x["hi"] for x in c["days"]
                          if x["d"][5:7] == "07" and x["d"][:4] in JUL_YEARS)
          for c in TRAVEL}
jul_low4 = sorted(jul_hi, key=jul_hi.get)[:4]
jul_opts = [c["city"] for c in TRAVEL if c["city"] in jul_low4]
jul_cool = jul_low4[0]

# 2) 나라별 도시 5곳 영어 위키백과 조회수 합
tr_views = {cc: sum(c["views"] for c in TRAVEL if c["cc"] == cc) for cc in TR_COUNTRIES}
tr_top = max(tr_views, key=tr_views.get)
tr_months = TRAVEL[0]["months"]

# 3·4) 바르셀로나 '쾌적한 날' = 최고기온 18~26도 · 강수량 1mm 미만
COMF_LO, COMF_HI, COMF_RAIN = 18, 26, 1
bcn = next(c for c in TRAVEL if c["city"] == "바르셀로나")
bcn_comf = Counter(int(x["d"][5:7]) for x in bcn["days"]
                   if COMF_LO <= x["hi"] <= COMF_HI and x["rain"] < COMF_RAIN)
bcn_top4 = sorted(bcn_comf, key=lambda m: -bcn_comf[m])[:4]
bcn_best = bcn_top4[0]
bcn_years = len(bcn["days"]) / 365.25
bcn_per_year = sum(bcn_comf.values()) / round(bcn_years)

topic(
    "travel", "🧳", "유럽과 일본, 언제 어디로",
    f"6개국 30개 도시의 최근 3년 날씨와 관심도 ({tr_first[:7]}~{tr_last[:7]})",
    "Open-Meteo Archive (ERA5) · Wikimedia Pageviews", "https://open-meteo.com/",
    [
        choice("t1", "30개 도시 중 7월 평균 최고기온이 가장 낮은 곳은?",
               jul_opts, jul_cool,
               f"{'·'.join(JUL_YEARS)}년 7월 도시마다 하루 최고기온을 평균하면 "
               + " · ".join(f"{c} {jul_hi[c]:.1f}도" for c in jul_low4)
               + "로 가장 낮은 네 곳 중 1위입니다",
               "북유럽은 다 비슷하게 서늘할 것 같지만, 바다를 낀 서쪽 해안과 내륙의 "
               "여름은 다릅니다."),
        choice("t2", "6개국 중 대표 도시 5곳의 영어 위키백과 조회수 합이 가장 많은 나라는?",
               TR_COUNTRIES, tr_top,
               f"{tr_first[:7]}~{tr_last[:7]} {tr_months}개월 동안 나라마다 도시 5곳 문서의 "
               "월별 조회수(사람만)를 모두 더하면 "
               + " · ".join(f"{cc} {tr_views[cc]:,}회"
                            for cc in sorted(tr_views, key=lambda k: -tr_views[k]))
               + "입니다",
               "관광지로 유명한 나라와 사람들이 많이 찾아 읽는 나라는 다를 수 있습니다."),
        choice("t3", "바르셀로나에서 '쾌적한 날'이 가장 많은 달은?",
               [f"{m}월" for m in sorted(bcn_top4)], f"{bcn_best}월",
               f"{tr_first}~{tr_last} 하루 최고기온 {COMF_LO}~{COMF_HI}도이고 강수량 "
               f"{COMF_RAIN}mm 미만인 날을 달별로 세면 "
               + " · ".join(f"{m}월 {bcn_comf[m]}일" for m in bcn_top4)
               + f"(3년 합)이라 {bcn_best}월이 가장 많습니다",
               "여행은 여름이라는 생각이 강하지만, 바르셀로나의 한여름은 '쾌적한 날' "
               "기준을 넘습니다."),
        slider("t4", "바르셀로나에서 1년 중 '쾌적한 날'은 며칠쯤일까요?",
               bcn_per_year, "일", 0, 200, 5,
               f"{tr_first}~{tr_last} {round(bcn_years)}년 동안 하루 최고기온 "
               f"{COMF_LO}~{COMF_HI}도이고 강수량 {COMF_RAIN}mm 미만인 날 "
               f"{sum(bcn_comf.values())}일을 {round(bcn_years)}으로 나누면 "
               f"{bcn_per_year:.1f}일입니다",
               "'날씨 좋은 도시'라는 인상과 실제로 쾌적한 날의 수는 다를 수 있습니다."),
    ],
    caveat="날씨는 도시 관측소가 아니라 약 25km 격자의 ERA5 모델 추정값이고, '쾌적한 날'"
           f"(최고 {COMF_LO}~{COMF_HI}도·강수 {COMF_RAIN}mm 미만)은 이 퀴즈가 정한 기준이며, "
           "관심도는 방문자 수가 아니라 영어 위키백과 문서를 읽은 횟수이고, 도시 30곳도 나라별 "
           "인구 상위 15곳 중 조회수 상위 5곳만 골라 다른 곳에서 본 순위·숫자와 다를 수 있습니다.",
    n=4)


# ════════════════════════════════════════════════════════════════
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for t in TOPICS:
        assert len(t["questions"]) == t["n"], f"{t['id']}: 문항이 {t['n']}개가 아닙니다"
        pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                                  "source", "source_url", "caveat")}
        pack["questions"] = t["questions"]
        io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
            json.dumps(pack, ensure_ascii=False, indent=2))
        index.append({k: t[k] for k in ("id", "emoji", "title", "blurb",
                                        "source")})

    # 제목·부제는 화면을 바꾸며 고친 값을 지킨다 (2장에서 내 제목으로 바꾼다).
    # 다시 계산해도 내 제목이 «감 테스트»로 돌아가지 않게, 있던 값을 읽어 쓴다
    old = {}
    if (APP / "topics.json").exists():
        try:
            old = json.load(io.open(APP / "topics.json", encoding="utf-8"))
        except ValueError:
            old = {}
    io.open(APP / "topics.json", "w", encoding="utf-8").write(json.dumps({
        "title": old.get("title", "감 테스트"),
        "subtitle": old.get("subtitle", "숫자에 대한 당신의 감은 몇 점입니까"),
        # 등급·문구는 여기서 고칩니다. 코드를 건드릴 일이 아닙니다
        "grades": [
            {"min": 90, "name": "촉이 데이터급", "emoji": "🎯"},
            {"min": 70, "name": "감이 좋은 편", "emoji": "📊"},
            {"min": 50, "name": "보통의 감각", "emoji": "🙂"},
            {"min": 30, "name": "느낌대로 삽니다", "emoji": "🎲"},
            {"min": 0, "name": "감은 접어두시죠", "emoji": "🙈"},
        ],
        "reactions_choice": {"hit": "맞히셨습니다", "miss": "다들 그렇게 찍습니다"},
        "reactions": [
            {"max": 5, "text": "촉이 좋으시네요"},
            {"max": 20, "text": "비슷하게 보셨습니다"},
            {"max": 60, "text": "음…"},
            {"max": 999, "text": "꽤 멀리 가셨습니다"},
        ],
        "topics": index,
    }, ensure_ascii=False, indent=2))

    # 사람이 읽는 정답지
    md = [f"# 문항 정답지 — {len(TOPICS)}주제 {sum(len(t['questions']) for t in TOPICS)}문항", "",
          "> 모든 값은 `data/raw/` 의 원본에서 `tools/build_topics.py` 가 계산합니다.", ""]
    for t in TOPICS:
        md += [f"## {t['emoji']} {t['title']}", "",
               f"- 출처: {t['source']} · {t['source_url']}"]
        if t["caveat"]:
            md += [f"- **한계** {t['caveat']}"]
        md += [""]
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            md += [f"**{q['text']}**", "",
                   f"- 정답 **{a}**", f"- 근거 {q['basis']}",
                   f"- 왜 틀리나 {q['why']}", ""]
    io.open(HERE / "정답지.md", "w", encoding="utf-8").write("\n".join(md))

    print(f"주제 {len(TOPICS)}개 · 문항 {sum(len(t['questions']) for t in TOPICS)}개")
    for t in TOPICS:
        print(f"\n{t['emoji']} {t['title']}  ({t['source']})")
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            print(f"    [{q['type'][:6]:<6}] {q['text'][:44]:<44} → {a}")


if __name__ == "__main__":
    main()
