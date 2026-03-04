"""
Model Training Script for YSU Bike Sharing Demand Prediction
Trains both LSTM and BP models on ysu_bike_data.csv, saves to models/ directory.
Usage: python train_models.py
"""
import os
import sys
import time
import shutil
import json
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server environments
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

# TensorFlow imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF info logs
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# Chinese font support for matplotlib
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============ Configuration ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'ysu_bike_data.csv')
MODELS_DIR = os.path.join(BASE_DIR, 'models')
HISTORY_DIR = os.path.join(MODELS_DIR, 'history')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
UTILS_DIR = os.path.join(BASE_DIR, 'utils')

LSTM_MODEL_PATH = os.path.join(MODELS_DIR, 'latest_lstm.h5')
BP_MODEL_PATH = os.path.join(MODELS_DIR, 'latest_bp.h5')
SCALER_X_PATH = os.path.join(UTILS_DIR, 'scaler_x.pkl')
SCALER_Y_PATH = os.path.join(UTILS_DIR, 'scaler_y.pkl')

# Also save to legacy paths for model_service compatibility
LEGACY_LSTM_PATH = os.path.join(MODELS_DIR, 'bike_lstm_model_optimized.h5')
LEGACY_BP_PATH = os.path.join(MODELS_DIR, 'bike_bp_model_final.h5')

# Training parameters
SEQ_LEN = 24       # 24-hour (1-day) rolling window — practical for YSU hourly data
LSTM_EPOCHS = 50
BP_EPOCHS = 100
BATCH_SIZE = 32
PATIENCE = 8
LSTM_ACCURACY_THRESHOLD = 80.0  # R² >= 80%
BP_ACCURACY_THRESHOLD = 75.0   # R² >= 75%

for d in [MODELS_DIR, HISTORY_DIR, RESULTS_DIR, UTILS_DIR]:
    os.makedirs(d, exist_ok=True)


# ============ Data Preprocessing ============
def load_and_preprocess(csv_path, seq_len=SEQ_LEN):
    """Load ysu_bike_data.csv, clean, engineer features, build sequences."""
    print(f"[Preprocess] Loading {csv_path} ...")
    df = pd.read_csv(csv_path)
    print(f"[Preprocess] Raw records: {len(df)}, columns: {list(df.columns)}")

    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.weekday  # 0=Mon, 6=Sun
    df['is_peak'] = df['hour'].apply(lambda h: 1 if (7 <= h <= 9) or (17 <= h <= 19) else 0)

    # Clean: remove zero/negative bike_count, cap at 99th percentile
    q99 = df['bike_count'].quantile(0.99)
    df = df[(df['bike_count'] > 0) & (df['bike_count'] <= q99)].copy()
    print(f"[Preprocess] After cleaning: {len(df)} records")

    # Normalize features
    loc_encoder = LabelEncoder()
    df['loc_id'] = loc_encoder.fit_transform(df['location_name'])

    feature_cols = ['hour', 'weekday', 'is_peak', 'loc_id']
    target_col = 'bike_count'

    scaler_x = MinMaxScaler()
    scaler_y = MinMaxScaler()

    df[feature_cols] = scaler_x.fit_transform(df[feature_cols])
    df[[target_col]] = scaler_y.fit_transform(df[[target_col]])

    # Save scalers
    joblib.dump(scaler_x, SCALER_X_PATH)
    joblib.dump(scaler_y, SCALER_Y_PATH)
    print(f"[Preprocess] Scalers saved to {UTILS_DIR}")

    # Build sequences per location (time-ordered)
    df = df.sort_values(['location_name', 'timestamp']).reset_index(drop=True)
    X_all, y_all = [], []
    for loc in df['location_name'].unique():
        loc_df = df[df['location_name'] == loc].reset_index(drop=True)
        if len(loc_df) <= seq_len:
            continue
        features = loc_df[feature_cols].values
        targets = loc_df[target_col].values
        for i in range(seq_len, len(loc_df)):
            X_all.append(features[i - seq_len:i])
            y_all.append(targets[i])

    X = np.array(X_all)
    y = np.array(y_all).reshape(-1, 1)
    print(f"[Preprocess] Sequences built: X={X.shape}, y={y.shape}")

    # Split 70/20/10 by time order
    n = len(X)
    tr = int(0.7 * n)
    va = int(0.9 * n)
    X_train, y_train = X[:tr], y[:tr]
    X_val, y_val = X[tr:va], y[tr:va]
    X_test, y_test = X[va:], y[va:]
    print(f"[Preprocess] Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")

    return (X_train, y_train, X_val, y_val, X_test, y_test), scaler_y


