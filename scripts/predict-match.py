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


# ─── Step 5: Corner Prediction ────────────────────────────────────

@dataclass
class CornerPrediction:
    total_low: int
    total_high: int
    home_corners: float
    away_corners: float
    over_confidence: str  # 高/中/低
    factors: dict = field(default_factory=dict)

CORNER_FACTORS = {
    "F1": {"name": "边路进攻", "weight": 1.0},
    "F2": {"name": "控球差距", "weight": 1.2},
    "F3": {"name": "比赛节奏", "weight": 0.8},
    "F4": {"name": "定位球依赖", "weight": 1.0},
}


def predict_corners(team_stats: dict, corner_factors: dict) -> CornerPrediction:
    """
    Predict corner count based on team stats and corner factors.

    team_stats: {
        "home": {"avg_corners": 5.2, "possession": 52, "crosses": 18, "set_piece_goals_pct": 22},
        "away": {"avg_corners": 4.1, "possession": 48, "crosses": 12, "set_piece_goals_pct": 15},
    }
    corner_factors: {"F1_home": +1, "F2_home": 0, ...}
    """
    base_total = team_stats.get("home", {}).get("avg_corners", 5.0) + team_stats.get("away", {}).get("avg_corners", 4.5)

    # Apply weighted corrections
    correction = 0.0
    for key, val in corner_factors.items():
        factor_id = key.split("_")[0]
        if factor_id in CORNER_FACTORS:
            correction += val * CORNER_FACTORS[factor_id]["weight"]

    adjusted = base_total + correction
    total_low = max(4, int(adjusted - 1.5))
    total_high = int(adjusted + 1.5)

    # Home/away split based on possession ratio
    home_poss = team_stats.get("home", {}).get("possession", 50)
    away_poss = team_stats.get("away", {}).get("possession", 50)
    ratio = home_poss / (home_poss + away_poss) if (home_poss + away_poss) > 0 else 0.5

    home_corners = round(adjusted * ratio, 1)
    away_corners = round(adjusted * (1 - ratio), 1)

    conf = "高" if abs(correction) <= 1.0 else "中" if abs(correction) <= 2.5 else "低"

    return CornerPrediction(
        total_low=total_low,
        total_high=total_high,
        home_corners=home_corners,
        away_corners=away_corners,
        over_confidence=conf,
        factors=corner_factors,
    )


# ─── Step 6: Card Prediction ───────────────────────────────────────

@dataclass
class CardPrediction:
    total_low: int
    total_high: int
    home_cards: float
    away_cards: float
    booking_points_low: int
    booking_points_high: int
    red_card_risk: str  # 高/中/低
    over_confidence: str
    referee_note: str = ""
    factors: dict = field(default_factory=dict)

CARD_FACTORS = {
    "G1": {"name": "防守侵略性", "weight": 1.2},
    "G2": {"name": "裁判严格度", "weight": 1.5},
    "G3": {"name": "比赛重要性", "weight": 1.0},
    "G4": {"name": "对抗/德比", "weight": 0.8},
    "G5": {"name": "关键球员风险", "weight": 0.6},
}


