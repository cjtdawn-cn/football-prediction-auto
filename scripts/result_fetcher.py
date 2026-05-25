#!/usr/bin/env python3
"""
比赛结果获取器 — 多源降级策略
1. 本地 CSV 查找 (Matches.csv / intl_processed.csv)
2. Fotmob 公开 API (免费, 无需 key)
3. football-data.org API (需 API key)
"""
import sys, os, json, re
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
CSV_CACHE = {}  # 缓存已加载的 DataFrame


def _load_csv(filename):
    """加载 CSV，带缓存"""
    if filename in CSV_CACHE:
        return CSV_CACHE[filename]
    path = DATA_DIR / filename
    if path.exists():
        df = pd.read_csv(path, low_memory=False)
        CSV_CACHE[filename] = df
        return df
    return None


def _normalize_name(name):
    """标准化队名用于模糊匹配"""
    return re.sub(r'\s+', '', name.lower().strip().replace('&', 'and'))


def lookup_csv(home_team, away_team, match_date_str):
    """在本地 CSV 数据中查找比赛结果（最可靠的来源）"""
    match_date = None
    try:
        match_date = datetime.strptime(match_date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

    home_norm = _normalize_name(home_team)
    away_norm = _normalize_name(away_team)

    # 1. 先查俱乐部数据 (Matches.csv)
    df = _load_csv("Matches.csv")
    if df is not None and 'MatchDate' in df.columns:
        df['_date'] = pd.to_datetime(df['MatchDate'], errors='coerce')
        df['_hn'] = df['HomeTeam'].astype(str).apply(_normalize_name)
        df['_an'] = df['AwayTeam'].astype(str).apply(_normalize_name)

        # 精确日期匹配
        mask = (df['_date'] == pd.Timestamp(match_date)) & \
               (df['_hn'] == home_norm) & (df['_an'] == away_norm)
        match = df[mask]
        if len(match) > 0:
            row = match.iloc[-1]
            return _build_result(row, 'club')

        # 模糊匹配 (日期±1天, 处理时差)
        for delta in [0, 1, -1, 2, -2]:
            d = match_date + timedelta(days=delta)
            mask = (df['_date'] == pd.Timestamp(d)) & \
                   (df['_hn'] == home_norm) & (df['_an'] == away_norm)
            match = df[mask]
            if len(match) > 0:
                row = match.iloc[-1]
                return _build_result(row, 'club')

    # 2. 查国际比赛数据
    idf = _load_csv("intl_processed.csv")
    if idf is not None:
        idf['_date'] = pd.to_datetime(idf['MatchDate'] if 'MatchDate' in idf.columns else idf['date'], errors='coerce')
        idf['_hn'] = idf['HomeTeam'].astype(str).apply(_normalize_name)
        idf['_an'] = idf['AwayTeam'].astype(str).apply(_normalize_name)

        for delta in [0, 1, -1, 2, -2]:
            d = match_date + timedelta(days=delta)
            mask = (idf['_date'] == pd.Timestamp(d)) & \
                   (idf['_hn'] == home_norm) & (idf['_an'] == away_norm)
            match = idf[mask]
            if len(match) > 0:
                row = match.iloc[-1]
                return _build_result(row, 'intl')

    return None


def _build_result(row, source):
    """从 DataFrame 行构建标准结果字典"""
    fthg = int(row.get('FTHome', row.get('FTHomeGoals', row.get('home_score', 0))))
    ftag = int(row.get('FTAway', row.get('FTAwayGoals', row.get('away_score', 0))))
    if fthg > ftag:
        ft_result = 'H'
    elif fthg == ftag:
        ft_result = 'D'
    else:
        ft_result = 'A'

    return {
        'ft_home_goals': fthg,
        'ft_away_goals': ftag,
        'ft_result': ft_result,
        'source': f'csv_{source}',
        'fetched_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    }


def fetch_fotmob(home_team, away_team, match_date_str):
    """从 Fotmob 公开 API 获取结果 (免费, 无需登录)
    Fotmob 有未公开但开放的 API，用于其 web 应用。
    """
    import requests
    try:
        # Fotmob search API 获取比赛
        # 注意: 这是公开接口，但可能随时变化
        date_formatted = match_date_str.replace('-', '')
        url = f"https://www.fotmob.com/api/matches?date={match_date_str}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        leagues = data.get('leagues', [])

        home_norm = _normalize_name(home_team)
        away_norm = _normalize_name(away_team)

        for league_group in leagues:
            for match in league_group.get('matches', []):
                h = _normalize_name(match.get('home', {}).get('name', ''))
                a = _normalize_name(match.get('away', {}).get('name', ''))
                if h == home_norm and a == away_norm:
                    status = match.get('status', {})
                    if status.get('finished', False):
                        result = status.get('scoreStr', '0-0')
                        parts = result.split('-')
                        fthg = int(parts[0]) if len(parts) == 2 else 0
                        ftag = int(parts[1]) if len(parts) == 2 else 0
                        if fthg > ftag:
                            ft = 'H'
                        elif fthg == ftag:
                            ft = 'D'
                        else:
                            ft = 'A'
                        return {
                            'ft_home_goals': fthg,
                            'ft_away_goals': ftag,
                            'ft_result': ft,
                            'source': 'fotmob',
                            'fetched_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
                        }
        return None
    except Exception as e:
        print(f"  [Fotmob error: {e}]")
        return None


def fetch_result(home_team, away_team, match_date_str):
    """获取比赛结果 — 多源降级策略"""
    # 1. 本地 CSV (最快最可靠)
    result = lookup_csv(home_team, away_team, match_date_str)
    if result:
        return result

    # 2. Fotmob API (免费公开)
    result = fetch_fotmob(home_team, away_team, match_date_str)
    if result:
        return result

    # 3. 标记为待获取
    return None


def find_missing_results(days_back=7):
    """扫描 results/ 目录，找出所有缺少结果的已完成比赛，尝试补全"""
    results_dir = BASE / "models" / "results"  # 与 EvolutionEngine 统一路径
    updated = 0
    now = datetime.now(timezone(timedelta(hours=8)))
    cutoff = now - timedelta(days=days_back)

    for f in sorted(results_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            continue

        changed = False
        for match_id, rec in data.items():
            if rec.get('actual') is not None:
                continue

            match_date = rec.get('match_date', f.stem)
            try:
                match_dt = datetime.strptime(match_date, "%Y-%m-%d")
            except ValueError:
                continue

            # 只处理截止日期之前的比赛
            if match_dt.date() >= now.date():
                continue
            if match_dt < cutoff:
                continue  # 太久远的跳过

            home = rec.get('home_team', '')
            away = rec.get('away_team', '')
            print(f"  查询: {home} vs {away} ({match_date})")

            result = fetch_result(home, away, match_date)
            if result:
                rec['actual'] = result
                changed = True
                updated += 1
                print(f"    → {result['ft_home_goals']}:{result['ft_away_goals']} ({result['ft_result']}) [{result['source']}]")

        if changed:
            tmp = str(f) + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as fout:
                json.dump(data, fout, indent=2, ensure_ascii=False)
            Path(tmp).replace(f)

    return updated


if __name__ == '__main__':
    print("=" * 50)
    print("  比赛结果获取测试")
    print("=" * 50)
    updated = find_missing_results()
    print(f"\n共补全 {updated} 场结果")
