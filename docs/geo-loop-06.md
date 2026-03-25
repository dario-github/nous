# Geo Loop 6 — 2026-03-16 19:04 UTC

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | 0.4331 | 0.5227 |
| R_event | 0.6957 | 0.5000 |
| R_causal | 0.6733 | 0.6733 |
| R_timing | 0.5561 | 0.7147 |
| R_calibration | 0.7655 | 0.5922 |
| R_hallucination | 0.4667 | 0.6667 |
| Matches | 8/8 | 5/5 |

## 策略
- LLM synthesis: True
- LLM judge: True
- Model: qwen3-32b
- Max predictions: 15
- Confidence threshold: 0.55

## 诊断
- 最弱分项: R_event
- 过拟合: ✅ No
- 耗时: 36.9s

## 策略变更
- confidence_threshold: 0.5 → 0.55

## 建议
- 幻觉率 67%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
