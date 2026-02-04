import numpy as np
import matplotlib.pyplot as plt
import joblib
import pandas as pd
from model import build_lstm_model

# matplotlib中文配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def load_model_and_predict():
    """
    加载模型和数据，生成预测结果
    """
    # 加载数据
    (X_train, y_train, X_val, y_val, X_test, y_test), scalers = pd.read_pickle('./data/preprocessed_data.pkl') if False else load_preprocessed_data()
    
    # 加载模型
    model = build_lstm_model((6, 6))
    model.load_weights('results/ysu_lstm_bsdp_model.h5')
    
    # 预测
    y_pred = model.predict(X_test)
    
    # 反归一化
    bike_scaler = scalers[0]
    y_test_original = bike_scaler.inverse_transform(y_test)
    y_pred_original = bike_scaler.inverse_transform(y_pred)
    
    return y_test_original, y_pred_original

def load_preprocessed_data():
    """
    加载预处理后的数据
    """
    from preprocess import preprocess_data
    return preprocess_data('ysu_bike_data.csv', seq_len=6)

def plot_time_series(y_test_original, y_pred_original, loc_name="还车点"):
    """
    时间序列可视化（单还车点）
    """
    # 取前50个样本可视化
    plt.figure(figsize=(12, 6))
    plt.plot(y_test_original[:50], label="真实车辆数", color="blue")
    plt.plot(y_pred_original[:50], label="预测车辆数", color="red", linestyle="--")
    plt.title(f"{loc_name} 车辆数预测结果")
    plt.xlabel("时间步")
    plt.ylabel("车辆数")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"results/{loc_name}_pred_result.png")
    plt.close()  # 关闭图形，避免内存占用

def plot_residuals(y_test_original, y_pred_original):
    """
    绘制残差图
    """
    residuals = y_test_original - y_pred_original
    plt.figure(figsize=(12, 6))
    plt.scatter(range(len(residuals)), residuals, alpha=0.5)
    plt.axhline(y=0, color='r', linestyle='--')
    plt.title('预测残差图')
    plt.xlabel('样本索引')
    plt.ylabel('残差（真实值 - 预测值）')
    plt.grid(True)
    plt.savefig('results/residuals.png')
    plt.close()  # 关闭图形，避免内存占用

def calculate_metrics(y_test_original, y_pred_original):
    """
    计算评估指标
    """
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    
    mae = mean_absolute_error(y_test_original, y_pred_original)
    mse = mean_squared_error(y_test_original, y_pred_original)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test_original, y_pred_original)
    
    print("\n模型评估指标：")
    print(f"MAE: {mae:.4f}")
    print(f"MSE: {mse:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R²: {r2:.4f}")
    
    return mae, mse, rmse, r2

def load_model_and_predict_by_location():
    """
    按还车点加载模型和预测
    """
    # 加载数据
    from preprocess import preprocess_data
    (X_train, y_train, X_val, y_val, X_test, y_test), scalers = preprocess_data('ysu_bike_data.csv', seq_len=6)
    
    # 加载模型
    model = build_lstm_model((6, 6))
    model.load_weights('ysu_lstm_bsdp_model.h5')
    
    # 加载原始数据获取还车点信息
    df = pd.read_csv('ysu_bike_data.csv')
    locations = df['location_name'].unique()
    
    # 预测
    y_pred = model.predict(X_test)
    
    # 反归一化
    bike_scaler = scalers[0]
    y_test_original = bike_scaler.inverse_transform(y_test)
    y_pred_original = bike_scaler.inverse_transform(y_pred)
    
    return y_test_original, y_pred_original, locations

def main():
    """
    主函数
    """
    # 加载模型和预测
    y_test_original, y_pred_original, locations = load_model_and_predict_by_location()
    
    # 计算评估指标
    calculate_metrics(y_test_original, y_pred_original)
    
    # 生成可视化结果
    # 遍历所有还车点批量预测
    for i, loc_name in enumerate(locations[:10]):  # 取前10个还车点作为示例
        # 为每个还车点生成预测图
        plot_time_series(y_test_original, y_pred_original, loc_name=loc_name)
    
    plot_residuals(y_test_original, y_pred_original)
    
    print("\n可视化结果已生成到 results 文件夹：")
    print("- 所有还车点的预测结果图")
    print("- results/residuals.png: 预测残差图")

if __name__ == "__main__":
    main()
