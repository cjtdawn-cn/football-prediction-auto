#!/usr/bin/env python3
"""
每日自动预测脚本 — GitHub Actions 触发
从 today_matches.json 加载比赛列表, 运行预测, 输出到 docs/
"""
import sys, os, json, math
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ============================================================
# 队名中英文映射表 — 持续扩充
# ============================================================
TEAM_CN = {
    # 英超
    "Arsenal": "阿森纳", "Chelsea": "切尔西", "Man City": "曼城", "Liverpool": "利物浦",
    "Man United": "曼联", "Tottenham": "热刺", "Newcastle": "纽卡斯尔", "Aston Villa": "阿斯顿维拉",
    "Brighton": "布莱顿", "West Ham": "西汉姆联", "Crystal Palace": "水晶宫", "Brentford": "布伦特福德",
    "Fulham": "富勒姆", "Wolves": "狼队", "Everton": "埃弗顿", "Nott'm Forest": "诺丁汉森林",
    "Bournemouth": "伯恩茅斯", "Leicester": "莱斯特城", "Leeds": "利兹联", "Southampton": "南安普顿",
    "Burnley": "伯恩利", "Sheffield Utd": "谢菲联", "Luton": "卢顿", "Ipswich": "伊普斯维奇",
    # 西甲
    "Barcelona": "巴塞罗那", "Real Madrid": "皇家马德里", "Ath Madrid": "马德里竞技",
    "Sevilla": "塞维利亚", "Valencia": "瓦伦西亚", "Real Sociedad": "皇家社会",
    "Betis": "皇家贝蒂斯", "Villarreal": "比利亚雷亚尔", "Ath Bilbao": "毕尔巴鄂竞技",
    "Osasuna": "奥萨苏纳", "Celta Vigo": "塞尔塔", "Mallorca": "马略卡", "Getafe": "赫塔费",
    "Girona": "赫罗纳", "Alaves": "阿拉维斯", "Las Palmas": "拉斯帕尔马斯",
    "Leganes": "莱加内斯", "Espanyol": "西班牙人", "Valladolid": "巴拉多利德",
    "Rayo Vallecano": "巴列卡诺",
    # 德甲
    "Bayern Munich": "拜仁慕尼黑", "Dortmund": "多特蒙德", "RB Leipzig": "莱比锡红牛",
    "Bayer Leverkusen": "勒沃库森", "Wolfsburg": "沃尔夫斯堡", "Eintracht Frankfurt": "法兰克福",
    "M'gladbach": "门兴", "Hoffenheim": "霍芬海姆", "Stuttgart": "斯图加特",
    "Freiburg": "弗赖堡", "Union Berlin": "柏林联合", "Werder Bremen": "不莱梅",
    "Augsburg": "奥格斯堡", "Bochum": "波鸿", "Heidenheim": "海登海姆",
    "St Pauli": "圣保利", "Holstein Kiel": "基尔",
    # 意甲
    "Inter": "国际米兰", "Milan": "AC米兰", "Juventus": "尤文图斯", "Napoli": "那不勒斯",
    "Atalanta": "亚特兰大", "Roma": "罗马", "Lazio": "拉齐奥", "Fiorentina": "佛罗伦萨",
    "Bologna": "博洛尼亚", "Torino": "都灵", "Monza": "蒙扎", "Udinese": "乌迪内斯",
    "Genoa": "热那亚", "Cagliari": "卡利亚里", "Como": "科莫", "Parma": "帕尔马",
    "Verona": "维罗纳", "Empoli": "恩波利", "Lecce": "莱切", "Venezia": "威尼斯",
    # 法甲
    "PSG": "巴黎圣日耳曼", "Marseille": "马赛", "Lyon": "里昂", "Monaco": "摩纳哥",
    "Lille": "里尔", "Rennes": "雷恩", "Nice": "尼斯", "Lens": "朗斯",
    "Strasbourg": "斯特拉斯堡", "Reims": "兰斯", "Montpellier": "蒙彼利埃", "Nantes": "南特",
    "Brest": "布雷斯特", "Toulouse": "图卢兹", "Auxerre": "欧塞尔",
    "Le Havre": "勒阿弗尔", "St Etienne": "圣埃蒂安", "Angers": "昂热",
    # 巴甲
    "Flamengo": "弗拉门戈", "Palmeiras": "帕尔梅拉斯", "Santos": "桑托斯",
    "Sao Paulo": "圣保罗", "Gremio": "格雷米奥", "Botafogo": "博塔弗戈",
    "Fluminense": "弗鲁米嫩", "Corinthians": "科林蒂安", "Cruzeiro": "克鲁塞罗",
    "Athletico-PR": "巴拉纳竞技", "Internacional": "巴西国际", "Fortaleza": "福塔莱萨",
    "Bahia": "巴伊亚", "Bragantino": "布拉甘蒂诺", "Vasco": "瓦斯科达伽马",
    "Atletico-MG": "米内罗竞技", "Atletico GO": "戈亚尼亚竞技", "Cuiaba": "库亚巴",
    "Juventude": "尤文图德", "Vitoria": "维多利亚", "Criciuma": "克里西乌马",
    # 南美俱乐部 (500.com 官方中文名)
    "Penarol": "佩纳罗尔", "Bolivar": "玻利瓦尔", "Libertad": "亚自由",
    "Rosario Central": "罗萨里奥", "Platense": "普拉滕斯",
    "Independiente del Valle": "德尔瓦耶", "Independiente Rivadavia": "里瓦达维亚独立",
    "Deportivo La Guaira": "拉瓜伊拉", "Universidad Central": "委内瑞拉中央大学",
    "Santa Fe": "圣菲独立", "Independiente": "独立竞技", "Racing Club": "竞技俱乐部",
    "River Plate": "河床", "Boca Juniors": "博卡青年", "Estudiantes": "拉普拉塔大学生",
    # 其他
    "Club Brugge": "布鲁日", "Anderlecht": "安德莱赫特", "Galatasaray": "加拉塔萨雷",
    "Fenerbahce": "费内巴切", "Besiktas": "贝西克塔斯",
}

