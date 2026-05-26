#!/usr/bin/env python3
"""
每日自动预测脚本 — GitHub Actions 触发
从 today_matches.json 加载比赛列表, 运行预测, 输出到 docs/
"""
import sys, os, json
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

# Add skill package to path
SKILL_PATH = Path(__file__).parent.parent.parent / "football-prediction-skill"
if SKILL_PATH.exists():
    sys.path.insert(0, str(SKILL_PATH))

try:
    from football_predictor.predict import FootballPredictor
    from football_predictor.report import generate_full_report
    from football_predictor.config import LEAGUE_MAP
except ImportError:
    print("Warning: football_predictor not available. Running in standalone mode.")
    FootballPredictor = None

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
RESULTS_DIR = BASE / "models" / "results"  # 与 EvolutionEngine 统一路径
DOCS_DIR = BASE / "docs"
TODAY = os.environ.get("PREDICTION_DATE") or datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

# Default fallback matches — edit this or create data/today_matches.json
FALLBACK_MATCHES = [
    {"lg": "E0", "home": "Arsenal", "away": "Chelsea"},
    {"lg": "E0", "home": "Man City", "away": "Liverpool"},
    {"lg": "D1", "home": "Bayern Munich", "away": "Dortmund"},
    {"lg": "I1", "home": "Inter", "away": "Milan"},
    {"lg": "SP1", "home": "Barcelona", "away": "Real Madrid"},
    {"lg": "F1", "home": "PSG", "away": "Marseille"},
]

MATCHES_JSON = BASE / "data" / "today_matches.json"
NEUTRAL_FLAGS = {}

def load_matches():
    if MATCHES_JSON.exists():
        data = json.loads(MATCHES_JSON.read_text(encoding='utf-8'))
        matches = [(m['lg'], m['home'], m['away']) for m in data.get('matches', [])]
        for m in data.get('matches', []):
            if m.get('neutral'):
                NEUTRAL_FLAGS[(m['home'], m['away'])] = True
        date = data.get('date', TODAY)
        return matches, date
    # Fallback
    return [(m['lg'], m['home'], m['away']) for m in FALLBACK_MATCHES], TODAY


def load_yesterday_results(today_str):
    """加载前一天的预测+实际结果"""
    try:
        dt = datetime.strptime(today_str, "%Y-%m-%d")
        yesterday = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return None, None

    result_path = RESULTS_DIR / f"{yesterday}.json"
    if not result_path.exists():
        return None, yesterday

    try:
        data = json.loads(result_path.read_text(encoding='utf-8'))
        # 过滤有实际结果的比赛
        review = {}
        for mid, rec in data.items():
            if rec.get('actual') is not None:
                review[mid] = rec
        return review, yesterday
    except (json.JSONDecodeError, FileNotFoundError):
        return None, yesterday


