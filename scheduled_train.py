"""
Scheduled Model Training for YSU Bike Sharing Platform
Runs daily at 2:00 AM to retrain LSTM and BP models using the latest 7 days of data.
Compares new model accuracy with existing models before overwriting.

Usage:
  python scheduled_train.py              # Run continuously (daily at 2:00 AM)
  python scheduled_train.py --now        # Train immediately and exit
"""
import os
import sys
import time
import shutil
import logging
from datetime import datetime, timedelta

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_dispatch_platform'))

import django
django.setup()

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

from django.utils import timezone as tz
from data_process.models import BikeRideData, WeatherData
from demand_prediction.models import ModelTrainLog
from system_support.models import SystemLog

import schedule

# ============ Paths ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, 'models')
HISTORY_DIR = os.path.join(MODELS_DIR, 'history')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
UTILS_DIR = os.path.join(BASE_DIR, 'utils')

LSTM_PATH = os.path.join(MODELS_DIR, 'latest_lstm.h5')
BP_PATH = os.path.join(MODELS_DIR, 'latest_bp.h5')
LEGACY_LSTM = os.path.join(MODELS_DIR, 'bike_lstm_model_optimized.h5')
LEGACY_BP = os.path.join(MODELS_DIR, 'bike_bp_model_final.h5')
SCALER_X_PATH = os.path.join(UTILS_DIR, 'scaler_x.pkl')
SCALER_Y_PATH = os.path.join(UTILS_DIR, 'scaler_y.pkl')
STATIC_CSV = os.path.join(BASE_DIR, 'ysu_bike_data.csv')

SEQ_LEN = 24
LSTM_THRESHOLD = 80.0
BP_THRESHOLD = 75.0

for d in [MODELS_DIR, HISTORY_DIR, RESULTS_DIR, UTILS_DIR]:
    os.makedirs(d, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ScheduledTrain] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, 'logs', 'scheduled_train.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)


# ============ Data Collection ============
def collect_training_data(days=7):
    """
    Collect the latest `days` of ride data from Django DB.
    Falls back to ysu_bike_data.csv if DB has insufficient data.
    Returns a DataFrame with columns compatible with the preprocessing pipeline.
    """
    cutoff = tz.now() - timedelta(days=days)
    db_count = BikeRideData.objects.filter(ride_datetime__gte=cutoff).count()
    logger.info(f"DB ride records in last {days} days: {db_count}")

    if db_count >= 500:
        # Use DB data — build a DataFrame matching ysu_bike_data.csv schema
        logger.info("Using database ride data for training.")
        from config import PARKING_SPOTS
        rows = []
        qs = BikeRideData.objects.filter(ride_datetime__gte=cutoff).order_by('ride_datetime')
        for r in qs.iterator():
            coords = PARKING_SPOTS.get(r.start_point, (119.528, 39.910))
            rows.append({
                'timestamp': r.ride_datetime,
                'longitude': coords[0],
                'latitude': coords[1],
                'bike_count': max(1, int(r.duration)),  # Use duration as proxy for bike count
                'location_name': r.start_point,
                'weekday': r.ride_datetime.weekday(),
                'hour': r.ride_datetime.hour,
                'is_peak': 1 if r.ride_datetime.hour in (7,8,9,17,18,19) else 0,
            })
        df = pd.DataFrame(rows)
    else:
        # Fall back to static CSV
        logger.info(f"Insufficient DB data ({db_count} < 500). Using ysu_bike_data.csv.")
        df = pd.read_csv(STATIC_CSV)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    logger.info(f"Training data size: {len(df)} records")
    return df


