# Geo Loop 18 — 2026-03-16 20:16 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.3674 | 0.7384 |
| R_event | 0.7778 | 0.1333 |
| R_causal | 0.6600 | 0.6600 |
| R_timing | 0.6641 | 0.4000 |
| R_calibration | 0.8230 | 0.4330 |
| R_hallucination | 0.3000 | 0.9000 |
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
- 耗时: 317.9s

## 策略变更
- max_predictions: 10 → 10
- confidence_threshold: 0.65 → 0.7
- llm_model: DeepSeek-V3.2 → qwen3-32b

## 建议
- 过拟合: train R=0.633 vs val R=0.262
- 幻觉率 90%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