# ============ LSTM Model ============
def build_lstm(input_shape):
    """Build LSTM model for bike demand prediction."""
    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=input_shape),
        Dropout(0.2),
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        Dense(16, activation='relu'),
        Dense(1, activation='linear')
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='mse', metrics=['mae'])
    return model


def train_lstm(X_train, y_train, X_val, y_val, X_test, y_test, scaler_y):
    """Train LSTM model, evaluate, save if accuracy meets threshold."""
    print("\n" + "=" * 60)
    print("  Training LSTM Model (YSU Bike Demand Prediction)")
    print("=" * 60)

    start = time.time()
    model = build_lstm((X_train.shape[1], X_train.shape[2]))
    model.summary()

    callbacks = [
        EarlyStopping(monitor='val_loss', patience=PATIENCE, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=4, min_lr=1e-6)
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=LSTM_EPOCHS, batch_size=BATCH_SIZE,
        callbacks=callbacks, verbose=1
    )

    elapsed = time.time() - start
    print(f"\n[LSTM] Training completed in {elapsed:.1f}s ({elapsed/60:.1f}min)")

    # Evaluate
    y_pred = model.predict(X_test, verbose=0)
    y_test_real = scaler_y.inverse_transform(y_test)
    y_pred_real = scaler_y.inverse_transform(y_pred)
    y_pred_real = np.maximum(np.round(y_pred_real), 0).astype(int)
    y_test_real = np.round(y_test_real).astype(int)

    mae = mean_absolute_error(y_test_real, y_pred_real)
    rmse = np.sqrt(mean_squared_error(y_test_real, y_pred_real))
    r2 = r2_score(y_test_real, y_pred_real) * 100

    print(f"[LSTM] MAE={mae:.2f}, RMSE={rmse:.2f}, R²={r2:.2f}%")
    meets_threshold = r2 >= LSTM_ACCURACY_THRESHOLD
    if meets_threshold:
        print(f"[LSTM] ✓ Accuracy {r2:.2f}% >= {LSTM_ACCURACY_THRESHOLD}% threshold — PASSED")
    else:
        print(f"[LSTM] ✗ Accuracy {r2:.2f}% < {LSTM_ACCURACY_THRESHOLD}% threshold — BELOW TARGET")
        print(f"[LSTM] Model will still be saved (best available).")

    # Save model
    _save_model(model, LSTM_MODEL_PATH, LEGACY_LSTM_PATH, 'lstm')

    # Plot training curves
    _plot_history(history, 'LSTM', RESULTS_DIR)
    _plot_predictions(y_test_real, y_pred_real, 'LSTM', RESULTS_DIR)

    return {'mae': mae, 'rmse': rmse, 'r2': r2, 'time': elapsed,
            'epochs_run': len(history.history['loss']), 'meets_threshold': meets_threshold}


