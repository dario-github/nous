# Geo Loop 14 — 2026-03-16 19:39 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.4297 | 0.7568 |
| R_event | 0.7368 | 0.1250 |
| R_causal | 0.7000 | 0.7000 |
| R_timing | 0.3810 | 0.2000 |
| R_calibration | 0.7673 | 0.4582 |
| R_hallucination | 0.3636 | 0.9091 |
| Matches | 7/8 | 1/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: qwen3-32b
- Max predictions: 10
- Confidence threshold: 0.7

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 433.1s

## 策略变更
- max_predictions: 10 → 10
- confidence_threshold: 0.65 → 0.7
- llm_model: DeepSeek-V3.2 → qwen3-32b

## 建议
- 过拟合: train R=0.570 vs val R=0.243
- 幻觉率 91%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
