# Geo Loop 9 — 2026-03-16 19:12 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.4545 | 0.6285 |
| R_event | 0.6000 | 0.2353 |
| R_causal | 0.6833 | 0.6833 |
| R_timing | 0.6748 | 0.7000 |
| R_calibration | 0.7171 | 0.5421 |
| R_hallucination | 0.5000 | 0.8333 |
| Matches | 6/8 | 2/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: qwen3-32b
- Max predictions: 13
- Confidence threshold: 0.7

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 391.0s

## 策略变更
- max_predictions: 15 → 13
- confidence_threshold: 0.65 → 0.7000000000000001
- llm_model: DeepSeek-V3.2 → qwen3-32b

## 建议
- 过拟合: train R=0.545 vs val R=0.371
- 幻觉率 83%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
