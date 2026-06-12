---
name: worldcup-predictor
description: >
  Multi-source football match score prediction engine for World Cup and other international tournaments. Predicts match score, total corners, and cards (yellow/red). Replaces Chinese pundit consensus with three-layer weighted sources: betting Correct Score market (40%), AI statistical models like Opta (35%), and international analyst consensus (25%). Applies five-dimensional correction factors (league quality, tactics, tournament stage, history, venue) for scores, plus independent factor sets for corners and cards. Use when predicting match scores, analyzing football fixtures, forecasting World Cup results, doing pre-match analysis, or when the user mentions 比分预测, 世界杯预测, 足球预测, 角球预测, 得牌预测, match prediction, score forecast, corner prediction, card prediction.
---

# World Cup Multi-Source Predictor

Predict football match scores, corners, and cards using a three-layer weighted consensus model with five-dimensional correction factors. This replaces unreliable single-source predictions with a robust multi-signal approach.

## What This Skill Predicts

| Dimension | Method | Key Factors |
|---|---|---|
| **比分 (Score)** | 3-layer consensus + A-E correction factors | League quality, tactics, stage, H2H, venue |
| **角球数 (Corners)** | 3-layer consensus + F1-F4 corner factors | Wing play, possession, tempo, set-piece reliance |
| **得牌数 (Cards)** | 3-layer consensus + G1-G5 card factors | Defensive aggression, referee strictness, match importance, rivalry |

## Quick Start

1. Collect data from three layers (see below)
2. Run the engine: `python3 scripts/predict-match.py`
3. Output: formatted Markdown report + structured JSON

## Workflow

### Step 1: Collect Three-Layer Source Data

Launch parallel research for all three layers simultaneously — they're independent.

**Layer 1: Betting Market (40% weight)**
- Search for Correct Score odds from Bet365, Pinnacle, William Hill
- Use odds comparison sites: oddsportal.com, flashscore.com, sofascore.com
- Extract: specific scores + decimal odds → compute implied probability (1/odds)
- Also collect 1X2 and Over/Under 2.5 market data for context
- Save as JSON array to `betting.json`

**Layer 2: AI Models (35% weight)**
- Search for Opta Supercomputer / The Analyst match predictions
- FiveThirtyEight is discontinued; prefer Opta
- Extract: win/draw/lose probabilities (%)
- Convert to score-level probabilities by distributing win% across likely win scores
- Save as JSON array to `models.json`

**Layer 3: International Analysts (25% weight)**
- Search BBC Sport, Sky Sports, ESPN FC, The Guardian, Goal.com match previews
- Collect explicit score predictions from named analysts or publication previews
- Build frequency table: each distinct score gets probability = count/total
- Save as JSON array to `analysts.json`

JSON format for each layer:
```json
[
  {"home_score": 1, "away_score": 1, "score": "1-1", "source": "Bet365", "probability": 0.154},
  {"home_score": 1, "away_score": 0, "score": "1-0", "source": "Opta", "probability": 0.215}
]
```

### Step 2: Determine Correction Factors

Read [`references/correction-factors.md`](references/correction-factors.md) for the full five-dimension framework. Compute the correction score vector:

```
A (League Quality, wt=1.0): +1 per team if ≥3 PL/CL starters
B (Tactical, wt=1.2): +1 for tall target man, defensive injuries = -1
C (Tournament Stage, wt=1.5): matchday 1 = 0, knockout = dynamic
D (History, wt=0.8): last 5 H2H advantage
E (Venue, wt=0.6): home/altitude/fan advantage
```

Sum the weighted corrections. Pass as `--corrections "A,B,C,D,E"` (raw scores, script applies weights internally).

### Step 3: Run the Engine

```bash
python3 scripts/predict-match.py \
  --home "South Korea" --away "Czech Republic" \
  --stage "Group A, Matchday 1" \
  --date "2026-06-12" \
  --venue "Estadio Akron, Guadalajara" \
  --betting-file betting.json \
  --model-file models.json \
  --analyst-file analysts.json \
  --corrections "1.0,0,0,0,0" \
  --direction home \
  --output report.md
```

- `--direction`: which side the corrections favor — "home", "draw", or "away"
- `--output`: Markdown report path (also generates `{name}.json` alongside)

### Step 4: Deliver Results

Present the report to the user. If a Feishu document exists from a previous prediction, update it with `lark-cli docs +update`.

For Feishu delivery:
- Use `block_insert_after` to add a new section
- Include the three-layer source breakdown table and final prediction table
- Add a comparison callout if this is a refresh vs. previous prediction

### Step 5: Predict Corners & Cards (Supplementary)

After delivering the score prediction, offer to predict corners and cards. These use the same three-layer architecture but with their own factor sets.

#### Corner Prediction Workflow

1. **Collect corner data**: Search for team corner stats (last 10 matches), corners Over/Under lines, wing-play tactics
2. **Apply corner factors**: Read [`references/corner-card-factors.md`](references/corner-card-factors.md) section "Corners"
   - F1 Wing Play (1.0): teams with ≥2 wide attackers → +1 corner
   - F2 Possession Gap (1.2): dominant team → +1, underdog → opponent +1
   - F3 Match Tempo (0.8): high press → +1 total, slow buildup → -1 total
   - F4 Set-Piece Reliance (1.0): ≥25% goals from set pieces → +1
3. **Output**: Total corners range + home/away split + Over/Under confidence

#### Card Prediction Workflow

1. **CRITICAL — find the referee first**: Referee card rate is the single biggest variable. Search for:
   - Referee name, nationality, average cards/game
   - Recent tournament history and disciplinary style
2. **Collect team card stats**: Average cards per game (last 10), fouls committed/drawn
3. **Apply card factors**: Read [`references/corner-card-factors.md`](references/corner-card-factors.md) section "Cards"
   - G1 Defensive Aggression (1.2): ≥2.5 cards/game → +1
   - G2 Referee Strictness (1.5): above/below average → ±1 total
   - G3 Match Importance (1.0): knockout/must-win → +1 total
   - G4 Rivalry (0.8): physical matchup or derby → +1 total
   - G5 Key Player Risk (0.6): yellow accumulation risk → +0.5
4. **Output**: Cards count range + booking points + home/away split + referee note

## Key Principles

- **Parallel collection**: always spawn concurrent research sub-agents — 3 for score layers, can add 2 more for corner/card data
- **Real data preferred**: when betting odds are available near kickoff, use them over model estimates
- **Layer independence**: each layer works standalone — if one fails, engine still runs with remaining layers
- **Direction matters**: correction factors apply per-direction; draws are direction-neutral
- **Referee first for cards**: never predict cards without finding the referee assignment — it's the single highest-impact variable

## Edge Cases

- **No pundit data**: common for Chinese pundits (broadcasting contracts). Rely on betting + models.
- **Pre-matchday 1**: Correct Score odds may be model estimates, not live. Flag this.
- **Single model**: if only Opta is available (no FiveThirtyEight), use it alone at full 35% weight.
- **Tied scores**: when multiple scores have equal final scores, rank all as tied — don't force a tiebreak.
- **No referee announced**: if referee not yet assigned, flag card prediction as "preliminary — pending referee confirmation" and use league-average card rate as placeholder.
