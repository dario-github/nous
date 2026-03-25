# Geo Loop 8 — 2026-03-16 19:05 UTC

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
- Model: DeepSeek-V3.2
- Max predictions: 15
- Confidence threshold: 0.65

## 诊断
- 最弱分项: R_event
- 过拟合: ✅ No
- 耗时: 37.2s

## 策略变更
- confidence_threshold: 0.6 → 0.65
- llm_model: → DeepSeek-V3.2

## 建议
- 幻觉率 67%：提高置信度阈值
- R_calibration 低：LLM 综合层应更积极地调整概率
- ⚠️ 连续 3 轮未改善，考虑换方向
