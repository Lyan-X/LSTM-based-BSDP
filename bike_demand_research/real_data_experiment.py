"""
BSDP项目 - 基于真实Capital Bikeshare数据集的共享单车需求预测实验
使用本地真实数据集：daily_rent_detail.csv 和 weather.csv
实验时间范围：2022年1月1日 - 2023年12月31日
"""

import os
import sys
import numpy as np
import pandas as pd
import tensorflow as tf
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

# 设置日志
log_file = "experiment_log.txt"
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

# 设置随机种子确保可复现
np.random.seed(42)
tf.random.set_seed(42)

# 数据路径
DATASET_DIR = r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\BSDP\bike_demand_research\dataset"
RIDE_DATA_PATH = os.path.join(DATASET_DIR, "daily_rent_detail.csv")
WEATHER_DATA_PATH = os.path.join(DATASET_DIR, "weather.csv")
STATION_DATA_PATH = os.path.join(DATASET_DIR, "station_list.csv")

def load_real_data():
    """读取本地真实数据集"""
    log("=" * 60)
    log("【真实数据读取报告】")
    log("=" * 60)
    
    # 读取骑行订单数据
    log(f"读取骑行订单数据: {RIDE_DATA_PATH}")
    ride_df = pd.read_csv(RIDE_DATA_PATH)
    log(f"原始骑行数据量: {len(ride_df):,} 条记录")
    log(f"数据时间范围: {ride_df['started_at'].min()} 至 {ride_df['started_at'].max()}")
    log(f"包含停车点数量: {ride_df['start_station_id'].nunique()} 个")
    
    # 读取气象数据
    log(f"\n读取气象数据: {WEATHER_DATA_PATH}")
    weather_df = pd.read_csv(WEATHER_DATA_PATH)
    log(f"气象数据量: {len(weather_df):,} 条记录")
    log(f"气象数据时间范围: {weather_df['datetime'].min()} 至 {weather_df['datetime'].max()}")
    
    # 读取停车点信息
    log(f"\n读取停车点信息: {STATION_DATA_PATH}")
    station_df = pd.read_csv(STATION_DATA_PATH)
    log(f"停车点总数: {len(station_df)} 个")
    
    return ride_df, weather_df, station_df