def main():
    print(f"=" * 60)
    print(f"  足彩预测SKIL — 每日自动预测")
    print(f"  日期: {TODAY}")
    print(f"  时间: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} CST")
    print(f"=" * 60)

    matches, pred_date = load_matches()
    print(f"\n比赛列表: {len(matches)} 场")

    # 加载昨日结果回顾
    yesterday_results, yesterday_date = load_yesterday_results(pred_date)

    predictions = []

    if FootballPredictor:
        try:
            predictor = FootballPredictor(base_path=BASE)
            predictor.load_data(matches_path=DATA_DIR / "Matches.csv",
                              elo_path=DATA_DIR / "EloRatings.csv")
            predictor.compute_elos()
            predictor.build_databases(reference_date=pred_date)

            if not predictor.load_models():
                print("Warning: No saved models. Using Elo+H2H+Baseline fusion only.")
            else:
                print(f"Models loaded. Accuracy: {predictor.metrics.get('accuracy', 0):.3f}")

            for lg, home, away in matches:
                is_neutral = NEUTRAL_FLAGS.get((home, away), False)
                p = predictor.predict_match(home, away, lg,
                                           match_date=pred_date,
                                           is_neutral=is_neutral)
                predictions.append(p)
                conf_bar = '|' + '#' * int(p['confidence'] * 25) + '-' * (25 - int(p['confidence'] * 25)) + '|'
                print(f"\n  [{p['league']}] {p['home_team']} vs {p['away_team']}")
                print(f"  预测: {p['prediction']}  置信: {conf_bar} {p['confidence']:.1%}")
                print(f"  概率: 主{p['home_prob']:.1%}/平{p['draw_prob']:.1%}/客{p['away_prob']:.1%}")
                print(f"  xG: {p['home_xg']:.2f}-{p['away_xg']:.2f} | Elo差: {p['elo_diff']:+.0f}")
        except Exception as e:
            print(f"Prediction error: {e}")
            import traceback; traceback.print_exc()
    else:
        print("No prediction engine available. Generating sample data.")
        # Generate sample predictions
        for lg, home, away in matches:
            league_name = LEAGUE_MAP.get(lg, lg) if 'LEAGUE_MAP' in dir() else lg
            predictions.append({
                'league': league_name, 'league_code': lg,
                'home_team': home, 'away_team': away,
                'home_prob': 0.42, 'draw_prob': 0.28, 'away_prob': 0.30,
                'prediction': '主胜', 'confidence': 0.42,
                'home_xg': 1.45, 'away_xg': 1.05, 'over25': 0.48,
                'elo_diff': 120, 'h2h_factor': 0.55,
                'spirit_h': 1.05, 'spirit_a': 0.98,
                'draw_signal': 0.25, 'is_intl': False,
            })

    # Save predictions JSON
    results = {}
    for p in predictions:
        match_id = f"{p['league_code']}_{p['home_team']}_{p['away_team']}_{pred_date}".replace(' ', '_')
        results[match_id] = {
            'match_id': match_id,
            'league': p['league'],
            'league_code': p['league_code'],
            'home_team': p['home_team'],
            'away_team': p['away_team'],
            'match_date': pred_date,
            'prediction': p,
            'actual': None,
            'analysis': None,
        }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS_DIR / f"{pred_date}.json"
    result_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, cls=NumpyEncoder), encoding='utf-8')

    # Generate report
    report = generate_full_report(predictions)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / f"prediction_{pred_date}.md").write_text(report, encoding='utf-8')

    # Generate HTML page for GitHub Pages
    html = generate_html_page(predictions, pred_date, yesterday_results, yesterday_date)
    (DOCS_DIR / "index.html").write_text(html, encoding='utf-8')

    # Update archive
    update_archive_html(predictions, pred_date)

    # Summary
    home_preds = sum(1 for p in predictions if p['prediction'] == '主胜')
    draw_preds = sum(1 for p in predictions if p['prediction'] == '平局')
    away_preds = sum(1 for p in predictions if p['prediction'] == '客胜')
    print(f"\n{'='*60}")
    print(f"  完成! 预测{len(predictions)}场 (主{home_preds}/平{draw_preds}/客{away_preds})")
    print(f"  报告: docs/index.html")
    print(f"{'='*60}")


def _component_bar(value, label, color='#4ecb71', max_w=20):
    """生成组件贡献条"""
    w = min(int(value * max_w), max_w)
    return f'<span style="color:{color}">{label}: {"|" + "#" * w + "-" * (max_w - w) + "|"} {value:.1%}</span>'


