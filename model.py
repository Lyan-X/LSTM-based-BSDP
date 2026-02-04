import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

def build_lstm_model(input_shape):
    """
    构建LSTM模型
    输入层：新增空间特征维度（经纬度 2 维 + 时间特征 3 维 + 历史车辆数 1 维）
    输出层：保持回归任务（激活函数linear）
    隐藏层：样本量小，减小 LSTM 单元数（从 128→64）
    """
    model = Sequential()
    # 输入层：LSTM(64)，适配小样本（减少过拟合）
    model.add(LSTM(64, return_sequences=False, input_shape=input_shape))
    model.add(Dropout(0.2))  # 正则化，防止过拟合
    # 全连接层
    model.add(Dense(32, activation="relu"))
    # 输出层：回归任务，预测车辆数（归一化后）
    model.add(Dense(1, activation="linear"))
    
    # 编译模型
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model

# 调用示例（input_shape=(seq_len, 特征数)= (6,6)）
if __name__ == "__main__":
    model = build_lstm_model((6, 6))
    model.summary()