def preprocess_real_data(ride_df, weather_df, station_df):
    """预处理真实数据"""
    log("\n" + "=" * 60)
    log("【数据预处理报告】")
    log("=" * 60)
    
    # 转换时间格式（使用format='mixed'处理不同格式的时间戳）
    ride_df['started_at'] = pd.to_datetime(ride_df['started_at'], format='mixed')
    ride_df['ended_at'] = pd.to_datetime(ride_df['ended_at'], format='mixed')
    weather_df['datetime'] = pd.to_datetime(weather_df['datetime'])
    
    # 筛选2022-2023年数据
    start_date = pd.Timestamp('2022-01-01')
    end_date = pd.Timestamp('2023-12-31 23:59:59')
    
    ride_df = ride_df[(ride_df['started_at'] >= start_date) & (ride_df['started_at'] <= end_date)]
    weather_df = weather_df[(weather_df['datetime'] >= start_date) & (weather_df['datetime'] <= end_date)]
    
    log(f"筛选后骑行数据量: {len(ride_df):,} 条记录 (2022-2023年)")
    log(f"筛选后气象数据量: {len(weather_df):,} 条记录")
    
    # 按小时粒度聚合借车量 D_t
    log("\n【目标数据聚合】")
    ride_df['start_hour'] = ride_df['started_at'].dt.floor('h')
    ride_df['end_hour'] = ride_df['ended_at'].dt.floor('h')
    
    # 借车量 D_t
    D_t = ride_df.groupby(['start_station_id', 'start_hour']).size().reset_index(name='D_t')
    D_t.rename(columns={'start_station_id': 'station_id', 'start_hour': 'hour'}, inplace=True)
    log(f"借车量聚合: {len(D_t):,} 条station-hour记录")
    
    # 还车量 R_t
    R_t = ride_df.groupby(['end_station_id', 'end_hour']).size().reset_index(name='R_t')
    R_t.rename(columns={'end_station_id': 'station_id', 'end_hour': 'hour'}, inplace=True)
    log(f"还车量聚合: {len(R_t):,} 条station-hour记录")
    
    # 合并借车和还车数据
    flow_df = pd.merge(D_t, R_t, on=['station_id', 'hour'], how='outer')
    flow_df['D_t'] = flow_df['D_t'].fillna(0)
    flow_df['R_t'] = flow_df['R_t'].fillna(0)
    
    # 计算净流量 F_t = R_t - D_t
    flow_df['F_t'] = flow_df['R_t'] - flow_df['D_t']
    log(f"净流量计算完成: 均值={flow_df['F_t'].mean():.2f}, 标准差={flow_df['F_t'].std():.2f}")
    
    # 计算累计停车辆 S_t
    flow_df = flow_df.sort_values(['station_id', 'hour'])
    flow_df['S_t'] = flow_df.groupby('station_id')['F_t'].cumsum()
    log(f"累计停车辆计算完成: 均值={flow_df['S_t'].mean():.2f}")
    
    # 异常值处理
    log("\n【异常值处理】")
    q99 = flow_df['S_t'].quantile(0.99)
    log(f"99分位数截断值: {q99:.2f}")
    
    # 剔除停车量为负的异常值
    negative_count = len(flow_df[flow_df['S_t'] < 0])
    flow_df = flow_df[flow_df['S_t'] >= 0]
    log(f"剔除负停车辆记录: {negative_count:,} 条")
    
    # 剔除超出容量的极端值
    capacity = q99
    extreme_count = len(flow_df[abs(flow_df['F_t']) > 0.8 * capacity])
    flow_df = flow_df[abs(flow_df['F_t']) <= 0.8 * capacity]
    log(f"剔除极端净流量记录: {extreme_count:,} 条")
    
    log(f"预处理后有效样本数: {len(flow_df):,} 条")
    log(f"有效停车点数量: {flow_df['station_id'].nunique()} 个")
    
    # 合并气象数据
    log("\n【气象数据合并】")
    weather_df['date'] = weather_df['datetime'].dt.date
    flow_df['date'] = flow_df['hour'].dt.date
    
    # 选择关键气象特征
    weather_features = ['date', 'temp', 'humidity', 'windspeed', 'precip']
    weather_subset = weather_df[weather_features].copy()
    weather_subset['precip'] = (weather_subset['precip'] > 0).astype(int)  # 是否降雨
    weather_subset.rename(columns={'precip': 'is_rain'}, inplace=True)
    
    flow_df = pd.merge(flow_df, weather_subset, on='date', how='left')
    
    # 缺失值处理：线性插值
    missing_before = flow_df[['temp', 'humidity', 'windspeed']].isnull().sum().sum()
    flow_df[['temp', 'humidity', 'windspeed']] = flow_df[['temp', 'humidity', 'windspeed']].interpolate()
    flow_df['is_rain'] = flow_df['is_rain'].fillna(0)
    log(f"气象数据缺失值插值完成: 处理 {missing_before} 个缺失值")
    
    return flow_df

