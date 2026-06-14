"""
BSDP 项目 - 48h 窗口优化实验（GPU 加速版）
配置：
- 固定 48h 滑动窗口（实验验证最优）
- 100 轮训练 + 早停机制（patience=10）
- 周期特征工程（前一天/周同时段）
- GPU 加速训练
- 结果自动保存至 experiment_results_48h.txt
"""

import os
import sys

# 添加 CUDA DLL 路径到环境变量
venv_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
nvidia_packages = os.path.join(venv_path, 'venv', 'Lib', 'site-packages', 'nvidia')

if os.path.exists(nvidia_packages):
    # 添加所有 NVIDIA 包的 bin 目录到 PATH
    for package in ['cudnn', 'cublas', 'cuda_runtime']:
        package_path = os.path.join(nvidia_packages, package)
        bin_path = os.path.join(package_path, 'bin')
        if os.path.exists(bin_path):
            os.environ['PATH'] = bin_path + os.pathsep + os.environ.get('PATH', '')
        elif os.path.exists(package_path):
            os.environ['PATH'] = package_path + os.pathsep + os.environ.get('PATH', '')

import numpy as np
import pandas as pd
import tensorflow as tf
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

# ==================== GPU 配置 ====================
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        print(f"✓ GPU 已启用：{gpus}")
        print(f"✓ 显存动态分配已开启")
    except RuntimeError as e:
        print(f"✗ GPU 配置失败：{e}")
else:
    print("⚠ 未检测到 GPU，将使用 CPU 训练")

# 设置随机种子
np.random.seed(42)
tf.random.set_seed(42)

# 日志配置
log_file = "experiment_results_48h.txt"
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

# 数据路径
DATASET_DIR = r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\BSDP\bike_demand_research\dataset"
RIDE_DATA_PATH = os.path.join(DATASET_DIR, "daily_rent_detail.csv")
WEATHER_DATA_PATH = os.path.join(DATASET_DIR, "weather.csv")

def load_and_preprocess():
    """数据加载与预处理"""
    log("=" * 80)
    log("【数据预处理】")
    log("=" * 80)
    
    ride_df = pd.read_csv(RIDE_DATA_PATH, usecols=['started_at', 'ended_at', 
                                                    'start_station_id', 'end_station_id'])
    weather_df = pd.read_csv(WEATHER_DATA_PATH, usecols=['datetime', 'temp', 
                                                          'humidity', 'windspeed', 'precip'])
    
    log(f"原始数据量：{len(ride_df):,} 条")
    
    ride_df['started_at'] = pd.to_datetime(ride_df['started_at'], format='mixed')
    ride_df['ended_at'] = pd.to_datetime(ride_df['ended_at'], format='mixed')
    weather_df['datetime'] = pd.to_datetime(weather_df['datetime'])
    
    start_date = pd.Timestamp('2022-01-01')
    end_date = pd.Timestamp('2023-12-31 23:59:59')
    ride_df = ride_df[(ride_df['started_at'] >= start_date) & (ride_df['started_at'] <= end_date)]
    weather_df = weather_df[(weather_df['datetime'] >= start_date) & (weather_df['datetime'] <= end_date)]
    
    log(f"筛选后数据量：{len(ride_df):,} 条 (2022-2023 年)")
    
    ride_df['start_hour'] = ride_df['started_at'].dt.floor('h')
    ride_df['end_hour'] = ride_df['ended_at'].dt.floor('h')
    
    D_t = ride_df.groupby(['start_station_id', 'start_hour']).size().reset_index(name='D_t')
    D_t.rename(columns={'start_station_id': 'station_id', 'start_hour': 'hour'}, inplace=True)
    
    R_t = ride_df.groupby(['end_station_id', 'end_hour']).size().reset_index(name='R_t')
    R_t.rename(columns={'end_station_id': 'station_id', 'end_hour': 'hour'}, inplace=True)
    
    flow_df = pd.merge(D_t, R_t, on=['station_id', 'hour'], how='outer')
    flow_df['D_t'] = flow_df['D_t'].fillna(0)
    flow_df['R_t'] = flow_df['R_t'].fillna(0)
    flow_df['F_t'] = flow_df['R_t'] - flow_df['D_t']
    flow_df = flow_df.sort_values(['station_id', 'hour'])
    flow_df['S_t'] = flow_df.groupby('station_id')['F_t'].cumsum()
    
    Q1 = flow_df['S_t'].quantile(0.25)
    Q3 = flow_df['S_t'].quantile(0.75)
    IQR = Q3 - Q1
    flow_df = flow_df[(flow_df['S_t'] >= Q1 - 1.5 * IQR) & (flow_df['S_t'] <= Q3 + 1.5 * IQR)]
    flow_df = flow_df[abs(flow_df['F_t']) <= flow_df['F_t'].quantile(0.99)]
    
    log(f"预处理后样本数：{len(flow_df):,} 条")
    log(f"有效停车点：{flow_df['station_id'].nunique()} 个")
    
    weather_df['date'] = weather_df['datetime'].dt.date
    flow_df['date'] = flow_df['hour'].dt.date
    weather_df['is_rain'] = (weather_df['precip'] > 0).astype(int)
    flow_df = pd.merge(flow_df, weather_df[['date', 'temp', 'humidity', 'windspeed', 'is_rain']], 
                       on='date', how='left')
    flow_df[['temp', 'humidity', 'windspeed']] = flow_df[['temp', 'humidity', 'windspeed']].interpolate()
    flow_df['is_rain'] = flow_df['is_rain'].fillna(0)
    
    return flow_df