def _reasoning_text(p):
    """生成单场比赛的推理说明"""
    lines = []
    home = p['home_team']
    away = p['away_team']
    pred = p['prediction']

    # ML 组件
    ml_h = p.get('ml_home', 0)
    ml_line = f"ML集成模型(XGBoost+LightGBM+RF)预测主胜概率 {ml_h:.1%}"
    lines.append(ml_line)

    # Elo 组件
    elo_h = p.get('elo_home', 0)
    elo_diff = p.get('elo_diff', 0)
    if elo_diff > 0:
        elo_line = f"Elo评分: {home}高于{away} {elo_diff:.0f}分，主胜概率{elo_h:.1%}"
    elif elo_diff < 0:
        elo_line = f"Elo评分: {away}高于{home} {-elo_diff:.0f}分，主胜概率{elo_h:.1%}"
    else:
        elo_line = f"Elo评分: 两队实力接近 (差值{elo_diff:.0f})，主胜概率{elo_h:.1%}"
    lines.append(elo_line)

    # H2H
    h2h = p.get('h2h_factor', 0.5)
    if h2h > 0.55:
        h2h_line = f"历史交锋: {home}占优 (H2H因子 {h2h:.2f})"
    elif h2h < 0.45:
        h2h_line = f"历史交锋: {away}占优 (H2H因子 {h2h:.2f})"
    else:
        h2h_line = f"历史交锋: 两队均势 (H2H因子 {h2h:.2f})"
    lines.append(h2h_line)

    # 战意
    sh = p.get('spirit_h', 1.0)
    sa = p.get('spirit_a', 1.0)
    if sh > sa + 0.05:
        lines.append(f"战意因子: {home}({sh:.2f}) > {away}({sa:.2f})，主队战意更强")
    elif sa > sh + 0.05:
        lines.append(f"战意因子: {away}({sa:.2f}) > {home}({sh:.2f})，客队战意更强")
    else:
        lines.append(f"战意因子: 两队接近 ({home} {sh:.2f}, {away} {sa:.2f})")

    # 伤病
    ih = p.get('inj_h', 0)
    ia = p.get('inj_a', 0)
    if ih > 0 or ia > 0:
        lines.append(f"伤病影响: {home} -{ih:.1%}, {away} -{ia:.1%}")

    # 赔率
    lines.append(f"市场赔率隐含: 主{p.get('ml_home', 0):.1%}/平{p.get('draw_prob', 0):.1%}/客{p.get('away_prob', 0):.1%}")

    # xG
    lines.append(f"预期进球xG: {home} {p['home_xg']:.2f} - {away} {p['away_xg']:.2f}")

    # 综合判断
    conf = p.get('confidence', 0)
    if conf > 0.45:
        conf_desc = "高置信度"
    elif conf > 0.35:
        conf_desc = "中等置信度"
    else:
        conf_desc = "低置信度 (比赛不确定性大)"

    if p.get('draw_signal', 0) > 0.6:
        lines.append(f"⚠ 平局信号较强 ({p.get('draw_signal', 0):.2f})，关注平局可能")
    lines.append(f"综合判断: {pred} ({conf_desc}, 置信度 {conf:.1%})")

    return lines


