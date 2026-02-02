import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import joblib
import os
import json
import time
import logging
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

# ===================== 配置日志 =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('train_lstm.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# ===================== 屏蔽冗余警告 =====================
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import warnings
warnings.filterwarnings('ignore')
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

# ===================== 配置参数 =====================
class Config:
    def __init__(self):
        # Data Configuration
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(current_dir, '../data')
        self.results_dir = os.path.join(current_dir, '../results')
        self.models_dir = current_dir
        
        # Model Configuration
        self.input_shape = (24, 11)  # Time steps, features
        self.lstm_units = [128, 64]  # LSTM layer units
        self.dropout_rate = 0.3  # Dropout rate
        self.dense_units = [32, 16]  # Dense layer units
        
        # Training Configuration
        self.batch_size = 64
        self.epochs = 100  # Increased epochs for better performance
        self.learning_rate = 0.0005  # Lower learning rate for better convergence
        self.patience = 10  # Early stopping patience
        self.k_folds = 5  # Cross validation folds
        
        # Save Configuration
        self.model_name = 'bike_lstm_model_optimized.h5'
        self.history_plot = 'lstm_training_loss_optimized.png'
        self.prediction_plot = 'lstm_prediction_result_optimized.png'

# ===================== 数据加载与预处理 =====================
def load_data(config):
    try:
        logger.info("Starting to load data...")
        x_train = np.load(os.path.join(config.data_dir, 'x_train.npy'))
        y_train = np.load(os.path.join(config.data_dir, 'y_train.npy'))
        x_val = np.load(os.path.join(config.data_dir, 'x_val.npy'))
        y_val = np.load(os.path.join(config.data_dir, 'y_val.npy'))
        
        logger.info(f"Data loading completed:")
        logger.info(f"Training data shape: x={x_train.shape}, y={y_train.shape}")
        logger.info(f"Validation data shape: x={x_val.shape}, y={y_val.shape}")
        
        return x_train, y_train, x_val, y_val
    except Exception as e:
        logger.error(f"Data loading failed: {e}")
        raise

# ===================== Build Optimized LSTM Model =====================
def build_model(config):
    try:
        logger.info("Starting to build LSTM model...")
        
        # Build model using functional API
        inputs = tf.keras.Input(shape=config.input_shape)
        
        # First LSTM layer
        x = tf.keras.layers.LSTM(
            config.lstm_units[0], 
            return_sequences=True,
            kernel_regularizer=tf.keras.regularizers.l2(0.001)
        )(inputs)
        x = tf.keras.layers.Dropout(config.dropout_rate)(x)
        
        # Second LSTM layer
        x = tf.keras.layers.LSTM(
            config.lstm_units[1], 
            return_sequences=False,
            kernel_regularizer=tf.keras.regularizers.l2(0.001)
        )(x)
        x = tf.keras.layers.Dropout(config.dropout_rate)(x)
        
        # Attention mechanism (optional)
        attention = tf.keras.layers.Dense(1, activation='tanh')(x)
        attention = tf.keras.layers.Flatten()(attention)
        attention = tf.keras.layers.Activation('softmax')(attention)
        attention = tf.keras.layers.RepeatVector(config.lstm_units[1])(attention)
        attention = tf.keras.layers.Permute([2, 1])(attention)
        x = tf.keras.layers.multiply([x, attention])
        x = tf.keras.layers.Lambda(lambda x: tf.reduce_sum(x, axis=1))(x)
        
        # Dense layers
        for units in config.dense_units:
            x = tf.keras.layers.Dense(
                units,
                activation="relu",
                kernel_regularizer=tf.keras.regularizers.l2(0.001)
            )(x)
            x = tf.keras.layers.Dropout(config.dropout_rate)(x)
        
        # Output layer
        outputs = tf.keras.layers.Dense(1)(x)
        
        # Build model
        model = tf.keras.Model(inputs=inputs, outputs=outputs)
        
        # Compile model
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=tf.keras.optimizers.schedules.ExponentialDecay(
                initial_learning_rate=config.learning_rate,
                decay_steps=10000,
                decay_rate=0.9
            )
        )
        
        model.compile(
            optimizer=optimizer,
            loss="mean_squared_error",
            metrics=["mae", "mse"]
        )
        
        logger.info("Model building completed")
        model.summary()
        
        return model
    except Exception as e:
        logger.error(f"Model building failed: {e}")
        raise

