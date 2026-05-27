#!/usr/bin/env python3
"""
当日比赛自动获取器 — 多源获取当天足球比赛列表
数据源:
  1. openfootball/football.json (免费, 无认证, 覆盖欧洲主要联赛)
  2. football-data.org API (免费注册, 覆盖更广, 需 FOOTBALL_DATA_KEY)
  3. Fotmob Next.js SSR 页面抓取 (免费, 无需认证)
输出: data/today_matches.json
"""
import sys, os, json, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
CST = timezone(timedelta(hours=8))

MAX_PER_LEAGUE = int(os.environ.get("MAX_PER_LEAGUE", "4"))
FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")

# ============================================================
# Source 1: openfootball/football.json 联赛文件映射
# ============================================================
OPENFOOTBALL_LEAGUES = {
    "en.1": "E0", "de.1": "D1", "es.1": "SP1", "it.1": "I1",
    "fr.1": "F1", "en.2": "E1", "nl.1": "N1", "pt.1": "P1",
    "de.2": "D2", "es.2": "SP2", "it.2": "I2", "fr.2": "F2",
}
OPENFOOTBALL_BASE = "https://raw.githubusercontent.com/openfootball/football.json/master"

# ============================================================
# Source 2: football-data.org 联赛映射 (free tier 覆盖13个赛事)
# ============================================================
FD_COMPETITIONS = {
    "PL": "E0",     # Premier League
    "PD": "SP1",    # La Liga
    "BL1": "D1",    # Bundesliga
    "SA": "I1",     # Serie A
    "FL1": "F1",    # Ligue 1
    "ELC": "E1",    # Championship
    "DED": "N1",    # Eredivisie
    "PPL": "P1",    # Primeira Liga
    "BSA": "BRA",   # Brazilian Serie A
    "CLI": "INTL",  # Copa Libertadores (南美解放者杯)
    "CL": "INTL",   # Champions League
    "EC": "INTL",   # European Championship
    "WC": "INTL",   # FIFA World Cup
}

# ============================================================
# Source 3: Fotmob Next.js SSR — 已验证可用的联赛页面
# ============================================================
FOTMOB_LEAGUE_PAGES = {
    130: ("usa/mls", "USA"),
    47: ("premier-league", "E0"),
    54: ("bundesliga", "D1"),
    87: ("laliga", "SP1"),
    55: ("serie-a", "I1"),
    53: ("ligue-1", "F1"),
    71: ("eredivisie", "N1"),
    76: ("primeira-liga", "P1"),
    52: ("championship", "E1"),
}

PRIORITY_LEAGUES = ["E0", "D1", "F1", "I1", "SP1", "N1", "P1", "BRA", "USA", "NOR", "SWE"]


def _fetch_openfootball(season, date_str):
    """从 openfootball/football.json 获取比赛"""
    by_league = {}
    for file_key, lg_code in OPENFOOTBALL_LEAGUES.items():
        url = f"{OPENFOOTBALL_BASE}/{season}/{file_key}.json"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            matches = data.get("matches", [])
            upcoming = [m for m in matches if m.get("date", "") == date_str
                       and not m.get("score")]
            if upcoming:
                by_league[lg_code] = []
                for m in upcoming[:MAX_PER_LEAGUE]:
                    by_league[lg_code].append({
                        "home": m.get("team1", ""),
                        "away": m.get("team2", ""),
                    })
                print(f"  [openfootball] {lg_code}: {len(by_league[lg_code])} matches")
        except Exception as e:
            print(f"  [openfootball] {lg_code} error: {e}")
    return by_league


def _fetch_football_data(date_str):
    """从 football-data.org API 获取比赛"""
    if not FOOTBALL_DATA_KEY:
        return {}
    by_league = {}
    headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
    url = f"https://api.football-data.org/v4/matches?dateFrom={date_str}&dateTo={date_str}"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  [football-data.org] HTTP {resp.status_code}")
            return {}
        data = resp.json()
        for match in data.get("matches", []):
            comp = match.get("competition", {}).get("code", "")
            lg_code = FD_COMPETITIONS.get(comp)
            if not lg_code:
                continue
            status = match.get("status", "")
            if status in ("FINISHED", "IN_PLAY", "PAUSED"):
                continue
            h = match.get("homeTeam", {}).get("name", "")
            a = match.get("awayTeam", {}).get("name", "")
            if h and a:
                by_league.setdefault(lg_code, []).append({"home": h, "away": a})
    except Exception as e:
        print(f"  [football-data.org] error: {e}")
    for lg, mlist in by_league.items():
        by_league[lg] = mlist[:MAX_PER_LEAGUE]
        print(f"  [football-data.org] {lg}: {len(by_league[lg])} matches")
    return by_league