def predict_cards(team_stats: dict, card_factors: dict, referee: dict) -> CardPrediction:
    """
    Predict card count and booking points.

    team_stats: {
        "home": {"avg_cards": 2.1, "avg_fouls": 14},
        "away": {"avg_cards": 1.8, "avg_fouls": 12},
    }
    card_factors: {"G1_home": +1, "G2_total": +1, ...}
    referee: {"name": "John Smith", "avg_cards": 4.2, "nationality": "ENG"}
    """
    base_home = team_stats.get("home", {}).get("avg_cards", 2.0)
    base_away = team_stats.get("away", {}).get("avg_cards", 1.8)
    base_total = base_home + base_away

    # Apply weighted corrections
    correction_home = 0.0
    correction_away = 0.0
    correction_total = 0.0

    for key, val in card_factors.items():
        parts = key.split("_")
        factor_id = parts[0]
        direction = parts[1] if len(parts) > 1 else "total"
        if factor_id in CARD_FACTORS:
            w = CARD_FACTORS[factor_id]["weight"]
            if direction == "home":
                correction_home += val * w
            elif direction == "away":
                correction_away += val * w
            else:
                correction_total += val * w

    # Referee adjustment: normalize team averages toward referee average
    ref_avg = referee.get("avg_cards", 3.5)
    league_avg = 3.5  # typical league average
    ref_bias = (ref_avg - league_avg) * CARD_FACTORS["G2"]["weight"]

    adjusted_home = base_home + correction_home + ref_bias * 0.5
    adjusted_away = base_away + correction_away + ref_bias * 0.5
    adjusted_total = adjusted_home + adjusted_away + correction_total

    total_low = max(1, int(adjusted_total - 1))
    total_high = int(adjusted_total + 1)

    # Booking points (yellow=10, red=25)
    booking_low = max(10, total_low * 10)
    booking_high = total_high * 10 + 15  # potential red card bump

    red_risk = "高" if adjusted_total > 5.0 else "中" if adjusted_total > 3.5 else "低"
    conf = "高" if abs(correction_total + ref_bias) <= 1.0 else "中" if abs(correction_total + ref_bias) <= 2.5 else "低"

    return CardPrediction(
        total_low=total_low,
        total_high=total_high,
        home_cards=round(adjusted_home, 1),
        away_cards=round(adjusted_away, 1),
        booking_points_low=booking_low,
        booking_points_high=booking_high,
        red_card_risk=red_risk,
        over_confidence=conf,
        referee_note=f"主裁 {referee.get('name', 'Unknown')} ({referee.get('nationality', '')})，场均 {ref_avg} 张牌",
        factors=card_factors,
    )


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
    # Corner & Card options
    parser.add_argument("--corners", action="store_true", help="预测角球数")
    parser.add_argument("--corner-stats", help="角球统计数据 JSON")
    parser.add_argument("--corner-factors", default="0,0,0,0", help="角球修正因子 F1,F2,F3,F4")
    parser.add_argument("--cards", action="store_true", help="预测得牌数")
    parser.add_argument("--card-stats", help="得牌统计数据 JSON")
    parser.add_argument("--card-factors", default="0,0,0,0,0", help="得牌修正因子 G1,G2,G3,G4,G5")
    parser.add_argument("--referee", help="裁判数据 JSON: {name, nationality, avg_cards}")
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

    # Initialize JSON summary
    json_summary = {
        "context": {k: v for k, v in context.__dict__.items()},
        "consensus": consensus[:3],
        "final": final[:3],
    }

    # Generate corner prediction
    if args.corners and args.corner_stats:
        with open(args.corner_stats) as f:
            corner_stats = json.load(f)
        cf_vals = [float(x) for x in args.corner_factors.split(",")]
        corner_factors = {
            f"F1_home": cf_vals[0] if len(cf_vals) > 0 else 0,
            f"F2_home": cf_vals[1] if len(cf_vals) > 1 else 0,
            f"F3_total": cf_vals[2] if len(cf_vals) > 2 else 0,
            f"F4_home": cf_vals[3] if len(cf_vals) > 3 else 0,
        }
        cp = predict_corners(corner_stats, corner_factors)
        corner_report = f"""
## ▎角球预测

| 指标 | 预测 |
|---|---|
| 预估总角球 | {cp.total_low}-{cp.total_high} 个 |
| {context.home_team} 角球 | ~{cp.home_corners} 个 |
| {context.away_team} 角球 | ~{cp.away_corners} 个 |
| 置信度 | {cp.over_confidence} |
"""
        report += corner_report
        json_summary["corners"] = {
            "total_low": cp.total_low, "total_high": cp.total_high,
            "home": cp.home_corners, "away": cp.away_corners,
            "confidence": cp.over_confidence,
        }

    # Generate card prediction
    if args.cards and args.card_stats and args.referee:
        with open(args.card_stats) as f:
            card_stats = json.load(f)
        with open(args.referee) as f:
            referee = json.load(f)
        gf_vals = [float(x) for x in args.card_factors.split(",")]
        card_factors = {}
        factor_names = ["G1_home", "G2_total", "G3_total", "G4_total", "G5_home"]
        for i, name in enumerate(factor_names):
            if i < len(gf_vals) and gf_vals[i] != 0:
                card_factors[name] = gf_vals[i]
        cp_cards = predict_cards(card_stats, card_factors, referee)
        card_report = f"""
## ▎得牌预测

| 指标 | 预测 |
|---|---|
| 预估总牌数 | {cp_cards.total_low}-{cp_cards.total_high} 张 |
| Booking Points | {cp_cards.booking_points_low}-{cp_cards.booking_points_high} |
| {context.home_team} 得牌 | ~{cp_cards.home_cards} 张 |
| {context.away_team} 得牌 | ~{cp_cards.away_cards} 张 |
| 红牌风险 | {cp_cards.red_card_risk} |
| 置信度 | {cp_cards.over_confidence} |
| 裁判 | {cp_cards.referee_note} |
"""
        report += card_report
        json_summary["cards"] = {
            "total_low": cp_cards.total_low, "total_high": cp_cards.total_high,
            "home": cp_cards.home_cards, "away": cp_cards.away_cards,
            "booking_points": f"{cp_cards.booking_points_low}-{cp_cards.booking_points_high}",
            "red_card_risk": cp_cards.red_card_risk,
            "referee": cp_cards.referee_note,
            "confidence": cp_cards.over_confidence,
        }

    # Write output AFTER all sections are appended
    if args.output == "-":
        print(report)
    else:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"✅ Report saved to {args.output}", file=sys.stderr)

    json_path = args.output.replace(".md", ".json") if args.output != "-" else "/dev/stdout"
    if args.output != "-":
        with open(json_path, "w") as f:
            json.dump(json_summary, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON saved to {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
