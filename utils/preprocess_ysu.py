import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import joblib

def preprocess_data(file_path, seq_len=6):
    # 1. 加载数据
    df = pd.read_csv(file_path)
    
    # 2. 归一化处理
    # 2.1 经纬度归一化
    lon_scaler = MinMaxScaler()
    lat_scaler = MinMaxScaler()
    df["lon_norm"] = lon_scaler.fit_transform(df[["longitude"]])
    df["lat_norm"] = lat_scaler.fit_transform(df[["latitude"]])
    
    # 2.2 车辆数归一化
    bike_scaler = MinMaxScaler()
    df["bike_count_norm"] = bike_scaler.fit_transform(df[["bike_count"]])
    
    # 3. 按还车点+时间排序（保证序列连续性）
    df = df.sort_values(by=["location_name", "timestamp"]).reset_index(drop=True)
    
    # 4. 构造LSTM输入序列
    X, y = [], []
    for loc in df["location_name"].unique():
        loc_df = df[df["location_name"] == loc].reset_index(drop=True)
        for i in range(seq_len, len(loc_df)):
            # 输入特征：前6步的[lon_norm, lat_norm, weekday, hour, is_peak, bike_count_norm]
            x_seq = loc_df.iloc[i-seq_len:i][["lon_norm", "lat_norm", "weekday", "hour", "is_peak", "bike_count_norm"]].values
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
    
    return (X_train, y_train, X_val, y_val, X_test, y_test), (bike_scaler, lon_scaler, lat_scaler)

# 调用示例
if __name__ == "__main__":
    (X_train, y_train, X_val, y_val, X_test, y_test), scalers = preprocess_data("ysu_bike_data.csv", seq_len=6)
    print(f"训练集形状：X={X_train.shape}, y={y_train.shape}")
    print(f"验证集形状：X={X_val.shape}, y={y_val.shape}")
    print(f"测试集形状：X={X_test.shape}, y={y_test.shape}")
    
    # 保存结果
    np.save("./data/x_train_ysu.npy", X_train)
    np.save("./data/y_train_ysu.npy", y_train)
    np.save("./data/x_val_ysu.npy", X_val)
    np.save("./data/y_val_ysu.npy", y_val)
    np.save("./data/x_test_ysu.npy", X_test)
    np.save("./data/y_test_ysu.npy", y_test)
    
    joblib.dump(scalers[0], "./utils/scaler_bike_ysu.pkl")
    joblib.dump(scalers[1], "./utils/scaler_lon_ysu.pkl")
    joblib.dump(scalers[2], "./utils/scaler_lat_ysu.pkl")
    
    print("数据预处理完成，已保存到data目录")
