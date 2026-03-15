# Model Training Log

**Training Time:** 2026-03-09 22:32:56

**Dataset:** ysu_bike_data.csv (YSU campus only)

**Sequence Length:** 24 hours

## LSTM Model
| Metric | Value |
|--------|-------|
| MAE | 4.27 |
| RMSE | 5.07 |
| R² Accuracy | 81.39% |
| Training Time | 652.7s |
| Epochs Run | 30 |
| Meets ≥80% | No |

## BP Neural Network
| Metric | Value |
|--------|-------|
| MAE | 4.26 |
| RMSE | 5.07 |
| R² Accuracy | 81.43% |
| Training Time | 107.4s |
| Epochs Run | 55 |
| Meets ≥75% | Yes |

## Model Files
- LSTM: `models/latest_lstm.h5`
- BP: `models/latest_bp.h5`
- History: `models/history/`
- Scalers: `utils/scaler_x.pkl`, `utils/scaler_y.pkl`