# ===================== Train Model =====================
def train_model(model, x_train, y_train, x_val, y_val, config):
    try:
        logger.info("Starting to train model...")
        
        # Early stopping
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=config.patience,
            restore_best_weights=True
        )
        
        # Model checkpoint
        checkpoint = tf.keras.callbacks.ModelCheckpoint(
            os.path.join(config.models_dir, config.model_name),
            monitor="val_loss",
            save_best_only=True,
            save_weights_only=False
        )
        
        # Training
        history = model.fit(
            x_train, y_train,
            batch_size=config.batch_size,
            epochs=config.epochs,
            validation_data=(x_val, y_val),
            callbacks=[early_stop, checkpoint],
            verbose=1
        )
        
        logger.info("Model training completed")
        return history
    except Exception as e:
        logger.error(f"Model training failed: {e}")
        raise

# ===================== Evaluate Model =====================
def evaluate_model(model, x_val, y_val, config):
    try:
        logger.info("Starting to evaluate model...")
        
        # Load scaler
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        scaler_y = joblib.load(os.path.join(current_dir, '../utils', 'scaler_y.pkl'))
        
        # Predict
        y_pred_scaled = model.predict(x_val)
        y_pred = scaler_y.inverse_transform(y_pred_scaled)
        y_true = scaler_y.inverse_transform(y_val.reshape(-1, 1))
        
        # Calculate evaluation metrics
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        
        logger.info(f"Model evaluation results：")
        logger.info(f"Mean Absolute Error (MAE): {mae:.2f}")
        logger.info(f"Root Mean Squared Error (RMSE): {rmse:.2f}")
        logger.info(f"R² Score: {r2:.4f}")
        
        return y_true, y_pred, mae, rmse, r2
    except Exception as e:
        logger.error(f"Model evaluation failed: {e}")
        raise