def preprocess(df, seq_len=SEQ_LEN):
    """Preprocess DataFrame into train/val/test splits."""
    # Clean
    if 'bike_count' in df.columns:
        q99 = df['bike_count'].quantile(0.99)
        df = df[(df['bike_count'] > 0) & (df['bike_count'] <= q99)].copy()

    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    df['weekday'] = pd.to_datetime(df['timestamp']).dt.weekday
    df['is_peak'] = df['hour'].apply(lambda h: 1 if (7 <= h <= 9) or (17 <= h <= 19) else 0)

    loc_enc = LabelEncoder()
    df['loc_id'] = loc_enc.fit_transform(df['location_name'])

    feat_cols = ['hour', 'weekday', 'is_peak', 'loc_id']
    scaler_x = MinMaxScaler()
    scaler_y = MinMaxScaler()
    df[feat_cols] = scaler_x.fit_transform(df[feat_cols])
    df[['bike_count']] = scaler_y.fit_transform(df[['bike_count']])

    joblib.dump(scaler_x, SCALER_X_PATH)
    joblib.dump(scaler_y, SCALER_Y_PATH)

    df = df.sort_values(['location_name', 'timestamp']).reset_index(drop=True)
    X, y = [], []
    for loc in df['location_name'].unique():
        ldf = df[df['location_name'] == loc].reset_index(drop=True)
        if len(ldf) <= seq_len:
            continue
        feats = ldf[feat_cols].values
        tgts = ldf['bike_count'].values
        for i in range(seq_len, len(ldf)):
            X.append(feats[i-seq_len:i])
            y.append(tgts[i])

    X = np.array(X)
    y = np.array(y).reshape(-1, 1)
    n = len(X)
    tr, va = int(0.7*n), int(0.9*n)
    return (X[:tr], y[:tr], X[tr:va], y[tr:va], X[va:], y[va:]), scaler_y