def feature_engineering(flow_df):
    """特征工程"""
    log("\n" + "=" * 60)
    log("【特征工程】")
    log("=" * 60)
    
    # 时间特征
    flow_df['hour_of_day'] = flow_df['hour'].dt.hour.astype(int)
    flow_df['day_of_week'] = flow_df['hour'].dt.weekday.astype(int)
    flow_df['is_weekday'] = (flow_df['day_of_week'] < 5).astype(int)
    flow_df['is_peak_hour'] = (((flow_df['hour_of_day'] >= 7) & (flow_df['hour_of_day'] <= 9)) | 
                               ((flow_df['hour_of_day'] >= 17) & (flow_df['hour_of_day'] <= 19))).astype(int)
    
    log("时间特征构建完成: hour_of_day, day_of_week, is_weekday, is_peak_hour")
    
    # 历史时序特征
    log("构建历史时序特征...")
    flow_df = flow_df.sort_values(['station_id', 'hour'])
    
    # 前24小时净流量的统计特征
    flow_df['F_t_mean_24h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.rolling(window=24, min_periods=1).mean())
    flow_df['F_t_max_24h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.rolling(window=24, min_periods=1).max())
    flow_df['F_t_std_24h'] = flow_df.groupby('station_id')['F_t'].transform(
        lambda x: x.rolling(window=24, min_periods=1).std()).fillna(0)
    
    # 前1天同时段净流量
    flow_df['F_t_lag_24h'] = flow_df.groupby('station_id')['F_t'].shift(24).fillna(0)
    
    log("历史时序特征构建完成: F_t_mean_24h, F_t_max_24h, F_t_std_24h, F_t_lag_24h")
    
    # 位置特征编码
    le = LabelEncoder()
    flow_df['station_id_encoded'] = le.fit_transform(flow_df['station_id'].astype(str))
    log(f"停车点ID编码完成: {len(le.classes_)} 个停车点")
    
    # 选择特征列
    feature_cols = [
        'station_id_encoded', 'hour_of_day', 'day_of_week', 'is_weekday', 'is_peak_hour',
        'F_t_mean_24h', 'F_t_max_24h', 'F_t_std_24h', 'F_t_lag_24h',
        'temp', 'humidity', 'windspeed', 'is_rain'
    ]
    
    # 特征归一化
    scaler = MinMaxScaler()
    flow_df[feature_cols] = scaler.fit_transform(flow_df[feature_cols])
    log(f"特征归一化完成: 共 {len(feature_cols)} 个特征")
    log(f"特征列表: {', '.join(feature_cols)}")
    
    return flow_df, feature_cols, le, scaler

def build_sequences(df, window_size=24):
    """构建序列数据"""
    X, y = [], []
    
    feature_cols = [
        'station_id_encoded', 'hour_of_day', 'day_of_week', 'is_weekday', 'is_peak_hour',
        'F_t_mean_24h', 'F_t_max_24h', 'F_t_std_24h', 'F_t_lag_24h',
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
    """按时间顺序划分数据集"""
    log("\n【数据集划分】")
    
    # 时间划分点
    train_end = pd.Timestamp('2023-06-30 23:59:59')
    val_end = pd.Timestamp('2023-09-30 23:59:59')
    
    train_df = df[df['hour'] <= train_end]
    val_df = df[(df['hour'] > train_end) & (df['hour'] <= val_end)]
    test_df = df[df['hour'] > val_end]
    
    log(f"训练集: {len(train_df):,} 条 ({train_df['hour'].min()} 至 {train_df['hour'].max()})")
    log(f"验证集: {len(val_df):,} 条 ({val_df['hour'].min()} 至 {val_df['hour'].max()})")
    log(f"测试集: {len(test_df):,} 条 ({test_df['hour'].min()} 至 {test_df['hour'].max()})")
    
    return train_df, val_df, test_df

def build_bp(input_shape):
    """构建BP神经网络"""
    model = tf.keras.Sequential([
        tf.keras.layers.Flatten(input_shape=input_shape),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1)
    ])
    
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(learning_rate=1e-3),
        loss='mse',
        metrics=['mae']
    )
    return model

def build_basic_lstm(input_shape):
    """构建基础LSTM"""
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(64, input_shape=input_shape, dropout=0.2),
        tf.keras.layers.Dense(1)
    ])
    
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(learning_rate=1e-3),
        loss='mse',
        metrics=['mae']
    )
    return model

def build_improved_lstm(input_shape):
    """构建改进LSTM"""
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(64, return_sequences=True, input_shape=input_shape, dropout=0.2),
        tf.keras.layers.LSTM(32, dropout=0.2),
        tf.keras.layers.Dense(1)
    ])
    
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(learning_rate=1e-3, weight_decay=1e-4),
        loss='mse',
        metrics=['mae']
    )
    return model

def train_model(model, X_train, y_train, X_val, y_val, model_name, epochs=50, batch_size=32):
    """训练模型"""
    log(f"\n训练 {model_name}...")
    
    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=5,
        restore_best_weights=True
    )
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stopping],
        verbose=1
    )
    
    return model, history

def evaluate_model(model, X_test, y_test, model_name):
    """评估模型"""
    log(f"\n评估 {model_name}...")
    
    y_pred = model.predict(X_test, verbose=0).flatten()
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    log(f"{model_name} - MAE: {mae:.4f}, RMSE: {rmse:.4f}, R²: {r2:.4f}")
    
    return mae, rmse, r2

