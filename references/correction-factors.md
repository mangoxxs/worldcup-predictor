# Five-Dimensional Correction Factors

Apply these factors to consensus scores before final ranking. Each factor is scored per-team-direction (-2 to +2), then multiplied by its weight.

## A. League Quality (weight: 1.0)

| Condition | Score |
|---|---|
| Team has ≥3 Premier League starters | +1 that direction |
| Team has ≥3 Champions League quarterfinal team starters | +1 that direction |
| Team's squad primarily from non-top-5 leagues, no CL experience | -1 that direction |

## B. Tactical Features (weight: 1.2)

| Condition | Score |
|---|---|
| Team has target forward ≥185cm who is a core attacking threat | +1 that direction |
| Team plays effective counter-attack, verified in recent matches | +1 that direction |
| Team missing key starter due to injury/suspension | -1 that direction |

## C. Tournament Stage (weight: 1.5)

**Matchday 1**: Weight = 0 (insufficient information)

**Matchday 2**:
- Round 1 winner needing points to secure advancement: +1
- Round 1 loser in must-win situation: +1 or -1 (judge by opponent strength)

**Matchday 3**:
- Already-qualified team rotating squad: -1
- Team must win to advance: +1 (motivation boost)
- Both teams can advance with draw (collusion risk): -1 to goal count

**Knockout Stage** (C weight → 2.0, D weight → 1.2):
- Team showing improving form across 3 group matches: +1
- Team regressing across group stage: -1
- Team with knockout experience: +1
- Extra time/penalties more likely: -1 big score, +1 small score

## D. Head-to-Head History (weight: 0.8)

| Condition | Score |
|---|---|
| Team dominant in last 5 meetings | +1 that direction |
| Continental matchup with historical win-rate bias | ±1 |

## E. Venue / Neutral Site (weight: 0.6)

| Condition | Score |
|---|---|
| Team better adapted to geography/climate/timezone (even at neutral site) | +1 |
| Significant home fan support advantage | +1 |

## Computing Final Correction

```
Total = A × 1.0 + B × 1.2 + C × 1.5 + D × 0.8 + E × 0.6
```

For knockout stage:
```
Total = A × 1.0 + B × 1.2 + C × 2.0 + D × 1.2 + E × 0.6
```

Pass the raw A,B,C,D,E scores to `predict-match.py --corrections "A,B,C,D,E"`. The script applies weights internally.
