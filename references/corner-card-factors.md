# Corner & Card Prediction Factors

Supplementary prediction dimensions. Apply these AFTER the main score prediction. Each dimension has its own factor set, independent from score correction factors.

## Corners (角球数)

### Three-Layer Approach (same weights as score prediction)

**Layer 1: Betting Market (40%)**
Search for "Corners Over/Under" or "Total Corners" lines. Common threshold: Over/Under 9.5 corners.

**Layer 2: Statistical Model (35%)**
Compute expected corners from team data:
- Average corners per game (last 10 matches)
- Corners per game for/against the opponent
- Possession % → corners correlation (~0.6 per 10% possession)

**Layer 3: Analyst Consensus (25%)**
Collect corner predictions from match previews.

### Corner Correction Factors

| Factor | Weight | Description |
|---|---|---|
| F1. Wing Play | 1.0 | Team with ≥2 wide attackers/wing-backs averaging 2+ crosses/game: +1 corner that direction |
| F2. Possession Gap | 1.2 | Team expected to dominate possession (≥55%): +1 corner that direction. Defensive underdog: +1 corner for opponent |
| F3. Match Tempo | 0.8 | High-intensity pressing teams: +1 total corners. Slow buildup: -1 total corners |
| F4. Set-Piece Reliance | 1.0 | Team scoring ≥25% goals from set pieces: +1 corner that direction |

### Output Format
```
预测角球总数: 9-11个
方向分布: 韩国 5-6 vs 捷克 4-5
Over 9.5 置信度: 中
```

## Cards (得牌数)

### Three-Layer Approach

**Layer 1: Betting Market (40%)**
Search for "Total Cards" or "Booking Points" lines. Common: Over/Under 3.5 cards or 35 booking points.

**Layer 2: Statistical Model (35%)**
- Team average cards per game (last 10 matches)
- Opponent fouls drawn per game
- Referee average cards per game (CRITICAL — referee variance is the single biggest factor)

**Layer 3: Analyst Consensus (25%)**
Match preview mentions of "physical battle", "disciplinary records", referee assignments.

### Card Correction Factors

| Factor | Weight | Description |
|---|---|---|
| G1. Defensive Aggression | 1.2 | Team averaging ≥2.5 cards/game: +1 card that direction |
| G2. Referee Strictness | 1.5 | Referee above-average card rate (>4.0/game): +1 total. Below-average (<2.5/game): -1 total |
| G3. Match Importance | 1.0 | Knockout or must-win match: +1 total cards. Dead rubber: -1 total |
| G4. Rivalry/Derby | 0.8 | Historical rivalry or physical matchup: +1 total cards |
| G5. Key Players at Risk | 0.6 | Player on yellow-card accumulation warning (knockout): +0.5 that team |

### Card Count Scale
Use booking points system (yellow = 10pts, red = 25pts) for betting compatibility.

### Output Format
```
预测得牌数: 3-5张黄牌，红牌概率低
Booking Points: 30-50
方向分布: 韩国 2-3 vs 捷克 1-2
Over 3.5 Cards 置信度: 中
关键变量: 主裁判场均出牌率
```

## Referee Database

When predicting cards, ALWAYS search for the assigned referee:
- Name and nationality
- Average cards per game in last season/tournament
- Recent World Cup or major tournament history
- Tendency: strict disciplinarian vs. "let them play" style

This is the single highest-impact variable for card predictions.
