#!/usr/bin/env python3
"""
竞彩足球数据抓取 — 从 500.com 获取每日竞彩比赛列表 + 官方赔率
输出: data/jczq_matches.json
"""
import re, json
from pathlib import Path
import requests

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"

URL = "https://trade.500.com/jczq/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_jczq_matches():
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.encoding = 'gbk'
    html = resp.text

    matches = []
    rows = re.findall(r'<tr[^>]*data-matchid="(\d+)"[^>]*>(.*?)</tr>', html, re.DOTALL)
    seen = set()

    for mid, row in rows:
        # 提取带 href 的 a 标签文字
        teams = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([^<]+)</a>', row)
        if len(teams) < 2:
            continue

        # 赛事名: 第一个 a 标签
        league_match = re.search(r'<td[^>]*>[\s]*<a[^>]*>([^<]+)</a>[\s]*</td>', row)
        league = league_match.group(1) if league_match else ''

        # 赔率
        odds_raw = re.findall(r'>(\d+\.\d+)<', row)
        odds = [float(o) for o in odds_raw if 1.01 <= float(o) <= 99.0]

        if len(odds) < 3:
            continue

        # 队伍名: 过滤 URL 和非文字内容
        team_names = [t for t in teams if len(t) > 1 and not t.startswith('http')]
        if len(team_names) < 2:
            continue

        # 用原始列表的倒数两个元素 (跳过赛事名)
        home = team_names[-2]
        away = team_names[-1]
        # 如果第一个是赛事名, 队名是倒数两个
        # 有时第一个也是赛事名的一部分, 跳过
        if team_names[0] == league and len(team_names) >= 3:
            home = team_names[-2]
            away = team_names[-1]

        key = (home, away)
        if key in seen:
            continue
        seen.add(key)

        # 让球数 (从 td[4] 提取: "0 -1" → "-1")
        handicap = ''
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) >= 5:
            hcap_text = re.sub(r'<[^>]+>', '', tds[4]).strip()
            hcap_nums = re.findall(r'([+-]?\d+)', hcap_text)
            if hcap_nums:
                hcap_nums_int = [int(x) for x in hcap_nums]
                handicap = str(max(hcap_nums_int, key=abs))

        match_info = {
            'league': league,
            'home': home,
            'away': away,
            'handicap': handicap,
            'spf_odds': odds[:3],
            'rqspf_odds': odds[3:6] if len(odds) >= 6 else [],
        }
        matches.append(match_info)

    return matches


def main():
    matches = fetch_jczq_matches()
    out_path = DATA_DIR / "jczq_matches.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f"[lottery_fetcher] {len(matches)} 竞彩比赛 → {out_path}")
    for i, m in enumerate(matches):
        hcap = f"({m['handicap']})" if m['handicap'] else ""
        print(f"  {i+1}. [{m['league']}] {m['home']} vs {m['away']} {hcap}")
        print(f"     SPF: {m['spf_odds']}  让球SPF: {m['rqspf_odds']}")
    return matches


if __name__ == '__main__':
    main()