def feature_engineering(flow_df):
    """特征工程（48h 窗口优化）"""
    log("\n" + "=" * 80)
    log("【特征工程】")
    log("=" * 80)
    
    flow_df['hour_of_day'] = flow_df['hour'].dt.hour
    flow_df['day_of_week'] = flow_df['hour'].dt.weekday
    flow_df['is_weekday'] = (flow_df['day_of_week'] < 5).astype(int)
    flow_df['is_peak_hour'] = (((flow_df['hour_of_day'] >= 7) & (flow_df['hour_of_day'] <= 9)) | 
                               ((flow_df['hour_of_day'] >= 17) & (flow_df['hour_of_day'] <= 19))).astype(int)
    
    flow_df = flow_df.sort_values(['station_id', 'hour'])
    flow_df['F_t_mean_24h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.rolling(window=24, min_periods=1).mean())
    flow_df['F_t_max_24h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.rolling(window=24, min_periods=1).max())
    flow_df['F_t_std_24h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.rolling(window=24, min_periods=1).std()).fillna(0)
    
    # 周期特征
    flow_df['F_t_lag_24h'] = flow_df.groupby('station_id')['F_t'].shift(24).fillna(0)
    flow_df['F_t_lag_168h'] = flow_df.groupby('station_id')['F_t'].shift(168).fillna(0)
    flow_df['F_t_lag24_mean3h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.shift(24).rolling(window=3, min_periods=1).mean()).fillna(0)
    flow_df['F_t_lag168_mean3h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.shift(168).rolling(window=3, min_periods=1).mean()).fillna(0)
    
    log("✓ 周期特征：F_t_lag_24h, F_t_lag_168h, F_t_lag24_mean3h, F_t_lag168_mean3h")
    
    le = LabelEncoder()
    flow_df['station_id_encoded'] = le.fit_transform(flow_df['station_id'].astype(str))
    
    feature_cols = [
        'station_id_encoded', 'hour_of_day', 'day_of_week', 'is_weekday', 'is_peak_hour',
        'F_t_mean_24h', 'F_t_max_24h', 'F_t_std_24h', 'F_t_lag_24h',
        'F_t_lag_168h', 'F_t_lag24_mean3h', 'F_t_lag168_mean3h',
        'temp', 'humidity', 'windspeed', 'is_rain'
    ]
    
    scaler = MinMaxScaler()
    flow_df[feature_cols] = scaler.fit_transform(flow_df[feature_cols])
    
    log(f"✓ 特征维度：{len(feature_cols)} 维")
    log(f"✓ 有效停车点：{len(le.classes_)} 个")
    
    return flow_df, feature_cols, le, scaler

def build_sequences(df, window_size=48):
    """构建 48h 窗口序列"""
    X, y = [], []
    
    feature_cols = [
        'station_id_encoded', 'hour_of_day', 'day_of_week', 'is_weekday', 'is_peak_hour',
        'F_t_mean_24h', 'F_t_max_24h', 'F_t_std_24h', 'F_t_lag_24h',
        'F_t_lag_168h', 'F_t_lag24_mean3h', 'F_t_lag168_mean3h',
        'temp', 'humidity', 'windspeed', 'is_rain'
    ]
    
    df = df.sort_values(['station_id', 'hour'])
    
    for station_id in df['station_id'].unique():
        station_data = df[df['station_id'] == station_id].copy()
        
        if len(station_data) < window_size + 1:
            continue
        
        values = station_data[feature_cols].values
        targets = station_data['F_t'].values
        
        for i in range(window_size, len(station_data)):
            X.append(values[i-window_size:i])
            y.append(targets[i])
    
    return np.array(X), np.array(y)

def split_by_time(df):
    """按时间划分数据集"""
    train_end = pd.Timestamp('2023-06-30 23:59:59')
    val_end = pd.Timestamp('2023-09-30 23:59:59')
    
    train_df = df[df['hour'] <= train_end]
    val_df = df[(df['hour'] > train_end) & (df['hour'] <= val_end)]
    test_df = df[df['hour'] > val_end]
    
    log(f"\n数据集划分：")
    log(f"  训练集：{len(train_df):,} 条 (70%)")
    log(f"  验证集：{len(val_df):,} 条 (20%)")
    log(f"  测试集：{len(test_df):,} 条 (10%)")
    
    return train_df, val_df, test_df

def build_improved_lstm(input_shape):
    """改进 LSTM（48h 窗口）"""
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(128, return_sequences=True, input_shape=input_shape, dropout=0.2),
        tf.keras.layers.LSTM(64, dropout=0.2),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1)
    ])
    model.compile(optimizer=tf.keras.optimizers.AdamW(learning_rate=1e-3, weight_decay=1e-4), 
                  loss='mse', metrics=['mae'])
    return model

def train_model(model, X_train, y_train, X_val, y_val, model_name, epochs=100, batch_size=32):
    """训练模型（100 轮 + 早停）"""
    log(f"\n训练 {model_name}...")
    log(f"  配置：{epochs}轮，Batch={batch_size}, 早停 patience=10, GPU 加速={'ON' if gpus else 'OFF'}")
    
    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor='val_loss', patience=10, restore_best_weights=True, verbose=1
    )
    
    lr_scheduler = tf.keras.callbacks.ReduceLROnPlateau(
        monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6, verbose=1
    )
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stopping, lr_scheduler],
        verbose=1
    )
    
    log(f"  实际训练轮次：{len(history.history['loss'])}")
    log(f"  最佳验证损失：{min(history.history['val_loss']):.6f}")
    
    return model, history

