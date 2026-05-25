#!/usr/bin/env python3
"""
自学习反馈闭环 — 检查过往预测结果, 与实际比赛结果对比, 触发进化引擎学习
"""
import sys, json
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE = Path(__file__).parent.parent
RESULTS_DIR = BASE / "results"
KB_PATH = BASE / "data" / "knowledge_base.json"


def check_results():
    """扫描 results/ 目录, 找出有预测但未录入结果的比赛, 尝试从网络获取结果"""
    updated = 0

    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            continue

        for match_id, rec in data.items():
            if rec.get('actual') is not None:
                continue  # 已有结果

            match_date = rec.get('match_date', f.stem)
            try:
                match_dt = datetime.strptime(match_date, "%Y-%m-%d")
            except ValueError:
                continue

            # 只检查已过去的比赛
            now = datetime.now(timezone(timedelta(hours=8)))
            if match_dt.date() >= now.date():
                continue

            # 尝试从 football-data.org API 获取结果 (免费层)
            result = fetch_result_from_api(rec)
            if result:
                rec['actual'] = result
                # 更新统计
                pred = rec.get('prediction', {})
                outcome_map = {"主胜": "H", "平局": "D", "客胜": "A"}
                pred_outcome = pred.get('predicted_outcome', pred.get('prediction', ''))
                correct = outcome_map.get(pred_outcome) == result['ft_result']

                y = {'H': [1,0,0], 'D': [0,1,0], 'A': [0,0,1]}[result['ft_result']]
                p = [pred.get('home_prob', 0.33), pred.get('draw_prob', 0.33), pred.get('away_prob', 0.34)]
                brier = sum((p[i] - y[i])**2 for i in range(3)) / 3.0

                rec['analysis'] = {
                    'prediction_correct': correct,
                    'brier_score': brier,
                    'goal_error': abs(pred.get('home_xg', 0) - result['ft_home_goals']) +
                                 abs(pred.get('away_xg', 0) - result['ft_away_goals']),
                }
                updated += 1
                print(f"  Updated: {match_id} → {result['ft_home_goals']}:{result['ft_away_goals']} ({result['ft_result']})")

        if updated > 0:
            tmp = str(f) + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as fout:
                json.dump(data, fout, indent=2, ensure_ascii=False)
            Path(tmp).replace(f)

    return updated


def fetch_result_from_api(rec):
    """从公开API获取比赛结果 (降级策略)"""
    home = rec.get('home_team', '')
    away = rec.get('away_team', '')
    match_date = rec.get('match_date', '')

    # 注意: 免费API有限制, 这里作为框架模板
    # 实际使用时需要接入: football-data.org API key 或 soccerway/fotmob 爬虫
    # GitHub Actions 环境频率限制较严格

    # 尝试方式1: football-data.org (需要API key)
    # 尝试方式2: 从本地CSV查找 (如果数据已下载)
    # 当前返回None表示需要手动录入

    return None


def update_knowledge_base():
    """优化知识库 (基于已有结果)"""
    if not KB_PATH.exists():
        return

    try:
        kb = json.loads(KB_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, FileNotFoundError):
        return

    total_recorded = 0
    total_correct = 0

    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            continue

        for match_id, rec in data.items():
            analysis = rec.get('analysis')
            if analysis:
                total_recorded += 1
                if analysis.get('prediction_correct'):
                    total_correct += 1

    kb['total_matches_recorded'] = total_recorded
    kb['total_matches_correct'] = total_correct
    kb['last_updated'] = datetime.now(timezone(timedelta(hours=8))).isoformat()

    # 更新滚动表现
    now = datetime.now(timezone(timedelta(hours=8)))
    for window_key, days in [('last_7_days', 7), ('last_30_days', 30), ('last_90_days', 90)]:
        cutoff = (now - timedelta(days=days)).strftime('%Y-%m-%d')
        total = correct = 0
        brier_sum = 0.0
        for f in sorted(RESULTS_DIR.glob("*.json")):
            if f.stem < cutoff:
                continue
            data = json.loads(f.read_text(encoding='utf-8'))
            for mid, rec in data.items():
                a = rec.get('analysis')
                if a:
                    total += 1
                    if a.get('prediction_correct'):
                        correct += 1
                    brier_sum += a.get('brier_score', 0)

        wp = kb.setdefault('rolling_performance', {}).setdefault(window_key, {})
        wp['total'] = total
        wp['correct'] = correct
        wp['accuracy'] = correct / total if total > 0 else 0
        wp['avg_brier'] = brier_sum / total if total > 0 else 0

    # 保存
    tmp = str(KB_PATH) + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)
    Path(tmp).replace(KB_PATH)

    print(f"  KB updated: {total_recorded} matches, {total_correct/total_recorded:.1%} accuracy"
          if total_recorded > 0 else "  KB: no matches yet")


def main():
    print("=" * 50)
    print("  自学习反馈闭环")
    print("=" * 50)

    updated = check_results()
    print(f"\n结果更新: {updated} 场")

    if updated > 0:
        update_knowledge_base()
        print("知识库已优化")

    print("\n反馈闭环完成")


if __name__ == '__main__':
    main()