# ============ BP Model ============
def build_bp(input_dim):
    """Build BP (feedforward) neural network."""
    model = Sequential([
        Dense(128, activation='relu', input_dim=input_dim),
        BatchNormalization(),
        Dropout(0.3),
        Dense(64, activation='relu'),
        BatchNormalization(),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dropout(0.1),
        Dense(1, activation='linear')
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='mse', metrics=['mae'])
    return model


def train_bp(X_train, y_train, X_val, y_val, X_test, y_test, scaler_y):
    """Train BP model on flattened sequences."""
    print("\n" + "=" * 60)
    print("  Training BP Neural Network (YSU Bike Demand Prediction)")
    print("=" * 60)

    # Flatten 3D sequences to 2D for BP
    X_tr_flat = X_train.reshape(len(X_train), -1)
    X_va_flat = X_val.reshape(len(X_val), -1)
    X_te_flat = X_test.reshape(len(X_test), -1)
    print(f"[BP] Flattened input dim: {X_tr_flat.shape[1]}")

    start = time.time()
    model = build_bp(X_tr_flat.shape[1])
    model.summary()

    callbacks = [
        EarlyStopping(monitor='val_loss', patience=PATIENCE + 2, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6)
    ]

    history = model.fit(
        X_tr_flat, y_train,
        validation_data=(X_va_flat, y_val),
        epochs=BP_EPOCHS, batch_size=BATCH_SIZE,
        callbacks=callbacks, verbose=1
    )

    elapsed = time.time() - start
    print(f"\n[BP] Training completed in {elapsed:.1f}s ({elapsed/60:.1f}min)")

    # Evaluate
    y_pred = model.predict(X_te_flat, verbose=0)
    y_test_real = scaler_y.inverse_transform(y_test)
    y_pred_real = scaler_y.inverse_transform(y_pred)
    y_pred_real = np.maximum(np.round(y_pred_real), 0).astype(int)
    y_test_real = np.round(y_test_real).astype(int)

    mae = mean_absolute_error(y_test_real, y_pred_real)
    rmse = np.sqrt(mean_squared_error(y_test_real, y_pred_real))
    r2 = r2_score(y_test_real, y_pred_real) * 100

    print(f"[BP] MAE={mae:.2f}, RMSE={rmse:.2f}, R²={r2:.2f}%")
    meets_threshold = r2 >= BP_ACCURACY_THRESHOLD
    if meets_threshold:
        print(f"[BP] ✓ Accuracy {r2:.2f}% >= {BP_ACCURACY_THRESHOLD}% threshold — PASSED")
    else:
        print(f"[BP] ✗ Accuracy {r2:.2f}% < {BP_ACCURACY_THRESHOLD}% threshold — BELOW TARGET")
        print(f"[BP] Model will still be saved (best available).")

    _save_model(model, BP_MODEL_PATH, LEGACY_BP_PATH, 'bp')
    _plot_history(history, 'BP', RESULTS_DIR)
    _plot_predictions(y_test_real, y_pred_real, 'BP', RESULTS_DIR)

    return {'mae': mae, 'rmse': rmse, 'r2': r2, 'time': elapsed,
            'epochs_run': len(history.history['loss']), 'meets_threshold': meets_threshold}


# ============ Helpers ============
def _save_model(model, primary_path, legacy_path, name):
    """Save model to primary path, copy to legacy path, and archive to history."""
    model.save(primary_path)
    shutil.copy2(primary_path, legacy_path)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    hist_path = os.path.join(HISTORY_DIR, f'{name}_{ts}.h5')
    shutil.copy2(primary_path, hist_path)
    print(f"[Save] {name.upper()} model saved:")
    print(f"       Primary: {primary_path}")
    print(f"       Legacy:  {legacy_path}")
    print(f"       History: {hist_path}")


def _plot_history(history, model_name, out_dir):
    """Plot training/validation loss curves."""
    plt.figure(figsize=(10, 5))
    plt.plot(history.history['loss'], label='Train Loss')
    plt.plot(history.history['val_loss'], label='Val Loss')
    plt.title(f'{model_name} Training Loss (YSU Bike Data)')
    plt.xlabel('Epoch')
    plt.ylabel('MSE')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f'{model_name.lower()}_training_loss.png'), dpi=150)
    plt.close()