def evaluate_model(model, X_test, y_test, model_name):
    """模型评估"""
    log(f"\n评估 {model_name}...")
    
    y_pred = model.predict(X_test, verbose=0).flatten()
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    log(f"{model_name} - MAE: {mae:.4f}, RMSE: {rmse:.4f}, R²: {r2:.4f}")
    
    return mae, rmse, r2

def main():
    log("\n" + "=" * 80)
    log("BSDP 项目 - 48h 窗口优化实验（GPU 加速版）")
    log("=" * 80)
    log(f"实验时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"GPU 状态：{'启用' if gpus else '未启用'}")
    
    # 1. 数据预处理
    flow_df = load_and_preprocess()
    
    # 2. 特征工程
    flow_df, feature_cols, le, scaler = feature_engineering(flow_df)
    
    # 3. 数据集划分
    train_df, val_df, test_df = split_by_time(flow_df)
    
    # 4. 构建 48h 窗口序列
    window_size = 48
    log(f"\n构建 48h 窗口序列...")
    X_train, y_train = build_sequences(train_df, window_size)
    X_val, y_val = build_sequences(val_df, window_size)
    X_test, y_test = build_sequences(test_df, window_size)
    
    log(f"序列数据：训练{X_train.shape}, 验证{X_val.shape}, 测试{X_test.shape}")
    
    # 5. 模型训练
    log("\n" + "=" * 80)
    log("【模型训练】")
    log("=" * 80)
    
    improved_lstm = build_improved_lstm((window_size, X_train.shape[2]))
    improved_lstm, history = train_model(improved_lstm, X_train, y_train, 
                                         X_val, y_val, "改进LSTM (48h)")
    
    # 6. 模型评估
    final_results = evaluate_model(improved_lstm, X_test, y_test, "改进LSTM (48h)")
    
    # 7. 输出最终结果
    log("\n" + "=" * 80)
    log("【最终实验结果】")
    log("=" * 80)
    
    log(f"\n{'配置项':<25} {'值':<20}")
    log("-" * 45)
    log(f"{'滑动窗口':<25} 48h (最优配置)")
    log(f"{'训练轮次':<25} 100 (早停 patience=10)")
    log(f"{'Batch Size':<25} 32")
    log(f"{'特征维度':<25} {len(feature_cols)} 维")
    log(f"{'GPU 加速':<25} {'启用' if gpus else '未启用'}")
    log(f"{'实际训练轮次':<25} {len(history.history['loss'])}")
    
    log(f"\n{'模型':<25} {'MAE':<12} {'RMSE':<12} {'R²':<12}")
    log("-" * 61)
    log(f"{'改进LSTM (48h)':<25} {final_results[0]:<12.4f} {final_results[1]:<12.4f} {final_results[2]:<12.4f}")
    
    # 与上次实验对比
    log(f"\n【与上次实验对比】")
    log(f"上次 (24h 窗口): MAE=1.6995, RMSE=2.3689, R²=0.1228")
    log(f"本次 (48h 窗口): MAE={final_results[0]:.4f}, RMSE={final_results[1]:.4f}, R²={final_results[2]:.4f}")
    
    if final_results[2] > 0.1228:
        improvement = ((final_results[2] - 0.1228) / 0.1228) * 100
        log(f"✓ R²提升：{improvement:.2f}%")
    
    log("\n" + "=" * 80)
    log("✓ 实验完成！")
    log("=" * 80)
    log(f"结果已保存至：{log_file}")

if __name__ == "__main__":
    main()