def generate_html_page(predictions, pred_date, yesterday_results=None, yesterday_date=None):
    """生成当天预测的HTML页面 — 包含详细推理、数据来源和昨日回顾"""
    # 昨日回顾 HTML
    yesterday_html = ""
    yesterday_stats = None
    if yesterday_results and yesterday_date:
        correct = 0
        total = len(yesterday_results)
        review_cards = []
        for mid, rec in yesterday_results.items():
            actual = rec['actual']
            pred = rec.get('prediction', {})
            pred_result = pred.get('prediction', '?')
            actual_result = {'H': '主胜', 'D': '平局', 'A': '客胜'}.get(actual['ft_result'], actual['ft_result'])
            is_correct = (pred_result == actual_result)
            if is_correct:
                correct += 1

            card_class = 'review-correct' if is_correct else 'review-wrong'
            icon = '✓' if is_correct else '✗'
            icon_color = '#4ecb71' if is_correct else '#e74c3c'

            review_cards.append(f'''
            <div class="review-card {card_class}">
              <div class="review-icon" style="color:{icon_color}">{icon}</div>
              <div class="review-teams">{rec['home_team']} <span class="vs">vs</span> {rec['away_team']}</div>
              <div class="review-league">{rec.get('league', '')}</div>
              <div class="review-compare">
                <div>预测: <b style="color:{'#4ecb71' if pred_result=='主胜' else '#f39c12' if pred_result=='平局' else '#e74c3c'}">{pred_result}</b> (H:{pred.get('home_prob',0):.1%} D:{pred.get('draw_prob',0):.1%} A:{pred.get('away_prob',0):.1%})</div>
                <div>实际: <b style="color:#ffd700">{actual['ft_home_goals']}:{actual['ft_away_goals']} ({actual_result})</b></div>
              </div>
            </div>''')

        acc = correct / total if total > 0 else 0
        yesterday_stats = {'total': total, 'correct': correct, 'accuracy': acc}
        yesterday_html = f'''
        <div class="yesterday-section">
          <h2>昨日回顾 — {yesterday_date}</h2>
          <div class="review-summary">
            <div class="review-stat"><span class="rlabel">比赛</span><span class="rvalue">{total}</span></div>
            <div class="review-stat"><span class="rlabel">命中</span><span class="rvalue" style="color:#4ecb71">{correct}</span></div>
            <div class="review-stat"><span class="rlabel">准确率</span><span class="rvalue" style="color:{'#4ecb71' if acc >= 0.5 else '#f39c12'}">{acc:.1%}</span></div>
          </div>
          <div class="review-grid">
            {''.join(review_cards)}
          </div>
        </div>'''

    # 今日预测卡片
    cards = []
    for p in predictions:
        conf_color = '#4ecb71' if p['confidence'] > 0.45 else ('#f39c12' if p['confidence'] > 0.35 else '#8899aa')
        pred_color = {'主胜': '#4ecb71', '平局': '#f39c12', '客胜': '#e74c3c'}.get(p['prediction'], '#8899aa')

        # 组件贡献条
        ml_bar = _component_bar(p.get('ml_home', 0.33), 'ML', '#4ecb71', 10)
        elo_bar = _component_bar(p.get('elo_home', 0.33), 'Elo', '#3498db', 10)
        h2h_bar = _component_bar(p.get('h2h_factor', 0.5), 'H2H', '#9b59b6', 8)
        spirit_val = (p.get('spirit_h', 1.0) / (p.get('spirit_h', 1.0) + p.get('spirit_a', 1.0)))
        spirit_bar = _component_bar(spirit_val, '战意', '#e67e22', 8)

        # 推理文本
        reasoning = _reasoning_text(p)
        reasoning_html = '<br>'.join(f'<span class="reason-line">{r}</span>' for r in reasoning)

        cards.append(f'''
        <div class="match-card">
          <div class="league-tag">{p['league']}</div>
          <div class="teams">{p['home_team']} <span class="vs">vs</span> {p['away_team']}</div>
          <div class="probs">
            <span class="prob home">主{p['home_prob']:.1%}</span>
            <span class="prob draw">平{p['draw_prob']:.1%}</span>
            <span class="prob away">客{p['away_prob']:.1%}</span>
          </div>
          <div class="pred-row">
            <span class="prediction" style="color:{pred_color}">{p['prediction']}</span>
            <span class="confidence" style="color:{conf_color}">{p['confidence']:.1%}</span>
          </div>
          <div class="component-bars">
            {ml_bar}<br>{elo_bar}<br>{h2h_bar}<br>{spirit_bar}
          </div>
          <div class="xg">xG {p['home_xg']:.1f}-{p['away_xg']:.1f} | Elo差 {p['elo_diff']:+.0f} | 大2.5 {p.get('over25', 0):.1%}</div>
          <details class="reasoning">
            <summary>预测推理过程</summary>
            <div class="reasoning-body">{reasoning_html}</div>
          </details>
        </div>''')

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>足彩预测SKIL — {pred_date}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', sans-serif; background: #0f1923; color: #e0e0e0; min-height: 100vh; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
header {{ text-align: center; padding: 30px 0; border-bottom: 2px solid #1a3a2a; margin-bottom: 30px; }}
header h1 {{ color: #4ecb71; font-size: 2em; }}
header .subtitle {{ color: #8899aa; margin-top: 8px; }}
header .date {{ color: #ffd700; font-size: 1.2em; margin-top: 4px; }}
.summary {{ display: flex; justify-content: center; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
.summary-item {{ background: #1a2a3a; padding: 12px 24px; border-radius: 8px; text-align: center; }}
.summary-item .label {{ font-size: 0.8em; color: #8899aa; }}
.summary-item .value {{ font-size: 1.4em; color: #4ecb71; font-weight: bold; }}
.match-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
.match-card {{ background: #1a2a3a; border-radius: 12px; padding: 18px; border-left: 3px solid #2a4a3a; }}
.league-tag {{ font-size: 0.75em; color: #8899aa; background: #0f1923; padding: 3px 10px; border-radius: 4px; display: inline-block; margin-bottom: 8px; }}
.teams {{ font-size: 1.1em; font-weight: bold; margin-bottom: 10px; }}
.vs {{ color: #667788; }}
.probs {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.9em; }}
.prob.home {{ color: #4ecb71; }} .prob.draw {{ color: #f39c12; }} .prob.away {{ color: #e74c3c; }}
.pred-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
.prediction {{ font-size: 1.2em; font-weight: bold; }}
.confidence {{ font-size: 1.1em; font-weight: bold; }}
.xg {{ color: #667788; font-size: 0.85em; margin-bottom: 4px; }}
.detail {{ color: #667788; font-size: 0.75em; }}
.component-bars {{ font-family: 'Courier New', monospace; font-size: 0.72em; color: #8899aa; margin: 8px 0; line-height: 1.6; }}
.reasoning {{ margin-top: 10px; border-top: 1px solid #2a4a3a; padding-top: 8px; }}
.reasoning summary {{ color: #4ecb71; cursor: pointer; font-size: 0.85em; padding: 4px 0; }}
.reasoning summary:hover {{ color: #5edc81; }}
.reasoning-body {{ background: #0f1923; border-radius: 6px; padding: 10px 12px; margin-top: 6px; font-size: 0.78em; color: #99aabb; line-height: 1.8; }}
.reason-line {{ display: block; padding: 1px 0; }}
footer {{ text-align: center; padding: 30px; color: #667788; font-size: 0.85em; border-top: 1px solid #2a3a4a; margin-top: 40px; }}
.data-sources {{ margin-top: 40px; padding: 20px; background: #1a2a3a; border-radius: 10px; }}
.data-sources h3 {{ color: #4ecb71; margin-bottom: 12px; }}
.data-sources ul {{ list-style: disc inside; color: #8899aa; line-height: 1.8; }}
a {{ color: #4ecb71; }}
.method-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85em; }}
.method-table th {{ background: #2a3a4a; color: #4ecb71; padding: 8px; text-align: left; }}
.method-table td {{ padding: 8px; border-bottom: 1px solid #2a3a4a; color: #99aabb; }}
.method-table tr:hover {{ background: #1a2a3a; }}
.learning-status {{ margin-top: 30px; padding: 20px; background: #1a2a3a; border-radius: 10px; border-left: 3px solid #4ecb71; }}
.learning-status h3 {{ color: #4ecb71; margin-bottom: 10px; }}
.yesterday-section {{ margin-bottom: 30px; padding: 20px; background: #1a2a3a; border-radius: 12px; border: 1px solid #2a4a3a; }}
.yesterday-section h2 {{ color: #ffd700; font-size: 1.3em; margin-bottom: 12px; }}
.review-summary {{ display: flex; gap: 20px; margin-bottom: 16px; }}
.review-stat {{ background: #0f1923; padding: 8px 16px; border-radius: 6px; text-align: center; }}
.rlabel {{ font-size: 0.75em; color: #8899aa; display: block; }}
.rvalue {{ font-size: 1.3em; font-weight: bold; display: block; }}
.review-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; }}
.review-card {{ background: #0f1923; border-radius: 8px; padding: 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }}
.review-correct {{ border-left: 3px solid #4ecb71; }}
.review-wrong {{ border-left: 3px solid #e74c3c; }}
.review-icon {{ font-size: 1.4em; font-weight: bold; width: 24px; text-align: center; }}
.review-teams {{ font-weight: bold; font-size: 0.9em; flex: 1; min-width: 120px; }}
.review-league {{ font-size: 0.7em; color: #667788; width: 100%; }}
.review-compare {{ font-size: 0.75em; color: #8899aa; width: 100%; line-height: 1.6; }}
</style>
</head>
<body>
<div class="container">
<header>
  <h1>足彩预测SKIL</h1>
  <div class="subtitle">6组件融合预测系统 — ML + Elo + H2H + Market + Baseline + Spirit</div>
  <div class="date">{pred_date} 比赛预测</div>
</header>

<div class="summary">
  <div class="summary-item"><span class="label">比赛总数</span><span class="value">{len(predictions)}</span></div>
  <div class="summary-item"><span class="label">主胜预测</span><span class="value">{sum(1 for p in predictions if p['prediction']=='主胜')}</span></div>
  <div class="summary-item"><span class="label">平局预测</span><span class="value">{sum(1 for p in predictions if p['prediction']=='平局')}</span></div>
  <div class="summary-item"><span class="label">客胜预测</span><span class="value">{sum(1 for p in predictions if p['prediction']=='客胜')}</span></div>
</div>

{yesterday_html}

<div class="match-grid">
{''.join(cards)}
</div>

<div class="data-sources">
  <h3>预测方法与数据来源</h3>
  <p style="color:#8899aa;margin-bottom:15px">每场比赛的预测结果由以下6个独立组件融合产生，点击比赛卡片中的"预测推理过程"查看各组件的具体贡献。</p>
  <table class="method-table">
    <tr><th>组件</th><th>权重</th><th>方法</th><th>数据来源</th></tr>
    <tr><td>ML集成</td><td>25%</td><td>XGBoost + LightGBM + RandomForest 三模型集成</td><td>xgabora 230K+场历史比赛 (2000-2026, 42个联赛)</td></tr>
    <tr><td>市场赔率</td><td>35%</td><td>庄家隐含概率反推 + 从Elo推导 (无真实赔率时)</td><td>Elo概率模型 + 赔率合成算法</td></tr>
    <tr><td>Elo评分</td><td>14%</td><td>双轨Elo系统: 俱乐部K=32, 国家队K=20-60</td><td>全历史比赛结果逐场计算</td></tr>
    <tr><td>基准模型</td><td>12%</td><td>泊松分布 + 联赛平均进球基准</td><td>各联赛历史进球统计</td></tr>
    <tr><td>H2H交锋</td><td>7%</td><td>近8场历史对战加权 (近期权重更高)</td><td>历史比赛记录</td></tr>
    <tr><td>战意因子</td><td>7%</td><td>积分榜位置分析 (争冠/欧战/保级激励)</td><td>联赛排名 + 赛事重要性权重</td></tr>
  </table>
  <p style="color:#667788;font-size:0.8em;margin-top:12px">
    融合公式: P_final = w1*P_ml + w2*P_market + w3*P_elo + w4*P_baseline + w5*P_h2h + w6*P_spirit<br>
    权重通过指数化梯度下降自进化: w_new = w * exp(-lr * grad), 然后simplex归一化
  </p>
</div>

<div class="learning-status">
  <h3>自学习状态</h3>
  <p style="color:#8899aa">每次比赛结果确认后，系统自动执行:</p>
  <ol style="color:#8899aa;line-height:2;margin-left:20px">
    <li>计算各组件预测梯度 → 指数化权重更新</li>
    <li>平局检测阈值自适应优化</li>
    <li>概率校准 (Isotonic Regression)</li>
    <li>特征有效性评分 → 低效特征自动修剪</li>
    <li>知识库迁移 → 新旧权重平滑过渡</li>
  </ol>
</div>

<footer>
  <p>足彩预测SKIL v3.0.0 | 自动生成于 {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')} CST</p>
  <p>!! 本预测仅供参考, 足球比赛存在较大不确定性, 理性购彩 !!</p>
  <p><a href="archive.html">历史预测归档</a> | <a href="https://github.com/cjtdawn-cn/football-prediction-auto">GitHub</a></p>
</footer>
</div>
</body>
</html>'''


def update_archive_html(predictions, pred_date):
    """更新归档页面"""
    archive_path = DOCS_DIR / "archive.html"
    entry = f'<li><a href="index.html">{pred_date}</a> — {len(predictions)}场预测</li>'

    if archive_path.exists():
        content = archive_path.read_text(encoding='utf-8')
        if pred_date not in content:
            content = content.replace('<!-- NEW_ENTRY -->', f'{entry}\n<!-- NEW_ENTRY -->')
        archive_path.write_text(content, encoding='utf-8')
    else:
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>预测归档 — 足彩预测SKIL</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', sans-serif; background: #0f1923; color: #e0e0e0; }}
.container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #4ecb71; }}
ul {{ list-style: none; padding: 0; }}
li {{ padding: 10px; border-bottom: 1px solid #2a4a3a; }}
a {{ color: #4ecb71; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="container">
<h1>历史预测归档</h1>
<ul>
<!-- NEW_ENTRY -->
{entry}
<!-- NEW_ENTRY -->
</ul>
<p><a href="index.html">返回最新预测</a></p>
</div>
</body>
</html>'''
        archive_path.write_text(html, encoding='utf-8')


if __name__ == '__main__':
    main()
