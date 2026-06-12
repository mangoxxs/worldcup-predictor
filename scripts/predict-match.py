#!/usr/bin/env python3
"""
多源比分预测引擎 (Multi-Source Score Prediction Engine)

替代中国足球评论员预测的三层信源：
  第一层（40%）：博彩 Correct Score 市场
  第二层（35%）：AI 数据模型
  第三层（25%）：国际分析师共识

用法：
  python3 predict-match.py \
    --home "South Korea" --away "Czech Republic" \
    --stage "Group A, Matchday 1" \
    --date "2026-06-12" \
    --venue "Estadio Akron, Guadalajara" \
    [--betting-file odds.json] \
    [--model-file models.json] \
    [--analyst-file analysts.json]

JSON 输入文件格式见下方示例。
"""

import json
import sys
from dataclasses import dataclass, field
from collections import Counter


# ─── Data Structures ──────────────────────────────────────────────

@dataclass
class ScorePrediction:
    home_score: int
    away_score: int
    score_str: str                          # e.g. "1-1"
    source: str = ""                        # "betting" | "model" | "analyst"
    source_name: str = ""                   # "Bet365" | "Opta" | "BBC"
    weight: float = 1.0                     # source layer weight
    probability: float = 0.0                # implied or stated probability

@dataclass
class MatchContext:
    home_team: str
    away_team: str
    stage: str
    date: str
    venue: str

@dataclass
class CorrectionFactors:
    """五维修正因子得分"""
    A_league_quality: float = 0.0   # 联赛质量
    B_tactical: float = 0.0         # 战术特征
    C_tournament: float = 0.0       # 赛制进程
    D_history: float = 0.0          # 历史交锋
    E_venue: float = 0.0            # 场地因素

    def total(self) -> float:
        return self.A_league_quality + self.B_tactical + self.C_tournament + self.D_history + self.E_venue


# ─── Layer Weights ─────────────────────────────────────────────────

LAYER_WEIGHTS = {
    "betting": 0.40,   # 博彩 Correct Score
    "model":   0.35,   # AI 数据模型
    "analyst": 0.25,   # 国际分析师共识
}

CORRECTION_WEIGHTS = {
    "A": 1.0,
    "B": 1.2,
    "C": 1.5,
    "D": 0.8,
    "E": 0.6,
}


# ─── Step 1: Multi-Source Consensus ────────────────────────────────

def compute_multisource_consensus(predictions: list[ScorePrediction]) -> list[dict]:
    """
    三层信源加权共识：
    - 博彩层：按 Correct Score 隐含概率
    - 模型层：按模型预测概率
    - 分析师层：按频次统计
    """
    if not predictions:
        return []

    # Group by score
    score_map: dict[str, dict] = {}
    for p in predictions:
        key = p.score_str
        if key not in score_map:
            score_map[key] = {
                "home_score": p.home_score,
                "away_score": p.away_score,
                "score_str": key,
                "total_weight": 0.0,
                "sources": {layer: {"weight": 0.0, "names": []} for layer in ["betting", "model", "analyst"]},
            }
        entry = score_map[key]
        layer_weight = LAYER_WEIGHTS.get(p.source, 0.0)
        entry["total_weight"] += p.probability * layer_weight
        entry["sources"][p.source]["weight"] += p.probability * layer_weight
        if p.source_name not in entry["sources"][p.source]["names"]:
            entry["sources"][p.source]["names"].append(p.source_name)

    # Rank by total weight
    ranked = sorted(score_map.values(), key=lambda x: x["total_weight"], reverse=True)
    return ranked


# ─── Step 2 & 3: Correction Factors & Final Score ──────────────────