def _fetch_fotmob_ssr(date_str):
    """从 Fotmob Next.js SSR 页面抓取每联赛的赛程"""
    by_league = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en,zh-CN;q=0.9",
    }
    for fotmob_id, (slug, lg_code) in FOTMOB_LEAGUE_PAGES.items():
        try:
            url = f"https://www.fotmob.com/leagues/{fotmob_id}/matches/{slug}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue

            m = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                resp.text,
            )
            if not m:
                continue

            data = json.loads(m.group(1))
            pp = data.get("props", {}).get("pageProps", {})
            fixtures = pp.get("fixtures", {})
            all_matches = fixtures.get("allMatches", [])

            upcoming = []
            for match in all_matches:
                st = match.get("status", {})
                utc_time = st.get("utcTime", "")[:10]
                if utc_time == date_str and not st.get("finished") and not st.get("started"):
                    h = match.get("home", {}).get("name", "")
                    a = match.get("away", {}).get("name", "")
                    if h and a:
                        upcoming.append({"home": h, "away": a})
                        if len(upcoming) >= MAX_PER_LEAGUE:
                            break

            if upcoming:
                by_league[lg_code] = upcoming
                print(f"  [fotmob] {lg_code}: {len(upcoming)} matches")
        except Exception as e:
            print(f"  [fotmob] {lg_code} (ID:{fotmob_id}) error: {e}")

    return by_league


def fetch_today_matches(date_str=None):
    """多源获取当天比赛, 合并去重"""
    if date_str is None:
        date_str = datetime.now(CST).strftime("%Y-%m-%d")

    # 确定赛季 (用于 openfootball)
    year = int(date_str[:4])
    month = int(date_str[5:7])
    # 赛季跨年: 8月→次年5月是同一赛季
    if month >= 8:
        season = f"{year}-{str(year+1)[-2:]}"
    else:
        season = f"{year-1}-{str(year)[-2:]}"

    all_by_league = {}

    # 数据源1: openfootball (免费, 覆盖欧洲主要联赛)
    print("\n[1] openfootball/football.json ...")
    try:
        of_data = _fetch_openfootball(season, date_str)
        for lg, mlist in of_data.items():
            all_by_league.setdefault(lg, []).extend(mlist)
    except Exception as e:
        print(f"  openfootball error: {e}")

    # 数据源2: football-data.org (如果配置了 API key)
    if FOOTBALL_DATA_KEY:
        print("\n[2] football-data.org ...")
        try:
            fd_data = _fetch_football_data(date_str)
            for lg, mlist in fd_data.items():
                if lg not in all_by_league:
                    all_by_league[lg] = mlist
        except Exception as e:
            print(f"  football-data.org error: {e}")

    # 数据源3: Fotmob Next.js SSR
    print("\n[3] Fotmob SSR ...")
    try:
        fm_data = _fetch_fotmob_ssr(date_str)
        for lg, mlist in fm_data.items():
            if lg not in all_by_league:
                all_by_league[lg] = mlist
    except Exception as e:
        print(f"  fotmob error: {e}")

    # 去重 + 限制每联赛数量
    for lg in all_by_league:
        seen = set()
        unique = []
        for m in all_by_league[lg]:
            key = (m["home"], m["away"])
            if key not in seen:
                seen.add(key)
                unique.append(m)
        all_by_league[lg] = unique[:MAX_PER_LEAGUE]

    return all_by_league


def save_match_list(by_league, date_str):
    """将联赛分组数据写入 today_matches.json"""
    matches = []
    done = set()
    for lg in PRIORITY_LEAGUES:
        if lg in by_league:
            for m in by_league[lg]:
                matches.append({"lg": lg, "home": m["home"], "away": m["away"]})
            done.add(lg)

    for lg, mlist in sorted(by_league.items()):
        if lg in done:
            continue
        for m in mlist:
            matches.append({"lg": lg, "home": m["home"], "away": m["away"]})

    if not matches:
        print("\n  WARNING: No matches found from any source!")
        return None

    payload = {
        "date": date_str,
        "matches": matches,
        "fetched_at": datetime.now(CST).isoformat(),
    }

    out_path = DATA_DIR / "today_matches.json"
    tmp = str(out_path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    Path(tmp).replace(out_path)

    print(f"\n  Total: {len(matches)} matches saved → {out_path}")
    for i, m in enumerate(matches):
        print(f"    {i+1}. [{m['lg']}] {m['home']} vs {m['away']}")
    return payload


def main():
    date_str = os.environ.get("PREDICTION_DATE") or datetime.now(CST).strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"  Match Fetcher v2.0 — {date_str}")
    print(f"  Sources: openfootball + football-data.org + Fotmob SSR")
    print(f"  API key: {'CONFIGURED' if FOOTBALL_DATA_KEY else 'NOT SET'}")
    print("=" * 60)

    by_league = fetch_today_matches(date_str)

    if not by_league:
        existing_path = DATA_DIR / "today_matches.json"
        if existing_path.exists():
            print("\n  No matches found. Keeping existing today_matches.json unchanged.")
            return 0
        print("\n  No matches found and no existing today_matches.json is available.")
        return 1

    save_match_list(by_league, date_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
