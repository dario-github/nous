# Geo Loop 13 — 2026-03-16 19:31 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.4391 | 0.6358 |
| R_event | 0.6364 | 0.2105 |
| R_causal | 0.6714 | 0.6714 |
| R_timing | 0.6641 | 0.7000 |
| R_calibration | 0.7625 | 0.5696 |
| R_hallucination | 0.5000 | 0.8571 |
| Matches | 7/8 | 2/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: DeepSeek-V3.2
- Max predictions: 10
- Confidence threshold: 0.65

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 289.8s

## 策略变更
- max_predictions: 11 → 10
- confidence_threshold: 0.6 → 0.65
- llm_model: → DeepSeek-V3.2

## 建议
- 过拟合: train R=0.561 vs val R=0.364
- 幻觉率 86%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
