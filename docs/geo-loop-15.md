# Geo Loop 15 — 2026-03-16 20:00 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.4152 | 0.5825 |
| R_event | 0.6957 | 0.3000 |
| R_causal | 0.6733 | 0.6733 |
| R_timing | 0.6436 | 0.8000 |
| R_calibration | 0.7893 | 0.5960 |
| R_hallucination | 0.4667 | 0.8000 |
| Matches | 8/8 | 3/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: DeepSeek-V3.2
- Max predictions: 13
- Confidence threshold: 0.55

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 326.8s

## 策略变更
- max_predictions: 15 → 13
- confidence_threshold: 0.5 → 0.55
- llm_model: → DeepSeek-V3.2

## 建议
- 过拟合: train R=0.585 vs val R=0.417
- 幻觉率 80%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
