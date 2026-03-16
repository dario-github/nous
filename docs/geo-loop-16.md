# Geo Loop 16 — 2026-03-16 20:07 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.3897 | 0.6285 |
| R_event | 0.7368 | 0.2500 |
| R_causal | 0.6636 | 0.6636 |
| R_timing | 0.6641 | 0.7000 |
| R_calibration | 0.8007 | 0.5370 |
| R_hallucination | 0.3636 | 0.8182 |
| Matches | 7/8 | 2/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: qwen3-32b
- Max predictions: 11
- Confidence threshold: 0.6

## 诊断
- 最弱分项: R_event
- 过拟合: ⚠️ YES
- 耗时: 418.5s

## 策略变更
- max_predictions: 13 → 11
- confidence_threshold: 0.55 → 0.6
- llm_model: DeepSeek-V3.2 → qwen3-32b

## 建议
- 过拟合: train R=0.610 vs val R=0.371
- 幻觉率 82%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
