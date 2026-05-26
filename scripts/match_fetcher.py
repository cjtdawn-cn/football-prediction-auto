#!/usr/bin/env python3
"""
当日比赛自动获取器 — 从 Fotmob 公开 API 获取今天比赛列表
输出: data/today_matches.json
"""
import sys, os, json, re, traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"

CST = timezone(timedelta(hours=8))

# Fotmob league id → 内部联赛代码
FOTMOB_ID_MAP = {
    47: "E0",     # Premier League
    54: "D1",     # Bundesliga
    53: "F1",     # Ligue 1
    55: "I1",     # Serie A
    87: "SP1",    # La Liga
    52: "E1",     # Championship
    77: "D2",     # 2. Bundesliga
    64: "F2",     # Ligue 2
    56: "I2",     # Serie B
    88: "SP2",    # La Liga 2
    71: "N1",     # Eredivisie
    76: "P1",     # Primeira Liga
    74: "B1",     # Belgian Pro League
    83: "T1",     # Super Lig
    89: "BRA",    # Brasileirão
    130: "USA",    # Major League Soccer
    92: "NOR",    # Eliteserien
    93: "SWE",    # Allsvenskan
    94: "DEN",    # Superliga
    73: "AUT",    # Austrian Bundesliga
    75: "SUI",    # Swiss Super League
    79: "JAP",    # J1 League
    124: "CHN",   # Chinese Super League
    67: "ARG",    # Argentine League
    68: "MEX",    # Liga MX
    59: "SC0",    # Scottish Premiership
    97: "IRL",    # Irish Premier Division
    98: "FIN",    # Veikkausliiga
    60: "G1",     # Greek Super League
    62: "ROM",    # Romanian Liga I
    63: "POL",    # Polish Ekstraklasa
    80: "RUS",    # Russian Premier League
}

# fallback: ccode → 候选联赛代码列表 (匹配时按优先级取)
CCODE_MAP = {
    "ENG": ["E0", "E1", "E2", "E3", "EC"],
    "GER": ["D1", "D2"],
    "FRA": ["F1", "F2"],
    "ITA": ["I1", "I2"],
    "ESP": ["SP1", "SP2"],
    "NED": ["N1"],
    "POR": ["P1"],
    "BEL": ["B1"],
    "TUR": ["T1"],
    "BRA": ["BRA"],
    "USA": ["USA"],
    "NOR": ["NOR"],
    "SWE": ["SWE"],
    "DEN": ["DEN"],
    "AUT": ["AUT"],
    "SUI": ["SUI"],
    "JPN": ["JAP"],
    "CHN": ["CHN"],
    "ARG": ["ARG"],
    "MEX": ["MEX"],
    "SCO": ["SC0"],
    "IRL": ["IRL"],
    "FIN": ["FIN"],
    "GRE": ["G1"],
    "ROU": ["ROM"],
    "POL": ["POL"],
    "RUS": ["RUS"],
}

# 每个联赛每天最多取几场 (避免单日几百场)
MAX_PER_LEAGUE = int(os.environ.get("MAX_PER_LEAGUE", "3"))

# 优先联赛 (这些联赛必取, 按顺序)
PRIORITY_LEAGUES = ["E0", "D1", "F1", "I1", "SP1", "N1", "P1", "BRA", "USA"]


def _match_league(fotmob_id, league_name, ccode):
    """将 Fotmob 联赛信息映射到内部代码"""
    # 1. 精确 ID 匹配
    if fotmob_id in FOTMOB_ID_MAP:
        return FOTMOB_ID_MAP[fotmob_id]

    # 2. ccode 匹配 (取该国家的第一个联赛)
    candidates = CCODE_MAP.get(ccode.upper(), [])
    if candidates:
        return candidates[0]

    return None


def fetch_today_matches(date_str=None):
    """从 Fotmob 获取当天比赛, 返回 {lg_code: [matches]}"""
    if date_str is None:
        date_str = datetime.now(CST).strftime("%Y-%m-%d")

    url = f"https://www.fotmob.com/api/matches?date={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  Fotmob API returned HTTP {resp.status_code}")
            return {}
        data = resp.json()
    except Exception as e:
        print(f"  Fotmob API error: {e}")
        return {}

    leagues_data = data.get("leagues", [])
    if not leagues_data:
        print(f"  No leagues data in Fotmob response (keys: {list(data.keys())[:5]})")
        return {}

    result = {}
    matched = 0
    skipped = 0

    for league_group in leagues_data:
        fotmob_id = league_group.get("id", 0)
        fotmob_name = league_group.get("name", "")
        ccode = league_group.get("ccode", "")
        matches = league_group.get("matches", [])

        lg_code = _match_league(fotmob_id, fotmob_name, ccode)
        if lg_code is None:
            skipped += 1
            continue

        # 取未开始的比赛
        pending = []
        for m in matches:
            status = m.get("status", {})
            if status.get("started") or status.get("finished"):
                continue
            h = m.get("home", {}).get("name", "")
            a = m.get("away", {}).get("name", "")
            if h and a:
                pending.append({"home": h, "away": a})
                if len(pending) >= MAX_PER_LEAGUE:
                    break

        if pending:
            result[lg_code] = pending
            matched += 1
            print(f"  {fotmob_name} ({ccode}) → {lg_code}: {len(pending)}场")

    print(f"  匹配: {matched}联赛, 跳过: {skipped}联赛")
    return result


def save_match_list(by_league, date_str):
    """将联赛分组数据写入 today_matches.json"""
    matches = []
    # 优先联赛排前面
    done = set()
    for lg in PRIORITY_LEAGUES:
        if lg in by_league:
            for m in by_league[lg]:
                matches.append({"lg": lg, "home": m["home"], "away": m["away"]})
            done.add(lg)

    # 其余联赛
    for lg, mlist in sorted(by_league.items()):
        if lg in done:
            continue
        for m in mlist:
            matches.append({"lg": lg, "home": m["home"], "away": m["away"]})

    if not matches:
        print("  WARNING: 没有匹配到任何支持的联赛比赛!")
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

    print(f"\n  共 {len(matches)} 场比赛 → {out_path}")
    # 打印所有比赛
    for i, m in enumerate(matches):
        print(f"    {i+1}. [{m['lg']}] {m['home']} vs {m['away']}")
    return payload


def main():
    date_str = os.environ.get("PREDICTION_DATE")
    if not date_str:
        date_str = datetime.now(CST).strftime("%Y-%m-%d")

    print("=" * 50)
    print(f"  比赛列表获取 — {date_str}")
    print("=" * 50)

    by_league = fetch_today_matches(date_str)

    if not by_league:
        print("\n  未获取到比赛数据。使用 fallback 列表。")
        # 不创建文件, 让 run_predict.py 用内置 fallback
        return

    save_match_list(by_league, date_str)


if __name__ == "__main__":
    main()
