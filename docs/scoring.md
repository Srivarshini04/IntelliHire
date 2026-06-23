# DELULU Scoring Formulas

## Capability Engine

```
Capability = 0.30 × Technical
           + 0.30 × Execution
           + 0.20 × Ownership
           + 0.20 × Learning Velocity
```

| Dimension | Inputs |
|-----------|--------|
| Technical | Projects, skills, GitHub activity |
| Execution | Deployments, products, production systems |
| Ownership | Repo creator, lead contributor, founder projects |
| Learning | Technology timeline, skill progression |

## Risk Engine

| Risk Type | Signals |
|-----------|---------|
| Evidence Risk | Missing sources, low evidence, weak validation |
| Role Gap Risk | Missing required skills |
| Credibility Risk | Claims ≠ evidence |

Output: `risk_score` (0–100, lower is better)

## Hidden Talent Index (HTI)

```
HTI = Capability − Visibility (normalized 0–100)
```

| Visibility Signals | Weight |
|--------------------|--------|
| College prestige | High |
| Brand companies | High |
| Awards / recognition | Medium |
| Public profile | Medium |

**Hero metric:** High capability + low visibility = hidden talent

## Confidence Engine

Based on:
- Evidence quality
- Evidence quantity
- Cross-source agreement

## Fit Score (Ranking)

```
Fit Score = 0.55 × Capability
          + 0.25 × HTI
          + 0.20 × Confidence
          − 0.15 × Risk
```

## Relevance Filter

- Score each evidence artifact 0–100 against role blueprint
- **Keep only relevance > 60**
- Example (AI Engineer role): Keep ClinicBot, Forge, WattWise — discard HTML Lab, Calculator App

## ATS Baseline (for comparison)

```
ATS Score = keyword_match + years_experience + college_score
```

Use this dumb baseline to demonstrate DELULU's hidden talent recall advantage.