# ===================== Visualize Results =====================
def visualize_results(history, y_true, y_pred, config):
    try:
        logger.info("Starting to visualize results...")
        
        # Training history visualization
        plt.figure(figsize=(14, 6))
        plt.subplot(1, 2, 1)
        plt.plot(history.history['loss'], label='Training Loss', color='darkorange', linewidth=1.5)
        plt.plot(history.history['val_loss'], label='Validation Loss', color='forestgreen', linewidth=1.5)
        plt.title('LSTM Model Training Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Mean Squared Error (MSE)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.subplot(1, 2, 2)
        plt.plot(history.history['mae'], label='Training MAE', color='darkorange', linewidth=1.5)
        plt.plot(history.history['val_mae'], label='Validation MAE', color='forestgreen', linewidth=1.5)
        plt.title('LSTM Model Training MAE')
        plt.xlabel('Epoch')
        plt.ylabel('Mean Absolute Error (MAE)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # 使用绝对路径保存图片
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(current_dir, '../results')
        
        plt.tight_layout()
        history_plot_path = os.path.join(results_dir, config.history_plot)
        plt.savefig(history_plot_path, dpi=300)
        plt.close()
        logger.info(f"Training history visualization saved to: {history_plot_path}")
        
        # Prediction results visualization
        plt.figure(figsize=(14, 6))
        plt.plot(y_true[:150], label="Actual Rides", color="blue", linewidth=1.5)
        plt.plot(y_pred[:150], label="Predicted Rides", color="red", alpha=0.7, linewidth=1.5)
        plt.title("Optimized LSTM Model Prediction Results (First 150 Hours)")
        plt.xlabel("Time (Hours)")
        plt.ylabel("Number of Rides")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Add statistical information
        mae = mean_absolute_error(y_true[:150], y_pred[:150])
        rmse = np.sqrt(mean_squared_error(y_true[:150], y_pred[:150]))
        plt.text(0.05, 0.95, f'MAE: {mae:.2f} rides\nRMSE: {rmse:.2f} rides', 
                 transform=plt.gca().transAxes, 
                 bbox=dict(facecolor='white', alpha=0.8))
        
        prediction_plot_path = os.path.join(results_dir, config.prediction_plot)
        plt.savefig(prediction_plot_path, dpi=300)
        plt.close()
        logger.info(f"Prediction results visualization saved to: {config.prediction_plot}")
        
    except Exception as e:
        logger.error(f"Visualization failed: {e}")
        raise

# ===================== Cross Validation =====================
def cross_validate(config, x_train, y_train):
    try:
        logger.info(f"Starting {config.k_folds}-fold cross validation...")
        
        kf = KFold(n_splits=config.k_folds, shuffle=True, random_state=42)
        fold_scores = []
        
        for fold, (train_idx, val_idx) in enumerate(kf.split(x_train)):
            logger.info(f"Fold {fold+1} validation started...")
            
            # Split data
            fold_x_train, fold_x_val = x_train[train_idx], x_train[val_idx]
            fold_y_train, fold_y_val = y_train[train_idx], y_train[val_idx]
            
            # Build model
            model = build_model(config)
            
            # Train model
            history = model.fit(
                fold_x_train, fold_y_train,
                batch_size=config.batch_size,
                epochs=config.epochs,
                validation_data=(fold_x_val, fold_y_val),
                callbacks=[tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    patience=config.patience,
                    restore_best_weights=True
                )],
                verbose=0
            )
            
            # Evaluate model
            val_loss = history.history['val_loss'][-1]
            val_mae = history.history['val_mae'][-1]
            fold_scores.append({'loss': val_loss, 'mae': val_mae})
            
            logger.info(f"Fold {fold+1} validation completed: loss={val_loss:.4f}, mae={val_mae:.4f}")
        
        # Calculate average scores
        avg_loss = np.mean([score['loss'] for score in fold_scores])
        avg_mae = np.mean([score['mae'] for score in fold_scores])
        
        logger.info(f"Cross validation completed：")
        logger.info(f"Average validation loss: {avg_loss:.4f}")
        logger.info(f"Average validation MAE: {avg_mae:.4f}")
        
        return fold_scores
    except Exception as e:
        logger.error(f"Cross validation failed: {e}")
        raise

# ===================== Save Model Configuration =====================
def save_config(config, scores):
    try:
        config_dict = {
            'model_config': {
                'lstm_units': config.lstm_units,
                'dropout_rate': config.dropout_rate,
                'dense_units': config.dense_units
            },
            'training_config': {
                'batch_size': config.batch_size,
                'epochs': config.epochs,
                'learning_rate': config.learning_rate,
                'patience': config.patience
            },
            'evaluation_scores': scores
        }
        
        with open(os.path.join(config.models_dir, 'lstm_model_config.json'), 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        
        logger.info("Model configuration saved successfully")
    except Exception as e:
        logger.error(f"Configuration saving failed: {e}")

# ===================== 主函数 =====================
def main():
    try:
        start_time = time.time()
        logger.info("=====================================")
        logger.info("开始优化LSTM模型训练")
        logger.info("=====================================")
        
        # 初始化配置
        config = Config()
        
        # 创建目录
        os.makedirs(config.results_dir, exist_ok=True)
        
        # 加载数据
        x_train, y_train, x_val, y_val = load_data(config)
        
        # 交叉验证
        cross_validate(config, x_train, y_train)
        
        # 构建模型
        model = build_model(config)
        
        # 训练模型
        history = train_model(model, x_train, y_train, x_val, y_val, config)
        
        # 评估模型
        y_true, y_pred, mae, rmse, r2 = evaluate_model(model, x_val, y_val, config)
        
        # 可视化结果
        visualize_results(history, y_true, y_pred, config)
        
        # 保存配置
        save_config(config, {
            'mae': mae,
            'rmse': rmse,
            'r2': r2
        })
        
        end_time = time.time()
        logger.info(f"=====================================")
        logger.info(f"LSTM模型优化训练完成！")
        logger.info(f"总耗时: {end_time - start_time:.2f}秒")
        logger.info(f"模型保存到: {config.model_name}")
        logger.info(f"=====================================")
        
    except Exception as e:
        logger.error(f"训练过程出错: {e}")
        raise

if __name__ == "__main__":
    main()