def cn(name):
    """翻译队名为中文, 找不到则返回原文"""
    return TEAM_CN.get(name, name)


def load_jczq_data():
    """加载竞彩数据"""
    jczq_path = BASE / "data" / "jczq_matches.json"
    if jczq_path.exists():
        return json.loads(jczq_path.read_text(encoding='utf-8'))
    return []


def match_jczq(our_home, our_away, jczq_list):
    """将我们的预测匹配到竞彩比赛. 返回匹配的竞彩条目或 None.
    匹配策略: 1) 中文名完全匹配 2) 包含关系匹配"""
    our_home_cn = cn(our_home)
    our_away_cn = cn(our_away)

    for jm in jczq_list:
        jh = jm['home']
        ja = jm['away']
        # 完全匹配
        if our_home_cn == jh and our_away_cn == ja:
            return jm
        # 主队包含匹配
        if (our_home_cn in jh or jh in our_home_cn) and (our_away_cn in ja or ja in our_away_cn):
            return jm
        # 更模糊的匹配: 至少2个字的交集
        if len(our_home_cn) >= 2 and len(jh) >= 2:
            h_overlap = sum(1 for c in our_home_cn if c in jh) / max(len(our_home_cn), len(jh))
            a_overlap = sum(1 for c in our_away_cn if c in ja) / max(len(our_away_cn), len(ja))
            if h_overlap > 0.5 and a_overlap > 0.5:
                return jm
    return None


def compare_odds(model_prob, jczq_odd):
    """对比模型公允赔率 vs 竞彩赔率, 返回差值分析.
    正差值 = 竞彩赔率高于模型公允 = 有价值"""
    fair_odd = 1.0 / model_prob if model_prob > 0.01 else 99
    diff = jczq_odd - fair_odd
    if diff > 0.15:
        return 'value', f'竞彩高估 +{diff:.2f}'
    elif diff < -0.15:
        return 'avoid', f'竞彩低估 {diff:.2f}'
    else:
        return 'fair', '基本吻合'


def poisson_total_goals_probs(home_xg, away_xg, max_goals=6):
    """用 Poisson 分布计算总进球数概率分布.
    返回: {0: P0, 1: P1, ..., '5+': P5+}, most_likely, low_score_prob
    low_score_prob = P(0球) + P(1球)
    """
    def poisson_pmf(k, lam):
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return math.exp(-lam) * (lam ** k) / math.factorial(k)

    total_probs = {}
    for total_k in range(max_goals):
        prob = 0.0
        for h_k in range(total_k + 1):
            a_k = total_k - h_k
            prob += poisson_pmf(h_k, home_xg) * poisson_pmf(a_k, away_xg)
        total_probs[total_k] = prob

    # 5+ goals
    total_probs['5+'] = 1.0 - sum(total_probs[k] for k in range(max_goals))

    most_likely = max(range(max_goals), key=lambda k: total_probs[k])
    low_score_prob = total_probs[0] + total_probs[1]

    return total_probs, most_likely, low_score_prob


# ============================================================
# 竞彩赔率修正 — 公允概率 → 竞彩赔率 (加 ~10% 抽水)
# ============================================================
LOTTERY_MARGIN = float(os.environ.get("LOTTERY_MARGIN", "0.10"))


def fair_to_lottery_odds(home_prob, draw_prob, away_prob, margin=LOTTERY_MARGIN):
    """公允概率加抽水转竞彩赔率. 返回 spf_odds = (主赔, 平赔, 客赔)"""
    scale = 1.0 + margin
    h_odd = 1.0 / (home_prob * scale) if home_prob > 0.001 else 50.0
    d_odd = 1.0 / (draw_prob * scale) if draw_prob > 0.001 else 50.0
    a_odd = 1.0 / (away_prob * scale) if away_prob > 0.001 else 50.0
    return round(h_odd, 2), round(d_odd, 2), round(a_odd, 2)


