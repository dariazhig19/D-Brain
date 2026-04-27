# Scoring Logic: Layout Generative Design

This document defines the evaluation criteria for the generated layout variants. Each criterion will be mapped to a Python formula for automated scoring.

## 1. Density (Efficiency of Land Use)
- **Goal**: Maximize the ratio of built area to total site area while respecting regulations.
- **Python Formula**:
```python
# [Insert Density Calculation Logic Here]
```

## 2. Connectivity (Accessibility)
- **Goal**: Minimize average path lengths between buildings and key infrastructure points.
- **Python Formula**:
```python
# [Insert Connectivity Calculation Logic Here]
```

## 3. Aesthetics (Visual Quality)
- **Goal**: Quantify spatial diversity, sightlines, and shadow patterns.
- **Python Formula**:
```python
# [Insert Aesthetics Metrics Logic Here]
```

## 4. Cost-efficiency
- **Goal**: Evaluate the cost-to-benefit ratio based on infrastructure length and building complexity.
- **Python Formula**:
```python
# [Insert Cost-efficiency Estimation Logic Here]
```

## Total Score calculation
- **Formula**: `Final Score = (w1 * Density) + (w2 * Connectivity) + (w3 * Aesthetics) + (w4 * Cost)`
