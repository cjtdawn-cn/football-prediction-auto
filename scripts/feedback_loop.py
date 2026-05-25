#!/usr/bin/env python3
"""
自学习反馈闭环 — 结果获取 → 进化引擎学习 → 权重更新 → 知识库优化
"""
import sys, os, json
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE = Path(__file__).parent.parent
RESULTS_DIR = BASE / "models" / "results"  # 与 EvolutionEngine 统一路径
KB_PATH = BASE / "data" / "knowledge_base.json"
MODEL_DIR = BASE / "models"

# 添加 skill package
SKILL_PATH = Path(__file__).parent.parent.parent / "football-prediction-skill"
if SKILL_PATH.exists():
    sys.path.insert(0, str(SKILL_PATH))

try:
    from football_predictor.evolution import EvolutionEngine
    EVO_AVAILABLE = True
except ImportError:
    print("Warning: EvolutionEngine not available, running in standalone mode.")
    EVO_AVAILABLE = False

from result_fetcher import fetch_result, find_missing_results


def run_feedback_loop():
    """完整反馈闭环"""
    now = datetime.now(timezone(timedelta(hours=8)))
    print("=" * 60)
    print(f"  自学习反馈闭环 — {now.strftime('%Y-%m-%d %H:%M')} CST")
    print("=" * 60)

    # Step 1: 扫描并补全缺失的比赛结果
    print("\n[1/4] 获取比赛结果...")
    updated = find_missing_results(days_back=7)
    print(f"  补全结果: {updated} 场")

    # Step 2: 通过进化引擎录入结果 (触发在线学习)
    print("\n[2/4] 进化引擎录入结果 + 在线学习...")
    total = total_new = correct = 0

    if EVO_AVAILABLE:
        try:
            evo = EvolutionEngine(base_path=BASE, model_dir=MODEL_DIR)

            for f in sorted(RESULTS_DIR.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding='utf-8'))
                except (json.JSONDecodeError, FileNotFoundError):
                    continue

                for match_id, rec in data.items():
                    actual = rec.get('actual')
                    if actual is None:
                        continue
                    # 已有分析结果则跳过 (已经录入过)
                    if rec.get('analysis') and rec['analysis'].get('component_gradients'):
                        total += 1
                        if rec['analysis'].get('prediction_correct'):
                            correct += 1
                        continue

                    # 通过进化引擎录入结果
                    try:
                        result = evo.record_result(
                            match_id,
                            actual['ft_result'],
                            actual['ft_home_goals'],
                            actual['ft_away_goals'],
                            match_date=rec.get('match_date', f.stem),
                            source=actual.get('source', 'auto')
                        )
                        if result and 'error' not in result:
                            total_new += 1
                            total += 1
                            if result.get('analysis', {}).get('prediction_correct'):
                                correct += 1
                            print(f"  录入: {match_id} → {actual['ft_home_goals']}:{actual['ft_away_goals']} "
                                  f"({'✓' if result['analysis']['prediction_correct'] else '✗'}) "
                                  f"Brier:{result['analysis']['brier_score']:.4f}")
                    except Exception as e:
                        print(f"  录入失败 {match_id}: {e}")

            if total_new > 0:
                # 批量优化 (需要足够数据)
                opt_result = evo.run_batch_optimization(days_back=30)

            # 保存当前进化状态
            evo._save_kb()
            print(f"  新录入: {total_new} 场 | 累计: {total} 场 | 准确率: {correct/total:.1%}" if total > 0 else "  暂无数据")

        except Exception as e:
            print(f"  进化引擎错误: {e}")
            import traceback; traceback.print_exc()

    # Step 3: 进化引擎批量优化
    print("\n[3/4] 批量权重优化...")
    if EVO_AVAILABLE and total > 0:
        try:
            evo = EvolutionEngine(base_path=BASE, model_dir=MODEL_DIR)
            result = evo.run_batch_optimization(days_back=30)
            if result and result.get('optimized'):
                new_w = result.get('weights', {})
                print(f"  融合权重已优化 (使用{result.get('matches_used', 0)}场比赛):")
                for k in sorted(new_w.keys()):
                    print(f"    {k}: {new_w[k]:.4f}")
                # 概率校准
                cal = evo.compute_calibration()
                if cal:
                    print(f"  概率校准: {len(cal)} bins")
                # 特征评分
                evo._update_feature_scores()
                print(f"  特征评分已更新")
            else:
                print(f"  跳过优化: {result.get('reason', '数据不足')}")

            # 平局阈值优化
            evo._optimize_draw_thresholds()
            print(f"  平局检测阈值已优化")

            # 数据修剪
            prune_result = evo.prune_old_results(retention_days=365)
            print(f"  数据修剪完成")

        except Exception as e:
            print(f"  批量优化错误 (非致命): {e}")
    else:
        print("  跳过 (需更多结果数据)")

    # Step 4: 更新知识库
    print("\n[4/4] 更新知识库...")
    update_knowledge_base()
    print(f"\n  反馈闭环完成。")

    # 返回摘要供 workflow 使用
    return {
        'results_fetched': updated,
        'total_matches': total,
        'accuracy': correct / total if total > 0 else 0,
        'weights_updated': EVO_AVAILABLE and total > 0,
    }


def update_knowledge_base():
    """更新知识库统计"""
    kb = {}
    if KB_PATH.exists():
        try:
            kb = json.loads(KB_PATH.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    now = datetime.now(timezone(timedelta(hours=8)))
    total = correct = 0
    brier_total = 0.0

    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        for mid, rec in data.items():
            a = rec.get('analysis')
            if a:
                total += 1
                if a.get('prediction_correct'):
                    correct += 1
                brier_total += a.get('brier_score', 0)

    kb['total_matches_recorded'] = total
    kb['total_matches_correct'] = correct
    kb['last_updated'] = now.isoformat()

    # 滚动窗口表现
    for window_key, days in [('last_7_days', 7), ('last_30_days', 30),
                               ('last_90_days', 90), ('all_time', 9999)]:
        cutoff = (now - timedelta(days=days)).strftime('%Y-%m-%d') if days < 9999 else '2000-01-01'
        w_total = w_correct = 0
        w_brier = 0.0
        for f in sorted(RESULTS_DIR.glob("*.json")):
            if f.stem < cutoff:
                continue
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, FileNotFoundError):
                continue
            for mid, rec in data.items():
                a = rec.get('analysis')
                if a:
                    w_total += 1
                    if a.get('prediction_correct'):
                        w_correct += 1
                    w_brier += a.get('brier_score', 0)

        wp = kb.setdefault('rolling_performance', {}).setdefault(window_key, {})
        wp['total'] = w_total
        wp['correct'] = w_correct
        wp['accuracy'] = w_correct / w_total if w_total > 0 else 0
        wp['avg_brier'] = w_brier / w_total if w_total > 0 else 0

    # 写回
    tmp = str(KB_PATH) + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)
    Path(tmp).replace(KB_PATH)

    acc = correct / total if total > 0 else 0
    print(f"  知识库: {total} 场 | 准确率: {acc:.1%}")


if __name__ == '__main__':
    run_feedback_loop()