def predict_lottery_full(home_xg, away_xg, home_prob, draw_prob, away_prob, handicap=None):
    """从 xG + 概率生成竞彩五大玩法完整预测.
    返回 dict:
      - spf: 胜平负赔率
      - rqspf: 让球胜平负赔率 (如果提供了让球数)
      - score: [{比分, 概率}, ...] 最可能的比分
      - total_goals: 竞彩总进球格式 {球数: 赔率}
      - ht_ft: 半全场预测 [{组合, 概率, 赔率}, ...]
      - suggestions: 建议投注 [{类型, 选项, 赔率, 理由}, ...]
    """
    result = {}

    # ---- 1. 胜平负 ----
    spf = fair_to_lottery_odds(home_prob, draw_prob, away_prob)
    result['spf'] = {'主胜': spf[0], '平局': spf[1], '客胜': spf[2]}

    # ---- 1b. 让球胜平负 (Poisson + handicap) ----
    result['rqspf'] = None
    if handicap is not None:
        def poisson_pmf_rq(k, lam):
            if lam <= 0:
                return 1.0 if k == 0 else 0.0
            return math.exp(-lam) * (lam ** k) / math.factorial(k)

        h_win = 0.0; h_draw = 0.0; h_lose = 0.0
        for hg in range(12):
            for ag in range(12):
                p = poisson_pmf_rq(hg, home_xg) * poisson_pmf_rq(ag, away_xg)
                adj_hg = hg + handicap  # 让球后主队得分
                if adj_hg > ag:
                    h_win += p
                elif adj_hg == ag:
                    h_draw += p
                else:
                    h_lose += p
        rq_spf = fair_to_lottery_odds(h_win, h_draw, h_lose)
        result['rqspf'] = {'主胜': rq_spf[0], '平局': rq_spf[1], '客胜': rq_spf[2],
                           'handicap': handicap,
                           'probs': [round(h_win, 4), round(h_draw, 4), round(h_lose, 4)]}

    # ---- 2. 比分预测 (Poisson) ----
    def poisson_pmf(k, lam):
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return math.exp(-lam) * (lam ** k) / math.factorial(k)

    score_probs = []
    for h in range(6):
        for a in range(6):
            p = poisson_pmf(h, home_xg) * poisson_pmf(a, away_xg)
            if p > 0.005:  # 只保留 > 0.5% 的比分
                score_probs.append({'score': f"{h}:{a}", 'prob': p, 'home': h, 'away': a})
    score_probs.sort(key=lambda x: x['prob'], reverse=True)
    # 给每个比分加上赔率
    for s in score_probs[:12]:
        s['lottery_odds'] = round(1.0 / (s['prob'] * (1 + LOTTERY_MARGIN)), 2)
    result['scores'] = score_probs[:12]

    # ---- 3. 总进球 (竞彩格式: 0,1,2,3,4,5,6,7+) ----
    total_probs, most_likely, low_risk = poisson_total_goals_probs(home_xg, away_xg, max_goals=8)
    goals_lottery = {}
    for k in range(7):  # 0-6球
        p = total_probs.get(k, 0)
        goals_lottery[k] = round(1.0 / (p * (1 + LOTTERY_MARGIN)), 2) if p > 0.01 else 99.0
    p7plus = total_probs.get('5+', 0)  # 这里 '5+' 其实是 >=5
    # 重新算 >=7
    p7plus_real = 1.0 - sum(total_probs.get(k, 0) for k in range(7))
    goals_lottery['7+'] = round(1.0 / (p7plus_real * (1 + LOTTERY_MARGIN)), 2) if p7plus_real > 0.01 else 99.0
    result['total_goals'] = goals_lottery
    result['total_goals_most_likely'] = most_likely

    # ---- 4. 半全场 (Half-time / Full-time) ----
    # 半场 xG ≈ 全场 xG * 0.44 (上半场进球略少于下半场)
    ht_hxg = home_xg * 0.44
    ht_axg = away_xg * 0.44
    # 计算半场胜平负概率
    ht_home_prob = 0.0; ht_draw_prob = 0.0; ht_away_prob = 0.0
    for h in range(8):
        for a in range(8):
            p = poisson_pmf(h, ht_hxg) * poisson_pmf(a, ht_axg)
            if h > a:
                ht_home_prob += p
            elif h == a:
                ht_draw_prob += p
            else:
                ht_away_prob += p
    # 半场三种结果
    ht_results = [
        ('胜', ht_home_prob),
        ('平', ht_draw_prob),
        ('负', ht_away_prob),
    ]
    # 全场三种结果 (从传入概率)
    ft_results = [
        ('胜', home_prob),
        ('平', draw_prob),
        ('负', away_prob),
    ]
    # 9种联合结果 (假设半场和全场独立 — 简化模型)
    ht_ft = []
    for ht_label, ht_p in ht_results:
        for ft_label, ft_p in ft_results:
            joint_p = ht_p * ft_p  # 简化独立性假设
            combo = f"{ht_label}{ft_label}"  # 如 "胜胜", "平胜", etc.
            odd = round(1.0 / (joint_p * (1 + LOTTERY_MARGIN)), 2) if joint_p > 0.01 else 99.0
            ht_ft.append({'combo': combo, 'prob': joint_p, 'lottery_odds': odd})
    ht_ft.sort(key=lambda x: x['prob'], reverse=True)
    result['ht_ft'] = ht_ft

    # ---- 5. 混合过关 ----
    # 给出该场比赛最有价值的投注组合建议
    suggestions = []
    # 比分推荐
    top_score = score_probs[0] if score_probs else None
    if top_score:
        suggestions.append({
            'type': '比分',
            'pick': top_score['score'],
            'odds': top_score.get('lottery_odds', 99),
            'reason': f"最可能比分, 概率{top_score['prob']:.1%}"
        })
    # 总进球推荐
    if most_likely >= 2:
        suggestions.append({
            'type': '总进球',
            'pick': f"{most_likely}球",
            'odds': goals_lottery.get(most_likely, 99),
            'reason': f"最可能总进球, 概率{total_probs.get(most_likely, 0):.1%}"
        })
    # 低进球特殊推荐
    if low_risk > 0.35:
        suggestions.append({
            'type': '总进球',
            'pick': '0-1球',
            'odds': round(1.0 / (low_risk * (1 + LOTTERY_MARGIN)), 2),
            'reason': f"低进球警报, 0-1球概率{low_risk:.1%}"
        })
    result['suggestions'] = suggestions

    return result


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
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

    # 加载竞彩数据
    jczq_data = load_jczq_data()
    jczq_matched_ids = set()

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
                # 提前匹配竞彩 — 获取真实市场赔率用于增强预测
                jczq_match = match_jczq(home, away, jczq_data)

                p = predictor.predict_match(home, away, lg,
                                           match_date=pred_date,
                                           is_neutral=is_neutral)
                # 计算总进球分布
                goals_probs, most_likely_goals, low_score_prob = poisson_total_goals_probs(
                    p['home_xg'], p['away_xg'])
                p['goals_probs'] = goals_probs
                p['most_likely_goals'] = most_likely_goals
                p['low_score_prob'] = low_score_prob
                p['total_xg'] = p['home_xg'] + p['away_xg']

                # 匹配竞彩数据 + 市场赔率增强
                if jczq_match:
                    p['jczq'] = jczq_match
                    jczq_matched_ids.add((jczq_match['home'], jczq_match['away']))
                    # 从竞彩SPF赔率反推市场隐含概率 (去margin)
                    spf = jczq_match.get('spf_odds', [])
                    if len(spf) >= 3:
                        raw = [1.0/o for o in spf[:3]]
                        total_raw = sum(raw)
                        mkt_h = raw[0] / total_raw
                        mkt_d = raw[1] / total_raw
                        mkt_a = raw[2] / total_raw
                        # 数据质量: Elo差≈0 → 无历史数据 → 重度依赖市场
                        has_elo_data = abs(p['elo_diff']) > 3
                        if has_elo_data:
                            mkt_weight = 0.50  # 有Elo数据: 模型+市场各半
                        else:
                            mkt_weight = 0.88  # 无任何数据: 市场占88% (1/0.88≈1.14赔率边际)
                        # 融合模型预测 + 市场真实赔率
                        p['home_prob'] = p['home_prob'] * (1-mkt_weight) + mkt_h * mkt_weight
                        p['draw_prob'] = p['draw_prob'] * (1-mkt_weight) + mkt_d * mkt_weight
                        p['away_prob'] = p['away_prob'] * (1-mkt_weight) + mkt_a * mkt_weight
                        # 归一化
                        tp = p['home_prob'] + p['draw_prob'] + p['away_prob']
                        if tp > 1e-9:
                            p['home_prob'] /= tp; p['draw_prob'] /= tp; p['away_prob'] /= tp
                        # 更新预测和置信度
                        max_p = max(p['home_prob'], p['draw_prob'], p['away_prob'])
                        if p['home_prob'] == max_p:
                            p['prediction'] = '主胜'
                        elif p['draw_prob'] == max_p:
                            p['prediction'] = '平局'
                        else:
                            p['prediction'] = '客胜'
                        p['confidence'] = max_p
                        p['market_weight'] = mkt_weight
                    # 赔率对比 (用更新后的概率)
                    spf_labels = ['home', 'draw', 'away']
                    probs = [p['home_prob'], p['draw_prob'], p['away_prob']]
                    odd_comparisons = []
                    for i, (label, prob) in enumerate(zip(spf_labels, probs)):
                        j_odd = jczq_match['spf_odds'][i] if i < len(jczq_match['spf_odds']) else 0
                        tag, desc = compare_odds(prob, j_odd)
                        odd_comparisons.append({'label': label, 'jczq_odd': j_odd, 'fair_odd': round(1.0/prob, 2), 'tag': tag, 'desc': desc})
                    p['odd_comparison'] = odd_comparisons

                # 竞彩五大玩法完整预测
                hcap = jczq_match.get('handicap') if jczq_match else None
                try:
                    hcap_int = int(hcap) if hcap else None
                except (ValueError, TypeError):
                    hcap_int = None
                lottery = predict_lottery_full(
                    p['home_xg'], p['away_xg'],
                    p['home_prob'], p['draw_prob'], p['away_prob'],
                    handicap=hcap_int
                )
                p['lottery'] = lottery

                predictions.append(p)
                conf_bar = '|' + '#' * int(p['confidence'] * 25) + '-' * (25 - int(p['confidence'] * 25)) + '|'
                mkt_note = f' [市场权重: {p.get("market_weight", 0):.0%}]' if p.get('market_weight') else ''
                print(f"\n  [{p['league']}] {cn(p['home_team'])} vs {cn(p['away_team'])}")
                print(f"  预测: {p['prediction']}  置信: {conf_bar} {p['confidence']:.1%}{mkt_note}")
                print(f"  概率: 主{p['home_prob']:.1%}/平{p['draw_prob']:.1%}/客{p['away_prob']:.1%}")
                print(f"  xG: {p['home_xg']:.2f}-{p['away_xg']:.2f} | Elo差: {p['elo_diff']:+.0f}")
                print(f"  总进球: 最可能{most_likely_goals}球 | 低进球风险(0-1球): {low_score_prob:.1%}")
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

    # 收集未匹配的竞彩专有比赛
    extra_jczq = []
    for jm in jczq_data:
        key = (jm['home'], jm['away'])
        if key not in jczq_matched_ids:
            extra_jczq.append(jm)
    if extra_jczq:
        print(f"\n  竞彩专有比赛: {len(extra_jczq)} 场 (无模型预测, 仅展示竞彩赔率)")
        for jm in extra_jczq:
            print(f"    [{jm['league']}] {jm['home']} vs {jm['away']}  让球:{jm['handicap']}  SPF:{jm['spf_odds']}")

    # Generate HTML page for GitHub Pages
    html = generate_html_page(predictions, pred_date, yesterday_results, yesterday_date, extra_jczq)
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
    home = cn(p['home_team'])
    away = cn(p['away_team'])
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
    odd_h = 1.0 / max(p['home_prob'], 0.001)
    odd_d = 1.0 / max(p['draw_prob'], 0.001)
    odd_a = 1.0 / max(p['away_prob'], 0.001)
    lines.append(f"模型公允赔率: {odd_h:.2f} / {odd_d:.2f} / {odd_a:.2f}")

    # xG
    lines.append(f"预期进球xG: {home} {p['home_xg']:.2f} - {away} {p['away_xg']:.2f}")

    # 总进球预测
    total_xg = p.get('total_xg', p['home_xg'] + p['away_xg'])
    most_likely = p.get('most_likely_goals', 2)
    goals_probs = p.get('goals_probs', {})
    low_risk = p.get('low_score_prob', 0)
    if goals_probs:
        prob_parts = ', '.join(f"{k}球:{goals_probs[k]:.1%}" for k in [0, 1, 2, 3])
        prob_5plus = goals_probs.get('5+', 0)
        lines.append(f"总进球Poisson分布: {prob_parts}, 5+:{prob_5plus:.1%}")
        lines.append(f"预期总进球xG: {total_xg:.2f} | 最可能总进球: {most_likely}球")
        if low_risk > 0.25:
            lines.append(f"⚠ 低进球风险警告: 0-1球概率 {low_risk:.1%}，比赛可能沉闷")

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