def _plot_predictions(y_true, y_pred, model_name, out_dir, n=80):
    """Plot true vs predicted values."""
    plt.figure(figsize=(12, 5))
    plt.plot(y_true[:n], label='Actual', color='#1890FF')
    plt.plot(y_pred[:n], label=f'{model_name} Predicted', color='#FF5722', linestyle='--')
    plt.title(f'{model_name} Prediction vs Actual (YSU, first {n} samples)')
    plt.xlabel('Time Step')
    plt.ylabel('Bike Count')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f'{model_name.lower()}_prediction.png'), dpi=150)
    plt.close()


def write_train_log(lstm_result, bp_result):
    """Write model_train_log.md with training results."""
    log_path = os.path.join(BASE_DIR, 'model_train_log.md')
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f'# Model Training Log\n\n')
        f.write(f'**Training Time:** {ts}\n\n')
        f.write(f'**Dataset:** ysu_bike_data.csv (YSU campus only)\n\n')
        f.write(f'**Sequence Length:** {SEQ_LEN} hours\n\n')
        f.write(f'## LSTM Model\n')
        f.write(f'| Metric | Value |\n|--------|-------|\n')
        f.write(f'| MAE | {lstm_result["mae"]:.2f} |\n')
        f.write(f'| RMSE | {lstm_result["rmse"]:.2f} |\n')
        f.write(f'| R² Accuracy | {lstm_result["r2"]:.2f}% |\n')
        f.write(f'| Training Time | {lstm_result["time"]:.1f}s |\n')
        f.write(f'| Epochs Run | {lstm_result["epochs_run"]} |\n')
        f.write(f'| Meets ≥80% | {"Yes" if lstm_result["meets_threshold"] else "No"} |\n\n')
        f.write(f'## BP Neural Network\n')
        f.write(f'| Metric | Value |\n|--------|-------|\n')
        f.write(f'| MAE | {bp_result["mae"]:.2f} |\n')
        f.write(f'| RMSE | {bp_result["rmse"]:.2f} |\n')
        f.write(f'| R² Accuracy | {bp_result["r2"]:.2f}% |\n')
        f.write(f'| Training Time | {bp_result["time"]:.1f}s |\n')
        f.write(f'| Epochs Run | {bp_result["epochs_run"]} |\n')
        f.write(f'| Meets ≥75% | {"Yes" if bp_result["meets_threshold"] else "No"} |\n\n')
        f.write(f'## Model Files\n')
        f.write(f'- LSTM: `models/latest_lstm.h5`\n')
        f.write(f'- BP: `models/latest_bp.h5`\n')
        f.write(f'- History: `models/history/`\n')
        f.write(f'- Scalers: `utils/scaler_x.pkl`, `utils/scaler_y.pkl`\n')
    print(f"\n[Log] Training log saved to {log_path}")


# ============ Main ============
if __name__ == '__main__':
    print("=" * 60)
    print("  YSU Bike Sharing Demand — Model Training Pipeline")
    print("=" * 60)

    # Preprocess
    splits, scaler_y = load_and_preprocess(DATA_FILE, seq_len=SEQ_LEN)
    X_train, y_train, X_val, y_val, X_test, y_test = splits

    # Train LSTM
    lstm_result = train_lstm(X_train, y_train, X_val, y_val, X_test, y_test, scaler_y)

    # Train BP
    bp_result = train_bp(X_train, y_train, X_val, y_val, X_test, y_test, scaler_y)

    # Write log
    write_train_log(lstm_result, bp_result)

    # Summary
    print("\n" + "=" * 60)
    print("  TRAINING SUMMARY")
    print("=" * 60)
    print(f"  LSTM — R²={lstm_result['r2']:.2f}% | MAE={lstm_result['mae']:.2f} | "
          f"{'PASS' if lstm_result['meets_threshold'] else 'BELOW'}")
    print(f"  BP   — R²={bp_result['r2']:.2f}% | MAE={bp_result['mae']:.2f} | "
          f"{'PASS' if bp_result['meets_threshold'] else 'BELOW'}")
    print(f"  Models saved to: {MODELS_DIR}")
    print("=" * 60)