def apply_correction_factors(
    consensus: list[dict],
    corrections: CorrectionFactors,
    direction: str  # "home" | "draw" | "away"
) -> list[dict]:
    """
    对共识比分应用修正因子，计算最终得分。
    direction: 该分数倾向的方向
    """
    total_correction = corrections.total()

    results = []
    for i, item in enumerate(consensus[:5]):  # top 5 consensus
        base_score = max(5 - i, 1)  # #1=5, #2=4, #3=3, ...
        # 基础分改为 3/2/1 对应排名
        if i == 0: base_score = 3
        elif i == 1: base_score = 2
        else: base_score = 1

        # 根据方向应用修正
        item_direction = "draw" if item["home_score"] == item["away_score"] else \
                         "home" if item["home_score"] > item["away_score"] else "away"

        if direction == item_direction:
            final_score = base_score + total_correction
        elif item_direction == "draw":
            final_score = base_score  # 平局中性
        else:
            final_score = base_score - total_correction  # 反方向

        item["base_score"] = base_score
        item["correction"] = total_correction if direction == item_direction else \
                            (0 if item_direction == "draw" else -total_correction)
        item["final_score"] = round(final_score, 2)
        item["direction"] = item_direction
        results.append(item)

    # Re-rank by final score
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


# ─── Step 4: Output ────────────────────────────────────────────────

def generate_report(
    context: MatchContext,
    consensus: list[dict],
    final: list[dict],
    corrections: CorrectionFactors,
) -> str:
    """生成 Markdown 格式预测报告"""
    lines = []
    lines.append(f"# 🏟️ {context.home_team} vs {context.away_team}")
    lines.append("")
    lines.append(f"| 项目 | 详情 |")
    lines.append(f"|---|---|")
    lines.append(f"| 赛制 | {context.stage} |")
    lines.append(f"| 日期 | {context.date} |")
    lines.append(f"| 场地 | {context.venue} |")
    lines.append("")

    # 共识表
    lines.append("## ▎多源共识比分 TOP3")
    lines.append("")
    lines.append("| 排名 | 比分 | 加权得分 | 信源分布 |")
    lines.append("|---|---|---|---|")
    for i, item in enumerate(consensus[:3]):
        rank = ["🥇", "🥈", "🥉"][i]
        sources = ", ".join(
            f"{k}({v['weight']:.1f})" for k, v in item["sources"].items() if v["weight"] > 0
        )
        lines.append(f"| {rank} | **{item['score_str']}** | {item['total_weight']:.2f} | {sources} |")
    lines.append("")

    # 修正因子
    lines.append("## ▎修正因子")
    lines.append("")
    lines.append(f"| 因子 | 得分 | 权重 | 加权 |")
    lines.append(f"|---|---|---|---|")
    lines.append(f"| A 联赛质量 | {corrections.A_league_quality} | {CORRECTION_WEIGHTS['A']} | {corrections.A_league_quality * CORRECTION_WEIGHTS['A']:.1f} |")
    lines.append(f"| B 战术特征 | {corrections.B_tactical} | {CORRECTION_WEIGHTS['B']} | {corrections.B_tactical * CORRECTION_WEIGHTS['B']:.1f} |")
    lines.append(f"| C 赛制进程 | {corrections.C_tournament} | {CORRECTION_WEIGHTS['C']} | {corrections.C_tournament * CORRECTION_WEIGHTS['C']:.1f} |")
    lines.append(f"| D 历史交锋 | {corrections.D_history} | {CORRECTION_WEIGHTS['D']} | {corrections.D_history * CORRECTION_WEIGHTS['D']:.1f} |")
    lines.append(f"| E 场地因素 | {corrections.E_venue} | {CORRECTION_WEIGHTS['E']} | {corrections.E_venue * CORRECTION_WEIGHTS['E']:.1f} |")
    lines.append(f"| **修正总分** | | | **{corrections.total():.1f}** |")
    lines.append("")

    # 最终预测
    lines.append("## ▎最终预测")
    lines.append("")
    lines.append("| 排名 | 比分 | 基础分 | 修正 | 最终得分 | 置信度 |")
    lines.append("|---|---|---|---|---|---|")
    for i, item in enumerate(final[:3]):
        rank = ["🥇", "🥈", "🥉"][i]
        conf = "高" if item["final_score"] >= 5.0 else "中" if item["final_score"] >= 2.5 else "低"
        lines.append(
            f"| {rank} | **{item['score_str']}** | {item['base_score']} | "
            f"{item['correction']:+.1f} | **{item['final_score']:.1f}** | {conf} |"
        )
    lines.append("")

    # 最终推荐
    lines.append("## ▎推荐")
    for i, item in enumerate(final[:3]):
        rank = ["第一", "第二", "第三"][i]
        conf = "高" if item["final_score"] >= 5.0 else "中" if item["final_score"] >= 2.5 else "低"
        lines.append(f"- 🥇 **{rank}推荐：{item['score_str']}** (得分 {item['final_score']:.1f}，置信度：{conf})")

    return "\n".join(lines)