def _rqspf_html(p):
    """生成让球胜平负 HTML"""
    lot = p.get('lottery', {})
    rqspf = lot.get('rqspf')
    if not rqspf:
        return ''
    hcap = rqspf.get('handicap', '')
    return f'''
    <div class="lottery-section">
      <span class="lottery-label">让球胜平负 (让{hcap})</span>
      <div class="rqspf-row">
        <div class="rqspf-item home"><span class="rq-label">主胜</span><span class="rq-odd">{rqspf['主胜']}</span></div>
        <div class="rqspf-item draw"><span class="rq-label">平局</span><span class="rq-odd">{rqspf['平局']}</span></div>
        <div class="rqspf-item away"><span class="rq-label">客胜</span><span class="rq-odd">{rqspf['客胜']}</span></div>
      </div>
    </div>'''


def _jczq_comparison_html(p):
    """生成竞彩赔率对比 HTML"""
    jczq = p.get('jczq')
    odd_comp = p.get('odd_comparison')
    if not jczq or not odd_comp:
        return ''

    tag_colors = {'value': '#4ecb71', 'avoid': '#e74c3c', 'fair': '#8899aa'}
    rows = ''
    labels = ['主胜', '平局', '客胜']
    for i, oc in enumerate(odd_comp):
        tc = tag_colors.get(oc['tag'], '#8899aa')
        icon = {'value': '▲', 'avoid': '▼', 'fair': '─'}.get(oc['tag'], '─')
        rows += f'<span class="odds-comp-row"><span class="odds-comp-label">{labels[i]}</span><span class="odds-comp-jc">竞彩 {oc["jczq_odd"]}</span><span class="odds-comp-fair">公允 {oc["fair_odd"]}</span><span class="odds-comp-tag" style="color:{tc}">{icon}</span></span>'

    handicap = jczq.get('handicap', '')
    hcap_str = f'让球 {handicap}' if handicap else ''

    # RQSFP comparison too
    rqspf_rows = ''
    rqspf = jczq.get('rqspf_odds', [])
    if rqspf and len(rqspf) >= 3:
        rq_labels = ['主胜', '平局', '客胜']
        for i, (rl, ro) in enumerate(zip(rq_labels, rqspf[:3])):
            rqspf_rows += f'<span class="odds-comp-row"><span class="odds-comp-label">{rl}</span><span class="odds-comp-jc">竞彩 {ro}</span><span class="odds-comp-fair"></span><span class="odds-comp-tag"></span></span>'

    rqspf_section = ''
    if rqspf_rows:
        rqspf_section = f'''
    <div style="margin-top:4px;padding-top:4px;border-top:1px solid #1a2a3a;">
      <div class="jczq-header" style="color:#f39c12;">竞彩让球SPF (让{handicap})</div>
      <div class="jczq-odds-rows">{rqspf_rows}</div>
    </div>'''

    return f'''
    <div class="jczq-compare">
      <div class="jczq-header">竞彩胜平负 (官方 vs 模型公允)</div>
      <div class="jczq-odds-rows">{rows}</div>{rqspf_section}
    </div>'''


