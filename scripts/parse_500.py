#!/usr/bin/env python3
"""解析 500.com 竞彩足球页面, 提取比赛列表和赔率"""
import re, json, sys
import requests

def fetch_jczq_matches():
    url = "https://trade.500.com/jczq/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = 'gbk'
    html = resp.text

    matches = []
    # 找所有 data-matchid 行
    rows = re.findall(r'<tr[^>]*data-matchid="(\d+)"[^>]*>(.*?)</tr>', html, re.DOTALL)

    for mid, row in rows:
        # 提取 a 标签中的文字 (队名)
        teams = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([^<]+)</a>', row)
        if len(teams) < 2:
            continue

        # 提取赛事名称 (通常在前面的 td 中)
        league_match = re.search(r'<td[^>]*>[\s]*<a[^>]*>([^<]+)</a>[\s]*</td>', row)
        league = league_match.group(1) if league_match else ''

        # 提取赔率 (胜平负)
        odds = re.findall(r'>(\d+\.\d+)<', row)

        home_team = teams[0] if len(teams) > 0 else ''
        away_team = ''  # 客队在让球之后或第二个a标签

        # 找让球数 (td[4]: "0 -1" → "-1")
        handicap = ''
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) >= 5:
            hcap_text = re.sub(r'<[^>]+>', '', tds[4]).strip()
            hcap_nums = re.findall(r'([+-]?\d+)', hcap_text)
            if hcap_nums:
                hcap_nums_int = [int(x) for x in hcap_nums]
                handicap = str(max(hcap_nums_int, key=abs))

        # 赔率: SPF 赔率通常在前三个 >x.xx< 中
        spf_odds = []
        for o in odds:
            try:
                val = float(o)
                if 1.01 <= val <= 99.0:
                    spf_odds.append(val)
            except:
                pass

        if len(spf_odds) >= 3 and len(teams) >= 2:
            # 队伍名: 跳过赛事名
            team_names = [t for t in teams if len(t) > 1 and not t.startswith('http')]
            if len(team_names) >= 2:
                match_info = {
                    'id': mid,
                    'league': team_names[0] if len(team_names) > 2 else league,
                    'home': team_names[-2],
                    'away': team_names[-1],
                    'handicap': handicap,
                    'spf_odds': spf_odds[:3],
                    'rqspf_odds': spf_odds[3:6] if len(spf_odds) >= 6 else [],
                }
                matches.append(match_info)

    return matches


if __name__ == '__main__':
    import os
    matches = fetch_jczq_matches()
    out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'jczq_matches.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(matches)} matches to {out_path}")