def ablation_experiment(train_df, val_df, test_df, window_sizes=[12, 24, 48, 72]):
    """滚动窗口消融实验"""
    log("\n" + "=" * 60)
    log("【滚动窗口消融实验】")
    log("=" * 60)
    
    results = {}
    
    for window_size in window_sizes:
        log(f"\n窗口大小: {window_size}h")
        
        X_train, y_train = build_sequences(train_df, window_size)
        X_val, y_val = build_sequences(val_df, window_size)
        X_test, y_test = build_sequences(test_df, window_size)
        
        if len(X_train) == 0 or len(X_test) == 0:
            log(f"数据不足，跳过窗口 {window_size}h")
            continue
        
        model = build_improved_lstm((window_size, X_train.shape[2]))
        model, _ = train_model(model, X_train, y_train, X_val, y_val, 
                              f"改进LSTM-{window_size}h", epochs=20)
        mae, rmse, r2 = evaluate_model(model, X_test, y_test, f"改进LSTM-{window_size}h")
        
        results[window_size] = {'mae': mae, 'rmse': rmse, 'r2': r2}
    
    return results

def main():
    log("\n" + "=" * 80)
    log("BSDP项目 - 基于真实Capital Bikeshare数据集的实验")
    log("=" * 80)
    
    # 1. 读取真实数据
    ride_df, weather_df, station_df = load_real_data()
    
    # 2. 预处理数据
    flow_df = preprocess_real_data(ride_df, weather_df, station_df)
    
    # 3. 特征工程
    flow_df, feature_cols, le, scaler = feature_engineering(flow_df)
    
    # 4. 划分数据集
    train_df, val_df, test_df = split_by_time(flow_df)
    
    # 5. 构建24小时窗口的序列数据
    window_size = 24
    log(f"\n构建 {window_size}h 窗口序列数据...")
    X_train, y_train = build_sequences(train_df, window_size)
    X_val, y_val = build_sequences(val_df, window_size)
    X_test, y_test = build_sequences(test_df, window_size)
    
    log(f"序列数据形状 - 训练: {X_train.shape}, 验证: {X_val.shape}, 测试: {X_test.shape}")
    
    # 6. 训练和评估三个模型
    log("\n" + "=" * 60)
    log("【核心对照实验】")
    log("=" * 60)
    
    # BP神经网络
    bp_model = build_bp((window_size, X_train.shape[2]))
    bp_model, _ = train_model(bp_model, X_train, y_train, X_val, y_val, "BP神经网络")
    bp_results = evaluate_model(bp_model, X_test, y_test, "BP神经网络")
    
    # 基础LSTM
    basic_lstm_model = build_basic_lstm((window_size, X_train.shape[2]))
    basic_lstm_model, _ = train_model(basic_lstm_model, X_train, y_train, X_val, y_val, "基础LSTM")
    basic_lstm_results = evaluate_model(basic_lstm_model, X_test, y_test, "基础LSTM")
    
    # 改进LSTM
    improved_lstm_model = build_improved_lstm((window_size, X_train.shape[2]))
    improved_lstm_model, _ = train_model(improved_lstm_model, X_train, y_train, X_val, y_val, "改进LSTM")
    improved_lstm_results = evaluate_model(improved_lstm_model, X_test, y_test, "改进LSTM")
    
    # 7. 滚动窗口消融实验
    ablation_results = ablation_experiment(train_df, val_df, test_df)
    
    # 8. 输出结果
    log("\n" + "=" * 80)
    log("【实验结果汇总】")
    log("=" * 80)
    
    log("\n核心对照实验结果表:")
    log(f"{'模型':<20} {'MAE':<12} {'RMSE':<12} {'R²':<12}")
    log("-" * 56)
    log(f"{'BP神经网络':<20} {bp_results[0]:<12.4f} {bp_results[1]:<12.4f} {bp_results[2]:<12.4f}")
    log(f"{'基础LSTM':<20} {basic_lstm_results[0]:<12.4f} {basic_lstm_results[1]:<12.4f} {basic_lstm_results[2]:<12.4f}")
    log(f"{'改进LSTM':<20} {improved_lstm_results[0]:<12.4f} {improved_lstm_results[1]:<12.4f} {improved_lstm_results[2]:<12.4f}")
    
    log("\n滚动窗口消融实验结果表:")
    log(f"{'窗口大小':<12} {'MAE':<12} {'RMSE':<12} {'R²':<12}")
    log("-" * 48)
    for window_size, metrics in sorted(ablation_results.items()):
        log(f"{f'{window_size}h':<12} {metrics['mae']:<12.4f} {metrics['rmse']:<12.4f} {metrics['r2']:<12.4f}")
    
    log("\n" + "=" * 80)
    log("实验完成！")
    log("=" * 80)

if __name__ == "__main__":
    main()