def _generate_jczq_only_card(jm):
    """为竞彩独有比赛生成简化卡片 (无模型预测, 仅市场赔率反推)"""
    # 从竞彩赔率反推隐含概率 (去 margin)
    spf = jm.get('spf_odds', [])
    if len(spf) >= 3:
        raw_probs = [1.0/o for o in spf]
        total = sum(raw_probs)
        home_prob = raw_probs[0] / total
        draw_prob = raw_probs[1] / total
        away_prob = raw_probs[2] / total
        # 判定预测
        max_prob = max(home_prob, draw_prob, away_prob)
        if home_prob == max_prob:
            pred = '主胜'; conf = home_prob
        elif draw_prob == max_prob:
            pred = '平局'; conf = draw_prob
        else:
            pred = '客胜'; conf = away_prob
    else:
        home_prob = draw_prob = away_prob = 0.33
        pred = '数据不足'; conf = 0

    conf_bar = '|' + '#' * int(conf * 20) + '-' * (20 - int(conf * 20)) + '|'
    handicap = jm.get('handicap', '')
    rqspf = jm.get('rqspf_odds', [])

    # RQSFP display
    rqspf_html = ''
    if rqspf and len(rqspf) >= 3:
        rq_labels = ['主胜', '平局', '客胜']
        rqspf_html = '<div class="rqspf-row">' + ''.join(
            f'<div class="rqspf-item {"home" if i==0 else "draw" if i==1 else "away"}"><span class="rq-label">{l}</span><span class="rq-odd">{o}</span></div>'
            for i, (l, o) in enumerate(zip(rq_labels, rqspf[:3]))
        ) + '</div>'

    return f'''
    <div class="match-card jczq-only">
      <div class="card-header">
        <span class="league-tag">{jm['league']}</span>
        <span class="jczq-only-badge" style="font-size:0.65em;color:#ffd700;background:#2a2a1a;padding:2px 6px;border-radius:3px;">仅竞彩</span>
      </div>
      <div class="teams">{jm['home']} <span class="vs">vs</span> {jm['away']}</div>

      <div class="lottery-spf">
        <div class="spf-item home"><span class="spf-label">主胜</span><span class="spf-odd">{spf[0] if len(spf)>0 else '?'}</span></div>
        <div class="spf-item draw"><span class="spf-label">平局</span><span class="spf-odd">{spf[1] if len(spf)>1 else '?'}</span></div>
        <div class="spf-item away"><span class="spf-label">客胜</span><span class="spf-odd">{spf[2] if len(spf)>2 else '?'}</span></div>
      </div>

      <div class="probs" style="margin:6px 0;">
        <span class="prob home">主{home_prob:.1%}</span>
        <span class="prob draw">平{draw_prob:.1%}</span>
        <span class="prob away">客{away_prob:.1%}</span>
      </div>

      <div class="pred-row">
        <span class="prediction">{pred}</span>
        <span class="confidence">{conf_bar}</span>
      </div>

      {rqspf_html if rqspf_html else ''}

      <div class="xg" style="color:#667788;font-size:0.7em;margin-top:4px;">市场赔率反推 | 让球: {handicap}</div>
    </div>'''