# ============ Training ============
def train_and_evaluate(model_type, X_tr, y_tr, X_va, y_va, X_te, y_te, scaler_y):
    """Train either LSTM or BP model and return metrics."""
    start = time.time()

    if model_type == 'lstm':
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(X_tr.shape[1], X_tr.shape[2])),
            Dropout(0.2),
            LSTM(32), Dropout(0.2),
            Dense(16, activation='relu'), Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        xtr, xva, xte = X_tr, X_va, X_te
        epochs = 50
    else:
        input_dim = X_tr.shape[1] * X_tr.shape[2]
        model = Sequential([
            Dense(128, activation='relu', input_dim=input_dim),
            BatchNormalization(), Dropout(0.3),
            Dense(64, activation='relu'),
            BatchNormalization(), Dropout(0.2),
            Dense(32, activation='relu'), Dropout(0.1),
            Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        xtr = X_tr.reshape(len(X_tr), -1)
        xva = X_va.reshape(len(X_va), -1)
        xte = X_te.reshape(len(X_te), -1)
        epochs = 100

    cbs = [
        EarlyStopping(monitor='val_loss', patience=8, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=4, min_lr=1e-6)
    ]
    model.fit(xtr, y_tr, validation_data=(xva, y_va),
              epochs=epochs, batch_size=32, callbacks=cbs, verbose=0)

    yp = model.predict(xte, verbose=0)
    yt_real = scaler_y.inverse_transform(y_te)
    yp_real = np.maximum(np.round(scaler_y.inverse_transform(yp)), 0).astype(int)
    yt_real = np.round(yt_real).astype(int)

    mae = mean_absolute_error(yt_real, yp_real)
    rmse = np.sqrt(mean_squared_error(yt_real, yp_real))
    r2 = r2_score(yt_real, yp_real) * 100
    elapsed = time.time() - start

    return model, {'mae': mae, 'rmse': rmse, 'r2': r2, 'time': elapsed}


def should_replace_model(new_r2, model_type):
    """Decide whether new model should replace existing one."""
    threshold = LSTM_THRESHOLD if model_type == 'lstm' else BP_THRESHOLD
    return new_r2 >= threshold


def save_model(model, model_type, metrics):
    """Save model to primary, legacy, and history paths."""
    primary = LSTM_PATH if model_type == 'lstm' else BP_PATH
    legacy = LEGACY_LSTM if model_type == 'lstm' else LEGACY_BP

    model.save(primary)
    shutil.copy2(primary, legacy)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(primary, os.path.join(HISTORY_DIR, f'{model_type}_{ts}.h5'))
    logger.info(f"[{model_type.upper()}] Model saved (R²={metrics['r2']:.2f}%)")


def log_training(model_type, metrics, status, error_msg=None):
    """Record training result in Django ModelTrainLog."""
    now = tz.now()
    dur = int(metrics['time'])
    ModelTrainLog.objects.create(
        train_date=now.date(),
        start_time=now - timedelta(seconds=dur),
        end_time=now,
        duration=dur,
        mae=metrics['mae'],
        rmse=metrics['rmse'],
        r2=metrics['r2'],
        model_filename=f'latest_{model_type}.h5',
        status=status,
        error_message=error_msg
    )


# ============ Main Training Job ============
def run_training_job():
    """Full training pipeline: collect data, train both models, compare, save."""
    logger.info("=" * 60)
    logger.info("  Scheduled Training Job Started")
    logger.info("=" * 60)

    try:
        df = collect_training_data(days=7)
        splits, scaler_y = preprocess(df)
        X_tr, y_tr, X_va, y_va, X_te, y_te = splits

        if len(X_tr) < 100:
            msg = f"Insufficient training samples ({len(X_tr)}). Skipping."
            logger.warning(msg)
            log_training('lstm', {'mae':0,'rmse':0,'r2':0,'time':0}, 'failed', msg)
            return

        # Train LSTM
        logger.info("Training LSTM...")
        lstm_model, lstm_m = train_and_evaluate('lstm', X_tr, y_tr, X_va, y_va, X_te, y_te, scaler_y)
        logger.info(f"[LSTM] R²={lstm_m['r2']:.2f}% MAE={lstm_m['mae']:.2f} ({lstm_m['time']:.0f}s)")

        if should_replace_model(lstm_m['r2'], 'lstm'):
            save_model(lstm_model, 'lstm', lstm_m)
            log_training('lstm', lstm_m, 'success')
        else:
            logger.warning(f"[LSTM] R²={lstm_m['r2']:.2f}% below {LSTM_THRESHOLD}%. Keeping old model.")
            log_training('lstm', lstm_m, 'failed', f"Accuracy {lstm_m['r2']:.2f}% < {LSTM_THRESHOLD}%")

        # Train BP
        logger.info("Training BP...")
        bp_model, bp_m = train_and_evaluate('bp', X_tr, y_tr, X_va, y_va, X_te, y_te, scaler_y)
        logger.info(f"[BP] R²={bp_m['r2']:.2f}% MAE={bp_m['mae']:.2f} ({bp_m['time']:.0f}s)")

        if should_replace_model(bp_m['r2'], 'bp'):
            save_model(bp_model, 'bp', bp_m)
            log_training('bp', bp_m, 'success')
        else:
            logger.warning(f"[BP] R²={bp_m['r2']:.2f}% below {BP_THRESHOLD}%. Keeping old model.")
            log_training('bp', bp_m, 'failed', f"Accuracy {bp_m['r2']:.2f}% < {BP_THRESHOLD}%")

        # System log
        SystemLog.objects.create(
            action='predict',
            description=f"Scheduled training: LSTM R²={lstm_m['r2']:.1f}%, BP R²={bp_m['r2']:.1f}%"
        )

        logger.info("Training job completed successfully.")

    except Exception as e:
        logger.error(f"Training job failed: {e}", exc_info=True)
        try:
            log_training('lstm', {'mae':0,'rmse':0,'r2':0,'time':0}, 'failed', str(e))
        except Exception:
            pass


# ============ Entry Point ============
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='YSU Scheduled Model Training')
    parser.add_argument('--now', action='store_true', help='Train immediately and exit')
    args = parser.parse_args()

    if args.now:
        logger.info("Running immediate training...")
        run_training_job()
    else:
        logger.info("Scheduling daily training at 02:00 AM...")
        schedule.every().day.at("02:00").do(run_training_job)

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped.")
