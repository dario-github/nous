# Geo Loop 11 — 2026-03-16 19:19 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.4267 | 0.6309 |
| R_event | 0.6957 | 0.2000 |
| R_causal | 0.6733 | 0.6733 |
| R_timing | 0.5811 | 0.7000 |
| R_calibration | 0.7787 | 0.6120 |
| R_hallucination | 0.4667 | 0.8667 |
| Matches | 8/8 | 2/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: DeepSeek-V3.2
- Max predictions: 13
- Confidence threshold: 0.55

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 254.0s

## 策略变更
- max_predictions: 15 → 13
- confidence_threshold: 0.5 → 0.55
- llm_model: → DeepSeek-V3.2

## 建议
- 过拟合: train R=0.573 vs val R=0.369
- 幻觉率 87%：提高置信度阈值
- ⚠️ 连续 3 轮未改善，考虑换方向