def _generate_extra_jczq_section(extra_matches):
    """生成竞彩独有比赛区域"""
    if not extra_matches:
        return ''

    cards = ''.join(_generate_jczq_only_card(jm) for jm in extra_matches)

    return f'''
    <div style="margin-top:30px;">
      <h2 style="color:#ffd700;font-size:1.2em;margin-bottom:4px;">竞彩专有比赛</h2>
      <p style="color:#667788;font-size:0.8em;margin-bottom:12px;">以下比赛仅出现在竞彩足球中,
      无模型预测数据, 仅展示竞彩官方赔率及市场隐含概率。</p>
      <div class="match-grid">
        {cards}
      </div>
    </div>'''


def _generate_parlay_html(predictions):
    if len(predictions) < 2:
        return ''

    rows = ''
    # 2串1: 找置信度最高的2场
    top2 = sorted(predictions, key=lambda p: p['confidence'], reverse=True)[:2]
    combo_2 = 1.0
    for p in top2:
        combo_2 *= max(p['home_prob'], p['draw_prob'], p['away_prob'])
    odd_2 = round(1.0 / (combo_2 * (1 + LOTTERY_MARGIN)), 2)
    rows += f'''
    <tr>
      <td>2串1</td>
      <td>{cn(top2[0]['home_team'])} vs {cn(top2[0]['away_team'])} <b>{top2[0]['prediction']}</b> + {cn(top2[1]['home_team'])} vs {cn(top2[1]['away_team'])} <b style="color:#ffd700">{top2[1]['prediction']}</b></td>
      <td class="parlay-odd">@{odd_2}</td>
      <td class="parlay-risk">{'中' if top2[0]['confidence'] > 0.40 else '高'}风险</td>
    </tr>'''

    # 3串1: 找3场
    if len(predictions) >= 3:
        top3 = sorted(predictions, key=lambda p: p['confidence'], reverse=True)[:3]
        combo_3 = 1.0
        for p in top3:
            combo_3 *= max(p['home_prob'], p['draw_prob'], p['away_prob'])
        odd_3 = round(1.0 / (combo_3 * (1 + LOTTERY_MARGIN)), 2)
        names_3 = ' + '.join(f"{cn(pp['home_team'])}vs{cn(pp['away_team'])}<b>{pp['prediction']}</b>" for pp in top3)
        rows += f'''
    <tr>
      <td>3串1</td>
      <td>{names_3}</td>
      <td class="parlay-odd">@{odd_3}</td>
      <td class="parlay-risk">高风险</td>
    </tr>'''

    # 低进球串关 (选低进球概率最高的2场)
    low_matches = sorted([p for p in predictions if p.get('low_score_prob', 0) > 0.25],
                         key=lambda p: p['low_score_prob'], reverse=True)
    if len(low_matches) >= 2:
        lm2 = low_matches[:2]
        lm_combo = lm2[0]['low_score_prob'] * lm2[1]['low_score_prob']
        lm_odd = round(1.0 / (lm_combo * (1 + LOTTERY_MARGIN)), 2)
        rows += f'''
    <tr>
      <td>总进球串</td>
      <td>{cn(lm2[0]['home_team'])}vs{cn(lm2[0]['away_team'])} <b style="color:#ff6b6b">0-1球</b> + {cn(lm2[1]['home_team'])}vs{cn(lm2[1]['away_team'])} <b style="color:#ff6b6b">0-1球</b></td>
      <td class="parlay-odd">@{lm_odd}</td>
      <td class="parlay-risk">{'中' if lm_combo > 0.10 else '高'}风险</td>
    </tr>'''

    if not rows:
        return ''

    return f'''
    <div class="parlay-section">
      <h3>混合过关推荐</h3>
      <p style="color:#8899aa;font-size:0.8em;margin-bottom:10px">基于模型置信度+概率最优组合，仅供参考</p>
      <table class="parlay-table">
        <tr><th>类型</th><th>组合</th><th>赔率</th><th>风险</th></tr>
        {rows}
      </table>
    </div>'''


