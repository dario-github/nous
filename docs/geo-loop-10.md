# Geo Loop 10 — 2026-03-16 19:12 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.3807 | 0.5444 |
| R_event | 0.8000 | 0.4706 |
| R_causal | 0.6667 | 0.6667 |
| R_timing | 0.5561 | 0.6684 |
| R_calibration | 0.8125 | 0.5708 |
| R_hallucination | 0.3333 | 0.6667 |
| Matches | 8/8 | 4/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: DeepSeek-V3.2
- Max predictions: 11
- Confidence threshold: 0.75

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 36.7s

## 策略变更
- max_predictions: 13 → 11
- confidence_threshold: 0.7 → 0.75
- llm_model: → DeepSeek-V3.2

## 建议
- 过拟合: train R=0.619 vs val R=0.456
- 幻觉率 67%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
