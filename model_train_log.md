# Model Training Log

**Training Time:** 2026-03-04 17:47:09

**Dataset:** ysu_bike_data.csv (YSU campus only)

**Sequence Length:** 24 hours

## LSTM Model
| Metric | Value |
|--------|-------|
| MAE | 4.27 |
| RMSE | 5.09 |
| R² Accuracy | 81.24% |
| Training Time | 307.9s |
| Epochs Run | 25 |
| Meets ≥80% | Yes |

## BP Neural Network
| Metric | Value |
|--------|-------|
| MAE | 4.27 |
| RMSE | 5.08 |
| R² Accuracy | 81.33% |
| Training Time | 97.8s |
| Epochs Run | 44 |
| Meets ≥75% | Yes |

## Model Files
- LSTM: `models/latest_lstm.h5`
- BP: `models/latest_bp.h5`
- History: `models/history/`
- Scalers: `utils/scaler_x.pkl`, `utils/scaler_y.pkl`
