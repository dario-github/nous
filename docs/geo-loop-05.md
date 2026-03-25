# Geo Loop 5 — 2026-03-16 18:50 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.4307 | 0.5979 |
| R_event | 0.6957 | 0.3000 |
| R_causal | 0.6733 | 0.6733 |
| R_timing | 0.5811 | 0.8000 |
| R_calibration | 0.7588 | 0.5188 |
| R_hallucination | 0.4667 | 0.8000 |
| Matches | 8/8 | 3/5 |

## 策略
- LLM synthesis: False
- LLM judge: False
- Model: N/A
- Max predictions: 15
- Confidence threshold: 0.5

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 456.7s

## 策略变更
- max_predictions: 15 → 13
- confidence_threshold: 0.5 → 0.55

## 建议
- 过拟合: train R=0.569 vs val R=0.402
- 幻觉率 80%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
