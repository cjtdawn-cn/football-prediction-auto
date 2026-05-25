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
RESULTS_DIR = BASE / "results"
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


def main():
    print(f"=" * 60)
    print(f"  足彩预测SKIL — 每日自动预测")
    print(f"  日期: {TODAY}")
    print(f"  时间: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} CST")
    print(f"=" * 60)

    matches, pred_date = load_matches()
    print(f"\n比赛列表: {len(matches)} 场")

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
    html = generate_html_page(predictions, pred_date, results)
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


def generate_html_page(predictions, pred_date, results):
    """生成当天预测的HTML页面"""
    cards = []
    for p in predictions:
        conf_color = '#4ecb71' if p['confidence'] > 0.45 else ('#f39c12' if p['confidence'] > 0.35 else '#8899aa')
        pred_color = {'主胜': '#4ecb71', '平局': '#f39c12', '客胜': '#e74c3c'}.get(p['prediction'], '#8899aa')
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
          <div class="xg">xG {p['home_xg']:.1f}-{p['away_xg']:.1f} | Elo差 {p['elo_diff']:+.0f}</div>
          <div class="detail">
            <small>ML主{p.get('ml_home', 0):.1%} | Elo主{p.get('elo_home', 0):.1%} | H2H {p.get('h2h_factor', 0):.2f}</small>
          </div>
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
footer {{ text-align: center; padding: 30px; color: #667788; font-size: 0.85em; border-top: 1px solid #2a3a4a; margin-top: 40px; }}
.data-sources {{ margin-top: 40px; padding: 20px; background: #1a2a3a; border-radius: 10px; }}
.data-sources h3 {{ color: #4ecb71; margin-bottom: 12px; }}
.data-sources ul {{ list-style: disc inside; color: #8899aa; line-height: 1.8; }}
a {{ color: #4ecb71; }}
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

<div class="match-grid">
{''.join(cards)}
</div>

<div class="data-sources">
  <h3>预测数据来源</h3>
  <ul>
    <li><strong>ML模型</strong>: XGBoost + LightGBM + RandomForest Ensemble, 训练数据 ~230K场 (2000-2026, 42个联赛)</li>
    <li><strong>Elo评分</strong>: 双轨系统 — 俱乐部K=32 + 国家队K=20-60 (基于赛事重要性)</li>
    <li><strong>H2H历史</strong>: 近8场对战记录加权</li>
    <li><strong>市场赔率</strong>: 隐含概率合成 (当无真实赔率时从Elo推导)</li>
    <li><strong>泊松xG</strong>: 联赛基准 + 球队攻防因子 + Elo调节</li>
    <li><strong>战意因子</strong>: 积分榜位置分析 (争冠/欧战/保级加成)</li>
    <li><strong>自进化引擎</strong>: 指数化梯度下降优化6组件权重, 每次结果反馈触发在线学习</li>
  </ul>
</div>

<footer>
  <p>足彩预测SKIL v3.0.0 | 自动生成于 {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')} CST</p>
  <p>!! 本预测仅供参考, 足球比赛存在较大不确定性, 理性购彩 !!</p>
  <p><a href="archive.html">历史预测归档</a></p>
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