# ─── Main ──────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="多源比分预测引擎")
    parser.add_argument("--home", required=True, help="主队名")
    parser.add_argument("--away", required=True, help="客队名")
    parser.add_argument("--stage", default="", help="赛制（如 Group A, Matchday 1）")
    parser.add_argument("--date", default="", help="日期")
    parser.add_argument("--venue", default="", help="场地")
    parser.add_argument("--betting-file", help="博彩数据 JSON 文件")
    parser.add_argument("--model-file", help="AI模型数据 JSON 文件")
    parser.add_argument("--analyst-file", help="分析师数据 JSON 文件")
    parser.add_argument("--corrections", default="0,0,0,0,0", help="修正因子：A,B,C,D,E（逗号分隔）")
    parser.add_argument("--direction", default="draw", choices=["home", "draw", "away"],
                       help="修正方向")
    parser.add_argument("--output", default="-", help="输出文件 (- 为 stdout)")
    args = parser.parse_args()

    context = MatchContext(
        home_team=args.home,
        away_team=args.away,
        stage=args.stage,
        date=args.date,
        venue=args.venue,
    )

    # Load predictions from JSON files
    predictions: list[ScorePrediction] = []

    for file_path, source in [
        (args.betting_file, "betting"),
        (args.model_file, "model"),
        (args.analyst_file, "analyst"),
    ]:
        if not file_path:
            continue
        try:
            with open(file_path) as f:
                data = json.load(f)
            for item in data:
                predictions.append(ScorePrediction(
                    home_score=item["home_score"],
                    away_score=item["away_score"],
                    score_str=item.get("score", f"{item['home_score']}-{item['away_score']}"),
                    source=source,
                    source_name=item.get("source", source),
                    probability=item.get("probability", 0.0),
                ))
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"⚠️  Failed to load {file_path}: {e}", file=sys.stderr)

    if not predictions:
        print("❌ No prediction data loaded. Provide at least one source file.", file=sys.stderr)
        sys.exit(1)

    # Step 1: Multi-source consensus
    consensus = compute_multisource_consensus(predictions)
    if not consensus:
        print("❌ Could not compute consensus.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Correction factors
    corr_vals = [float(x) for x in args.corrections.split(",")]
    corrections = CorrectionFactors(
        A_league_quality=corr_vals[0],
        B_tactical=corr_vals[1],
        C_tournament=corr_vals[2],
        D_history=corr_vals[3],
        E_venue=corr_vals[4],
    )

    # Step 3: Final scores
    final = apply_correction_factors(consensus, corrections, args.direction)

    # Step 4: Report
    report = generate_report(context, consensus, final, corrections)

    if args.output == "-":
        print(report)
    else:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"✅ Report saved to {args.output}", file=sys.stderr)

    # Also print JSON summary
    json_summary = {
        "context": {k: v for k, v in context.__dict__.items()},
        "consensus": consensus[:3],
        "final": final[:3],
    }
    json_path = args.output.replace(".md", ".json") if args.output != "-" else "/dev/stdout"
    if args.output != "-":
        with open(json_path, "w") as f:
            json.dump(json_summary, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON saved to {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
