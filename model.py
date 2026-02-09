import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

def build_lstm_model(input_shape):
    """
    构建轻量级LSTM模型
    输入层：单层LSTM（64-128神经元）
    输出层：回归任务（激活函数linear）
    隐藏层：单个全连接层
    """
    model = Sequential()
    # 输入层：LSTM(128)，适配较长序列
    model.add(LSTM(128, return_sequences=False, input_shape=input_shape))
    model.add(Dropout(0.2))  # 正则化，防止过拟合
    # 全连接层
    model.add(Dense(32, activation="relu"))
    # 输出层：回归任务，预测车辆数（归一化后）
    model.add(Dense(1, activation="linear"))
    
    # 编译模型
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model

# 调用示例
if __name__ == "__main__":
    # 14天=336小时，4个特征
    model = build_lstm_model((336, 4))
    model.summary()