def generate_html_page(predictions, pred_date, yesterday_results=None, yesterday_date=None, extra_jczq=None):
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
              <div class="review-teams">{cn(rec['home_team'])} <span class="vs">vs</span> {cn(rec['away_team'])}</div>
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

        # 总进球预测
        gprobs = p.get('goals_probs', {})
        most_likely_g = p.get('most_likely_goals', 2)
        low_risk = p.get('low_score_prob', 0)
        total_xg = p.get('total_xg', p['home_xg'] + p['away_xg'])
        alert_badge = ''
        alert_class = ''
        if low_risk > 0.25:
            alert_level = 'high' if low_risk > 0.40 else 'medium'
            alert_class = f'alert-{alert_level}'
            alert_badge = f'<div class="low-score-alert {alert_class}">⚠ 低进球警报: 0-1球概率 {low_risk:.1%}</div>'

        goals_dist_html = ''
        if gprobs:
            bars = []
            for k in [0, 1, 2, 3, 4]:
                pct = gprobs.get(k, 0)
                w = int(pct * 40)
                highlight = 'style="color:#ffd700;font-weight:bold"' if k == most_likely_g else ''
                bars.append(f'<span class="goal-bar-row"><span class="goal-k">{"⚽" if k>0 else "0️⃣"} {k}球</span><span class="goal-pct" {highlight}>{pct:.1%}</span><span class="goal-vis-bar"><span class="goal-fill" style="width:{pct*200}px"></span></span></span>')
            p5 = gprobs.get('5+', 0)
            highlight5 = 'style="color:#ffd700;font-weight:bold"' if most_likely_g == '5+' else ''
            bars.append(f'<span class="goal-bar-row"><span class="goal-k">5+球</span><span class="goal-pct" {highlight5}>{p5:.1%}</span><span class="goal-vis-bar"><span class="goal-fill" style="width:{p5*200}px"></span></span></span>')
            goals_dist_html = f'<div class="goals-dist">{"".join(bars)}</div>'

        # 竞彩五大玩法
        lot = p.get('lottery', {})
        spf = lot.get('spf', {})
        scores = lot.get('scores', [])
        tg_odds = lot.get('total_goals', {})
        tg_most = lot.get('total_goals_most_likely', 2)
        ht_ft = lot.get('ht_ft', [])
        suggestions = lot.get('suggestions', [])

        # 比分预测 (前5名)
        score_lines = ''.join(
            f'<span class="score-chip{" top" if i==0 else ""}">{s["score"]}<small> {s["prob"]:.1%}</small></span>'
            for i, s in enumerate(scores[:6])
        )

        # 半全场 (前4名)
        ht_ft_lines = ''.join(
            f'<span class="htft-chip">{"{}{}{}".format(c["combo"][:1], "→", c["combo"][1:])}<small> {c["prob"]:.1%}</small></span>'
            for c in ht_ft[:4]
        )

        # 总进球 (竞彩格式: 0/1/2/3/4/5/6/7+)
        tg_chips = ''
        for kg in [0, 1, 2, 3, 4, 5, 6, '7+']:
            odd = tg_odds.get(kg, 99)
            hl = 'style="color:#ffd700;font-weight:bold"' if kg == tg_most else ''
            tg_chips += f'<span class="tg-chip" {hl}>{kg}球<small> {odd}</small></span>'

        # 投注建议
        sug_lines = ''
        for sug in suggestions:
            sug_lines += f'<span class="sug-item">[{sug["type"]}] {sug["pick"]} @{sug["odds"]} <small>{sug["reason"]}</small></span>'

        cards.append(f'''
        <div class="match-card {alert_class}">
          <div class="card-header">
            <span class="league-tag">{p['league']}</span>
            {alert_badge}
          </div>
          <div class="teams">{cn(p['home_team'])} <span class="vs">vs</span> {cn(p['away_team'])}</div>

          <!-- 胜平负赔率 -->
          <div class="lottery-spf">
            <div class="spf-item home"><span class="spf-label">主胜</span><span class="spf-odd">{spf.get('主胜', 99)}</span></div>
            <div class="spf-item draw"><span class="spf-label">平局</span><span class="spf-odd">{spf.get('平局', 99)}</span></div>
            <div class="spf-item away"><span class="spf-label">客胜</span><span class="spf-odd">{spf.get('客胜', 99)}</span></div>
          </div>

          <!-- 比分预测 -->
          <div class="lottery-section">
            <span class="lottery-label">比分</span>
            <div class="score-row">{score_lines}</div>
          </div>

          <!-- 总进球 -->
          <div class="lottery-section">
            <span class="lottery-label">总进球</span>
            <div class="tg-row">{tg_chips}</div>
          </div>

          <!-- 半全场 -->
          <div class="lottery-section">
            <span class="lottery-label">半全场</span>
            <div class="htft-row">{ht_ft_lines}</div>
          </div>

          <!-- 让球胜平负 -->
          {_rqspf_html(p)}

          <!-- 竞彩赔率对比 -->
          {_jczq_comparison_html(p)}

          <!-- 智能推荐 -->
          <div class="suggestions">{sug_lines}</div>

          <!-- xG 数据 -->
          <div class="xg">xG: {p['home_xg']:.2f}-{p['away_xg']:.2f} | 总xG: {total_xg:.2f} | Elo差: {p['elo_diff']:+.0f}</div>

          <details class="reasoning">
            <summary>预测推理过程 & 模型详情</summary>
            <div class="reasoning-body">
              <div class="component-bars">
                {ml_bar}<br>{elo_bar}<br>{h2h_bar}<br>{spirit_bar}
              </div>
              <div class="reason-divider"></div>
              {reasoning_html}
            </div>
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
.low-score-alert {{ margin-top: 8px; padding: 6px 10px; border-radius: 5px; font-size: 0.8em; font-weight: bold; text-align: center; }}
.alert-high {{ background: #3a1a1a; border: 1px solid #e74c3c; color: #ff6b6b; }}
.alert-medium {{ background: #3a2a1a; border: 1px solid #f39c12; color: #ffaa33; }}
.match-card.alert-high {{ border-left: 3px solid #e74c3c; }}
.match-card.alert-medium {{ border-left: 3px solid #f39c12; }}
.goals-pred {{ display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 0.82em; }}
.goals-label {{ color: #667788; }}
.goals-most-likely {{ }}
.goals-dist {{ margin-top: 6px; background: #0f1923; border-radius: 5px; padding: 6px 8px; }}
.goal-bar-row {{ display: flex; align-items: center; font-size: 0.72em; margin: 2px 0; gap: 6px; }}
.goal-k {{ color: #8899aa; width: 35px; text-align: right; flex-shrink: 0; }}
.goal-pct {{ color: #99aabb; width: 40px; text-align: right; flex-shrink: 0; }}
.goal-vis-bar {{ flex: 1; height: 6px; background: #2a3a4a; border-radius: 3px; overflow: hidden; }}
.goal-fill {{ display: block; height: 6px; background: linear-gradient(90deg, #4ecb71, #ffd700); border-radius: 3px; }}
.summary-alert {{ display: flex; justify-content: center; gap: 20px; margin-bottom: 15px; }}
.summary-alert-item {{ background: #3a1a1a; border: 1px solid #e74c3c; padding: 10px 20px; border-radius: 8px; text-align: center; }}
.odds-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.85em; }}
.odds-item {{ font-family: 'Courier New', monospace; font-weight: bold; }}
.odds-item.home {{ color: #4ecb71; }} .odds-item.draw {{ color: #f39c12; }} .odds-item.away {{ color: #e74c3c; }}
/* 竞彩五大玩法 */
.card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }}
.low-score-alert {{ padding: 3px 8px; border-radius: 4px; font-size: 0.7em; font-weight: bold; display: inline-block; }}
.lottery-spf {{ display: flex; gap: 6px; margin: 8px 0; }}
.spf-item {{ flex: 1; text-align: center; padding: 6px 4px; border-radius: 6px; }}
.spf-item.home {{ background: #1a3a2a; border: 1px solid #2a5a3a; }}
.spf-item.draw {{ background: #2a2a1a; border: 1px solid #5a4a2a; }}
.spf-item.away {{ background: #2a1a1a; border: 1px solid #5a2a2a; }}
.spf-label {{ display: block; font-size: 0.7em; color: #8899aa; }}
.spf-odd {{ display: block; font-size: 1.2em; font-weight: bold; font-family: 'Courier New', monospace; }}
.spf-item.home .spf-odd {{ color: #4ecb71; }}
.spf-item.draw .spf-odd {{ color: #f39c12; }}
.spf-item.away .spf-odd {{ color: #e74c3c; }}
.lottery-section {{ margin-top: 8px; }}
.lottery-label {{ font-size: 0.7em; color: #667788; display: block; margin-bottom: 3px; }}
.score-row {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.score-chip {{ background: #0f1923; padding: 2px 7px; border-radius: 3px; font-size: 0.78em; font-weight: bold; color: #ccddee; border: 1px solid #2a4a3a; }}
.score-chip.top {{ border-color: #ffd700; color: #ffd700; }}
.score-chip small {{ color: #8899aa; font-weight: normal; margin-left: 2px; }}
.htft-row {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.htft-chip {{ background: #1a1a2a; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; color: #99aaff; border: 1px solid #2a2a4a; }}
.htft-chip small {{ color: #667788; font-weight: normal; margin-left: 2px; }}
.tg-row {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.tg-chip {{ background: #0f1923; padding: 2px 5px; border-radius: 3px; font-size: 0.72em; color: #99aabb; border: 1px solid #2a3a4a; }}
.tg-chip small {{ color: #667788; margin-left: 1px; }}
.suggestions {{ margin-top: 8px; padding: 6px 8px; background: #1a2a1a; border-radius: 5px; border-left: 2px solid #4ecb71; }}
.sug-item {{ display: block; font-size: 0.72em; color: #4ecb71; padding: 1px 0; }}
.sug-item small {{ color: #8899aa; }}
.reason-divider {{ height: 1px; background: #2a4a3a; margin: 8px 0; }}
/* 竞彩赔率对比 */
.jczq-compare {{ margin-top: 8px; padding: 6px 8px; background: #0f1a2a; border-radius: 5px; border: 1px solid #2a4a6a; }}
.jczq-header {{ font-size: 0.72em; color: #4ecb71; margin-bottom: 4px; font-weight: bold; }}
.jczq-odds-rows {{ display: flex; flex-direction: column; gap: 2px; }}
.odds-comp-row {{ display: flex; align-items: center; gap: 6px; font-size: 0.72em; }}
.odds-comp-label {{ color: #8899aa; width: 28px; }}
.odds-comp-jc {{ color: #ffd700; font-family: 'Courier New', monospace; width: 55px; }}
.odds-comp-fair {{ color: #667788; font-family: 'Courier New', monospace; width: 55px; }}
.odds-comp-tag {{ font-weight: bold; width: 16px; text-align: center; }}
/* 让球盘 */
.rqspf-row {{ display: flex; gap: 4px; margin-top: 4px; }}
.rqspf-item {{ flex: 1; text-align: center; padding: 3px; border-radius: 4px; font-size: 0.7em; background: #121a24; border: 1px solid #1a2a3a; }}
.rqspf-item .rq-label {{ color: #667788; display: block; }}
.rqspf-item .rq-odd {{ font-family: 'Courier New', monospace; font-weight: bold; }}
.rqspf-item.home .rq-odd {{ color: #4ecb71; }}
.rqspf-item.draw .rq-odd {{ color: #f39c12; }}
.rqspf-item.away .rq-odd {{ color: #e74c3c; }}
/* 混合过关 */
.parlay-section {{ margin: 25px 0; padding: 20px; background: #1a2a3a; border-radius: 12px; border: 1px solid #ffd700; }}
.parlay-section h3 {{ color: #ffd700; margin-bottom: 4px; }}
.parlay-table {{ width: 100%; border-collapse: collapse; font-size: 0.82em; }}
.parlay-table th {{ background: #2a3a4a; color: #ffd700; padding: 8px 10px; text-align: left; }}
.parlay-table td {{ padding: 8px 10px; border-bottom: 1px solid #2a3a4a; color: #ccddee; }}
.parlay-table td b {{ color: #4ecb71; }}
.parlay-odd {{ font-family: 'Courier New', monospace; font-weight: bold; color: #e74c3c !important; font-size: 1.1em; }}
.parlay-risk {{ font-size: 0.85em; }}
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
  <div class="summary-item"><span class="label">低进球警报</span><span class="value" style="color:{'#e74c3c' if sum(1 for p in predictions if p.get('low_score_prob',0)>0.25) > 0 else '#8899aa'}">{sum(1 for p in predictions if p.get('low_score_prob',0)>0.25)}</span></div>
</div>

<!-- LOW_SCORE_ALERT -->
<!-- LOW_SCORE_ALERT_END -->

{yesterday_html}

<div class="match-grid">
{''.join(cards)}
</div>

{_generate_parlay_html(predictions)}

{_generate_extra_jczq_section(extra_jczq or [])}

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
