import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
import joblib

def parse_time_features(df):
    """
    解析时间特征
    将timestamp解析为weekday/hour/is_peak
    """
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['weekday'] = df['timestamp'].dt.weekday + 1  # 1=周一，7=周日
    df['hour'] = df['timestamp'].dt.hour
    df['is_peak'] = df['hour'].apply(lambda x: 1 if (8 <= x <= 9) or (17 <= x <= 18) else 0)
    return df

def clean_data(df):
    """
    数据清洗
    过滤极端异常值，保留有效样本
    """
    # 过滤极端异常值
    # 1. 过滤骑行量为0的极端天气情况
    # 2. 过滤异常高值（超过99%分位数的值）
    q99 = df['bike_count'].quantile(0.99)
    df = df[(df['bike_count'] > 0) & (df['bike_count'] < q99)]
    return df

def preprocess_data(file_path, seq_len=336):  # 默认14天=336小时
    """
    预处理数据
    1. 时间特征：将timestamp解析为weekday/hour/is_peak
    2. 空间特征：对经纬度做min-max归一化（缩放到[0,1]）
    3. 车辆数归一化：bike_count缩放到[0,1]
    4. 构造LSTM序列（用前seq_len个时间步预测下1步）
    5. 按时间顺序7:2:1拆分训练/验证/测试集（禁止随机打乱）
    """
    # 加载数据
    df = pd.read_csv(file_path)
    
    # 数据清洗
    df = clean_data(df)
    
    # 解析时间特征
    df = parse_time_features(df)
    
    # 归一化处理
    # 2.1 经纬度归一化
    lon_scaler = MinMaxScaler()
    lat_scaler = MinMaxScaler()
    df["lon_norm"] = lon_scaler.fit_transform(df[["longitude"]])
    df["lat_norm"] = lat_scaler.fit_transform(df[["latitude"]])
    
    # 2.2 车辆数归一化
    bike_scaler = MinMaxScaler()
    df["bike_count_norm"] = bike_scaler.fit_transform(df[["bike_count"]])
    
    # 2.3 停车点ID编码
    loc_encoder = LabelEncoder()
    df["location_id_encoded"] = loc_encoder.fit_transform(df["location_name"])
    loc_scaler = MinMaxScaler()
    df["location_id_norm"] = loc_scaler.fit_transform(df[["location_id_encoded"]])
    
    # 3. 按还车点+时间排序（保证序列连续性）
    df = df.sort_values(by=["location_name", "timestamp"]).reset_index(drop=True)
    
    # 4. 构造LSTM输入序列
    X, y = [], []
    for loc in df["location_name"].unique():
        loc_df = df[df["location_name"] == loc].sort_values(by="timestamp").reset_index(drop=True)
        if len(loc_df) > seq_len:
            for i in range(seq_len, len(loc_df)):
                # 输入特征：仅保留核心特征
                x_seq = loc_df.iloc[i-seq_len:i][["hour", "weekday", "location_id_norm", "bike_count_norm"]].values
                # 输出：当前步的bike_count_norm
                y_seq = loc_df.iloc[i]["bike_count_norm"]
                X.append(x_seq)
                y.append(y_seq)
    
    X = np.array(X)
    y = np.array(y).reshape(-1, 1)
    
    # 5. 数据划分（时间顺序）
    train_size = int(0.7 * len(X))
    val_size = int(0.2 * len(X))
    X_train, y_train = X[:train_size], y[:train_size]
    X_val, y_val = X[train_size:train_size+val_size], y[train_size:train_size+val_size]
    X_test, y_test = X[train_size+val_size:], y[train_size+val_size:]
    
    return (X_train, y_train, X_val, y_val, X_test, y_test), (bike_scaler, lon_scaler, lat_scaler, loc_scaler)

# 调用示例
if __name__ == "__main__":
    (X_train, y_train, X_val, y_val, X_test, y_test), scalers = preprocess_data("ysu_bike_data.csv", seq_len=6)
    print(f"训练集形状：X={X_train.shape}, y={y_train.shape}")
    print(f"验证集形状：X={X_val.shape}, y={y_val.shape}")
    print(f"测试集形状：X={X_test.shape}, y={y_test.shape}")
    
    # 保存结果
    np.save("./data/x_train.npy", X_train)
    np.save("./data/y_train.npy", y_train)
    np.save("./data/x_val.npy", X_val)
    np.save("./data/y_val.npy", y_val)
    np.save("./data/x_test.npy", X_test)
    np.save("./data/y_test.npy", y_test)
    
    joblib.dump(scalers[0], "./utils/scaler_bike.pkl")
    joblib.dump(scalers[1], "./utils/scaler_lon.pkl")
    joblib.dump(scalers[2], "./utils/scaler_lat.pkl")
    
    print("数据预处理完成，已保存到data目录")
