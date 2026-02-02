"""
模型管理服务
负责模型的加载、缓存、版本管理和预测
"""

import os
import time
import tensorflow as tf
import joblib
import numpy as np
from django.conf import settings
from django.utils import timezone
from demand_prediction.models import PredictionResult
from system_support.models import SystemLog

class ModelService:
    """模型管理服务"""
    
    def __init__(self):
        self.base_dir = settings.BASE_DIR
        self.models = {}
        self.scalers = {}
        self.model_info = {}
        self.load_times = {}
        self.initialize()
    
    def initialize(self):
        """初始化模型服务"""
        print("初始化模型服务...")
        self.load_models()
    
    def get_model_path(self, model_name):
        """获取模型路径"""
        # 项目根目录（向上一级）
        project_root = os.path.abspath(os.path.join(self.base_dir, '..'))
        model_paths = {
            'lstm': os.path.join(project_root, 'models', 'bike_lstm_model_optimized.h5'),
            'bp': os.path.join(project_root, 'models', 'bike_bp_model_final.h5'),
            'scaler_x': os.path.join(project_root, 'utils', 'scaler_x.pkl'),
            'scaler_y': os.path.join(project_root, 'utils', 'scaler_y.pkl')
        }
        return model_paths.get(model_name)
    
    def load_models(self):
        """加载所有模型"""
        models_to_load = ['lstm', 'bp', 'scaler_x', 'scaler_y']
        
        for model_name in models_to_load:
            try:
                start_time = time.time()
                model_path = self.get_model_path(model_name)
                
                if not model_path:
                    print(f"模型路径不存在: {model_name}")
                    continue
                
                if not os.path.exists(model_path):
                    print(f"模型文件不存在: {model_path}")
                    continue
                
                if model_name in ['scaler_x', 'scaler_y']:
                    model = joblib.load(model_path)
                    self.scalers[model_name] = model
                else:
                    model = tf.keras.models.load_model(model_path)
                    self.models[model_name] = model
                
                load_time = time.time() - start_time
                self.load_times[model_name] = load_time
                self.model_info[model_name] = {
                    'path': model_path,
                    'loaded_at': timezone.now(),
                    'load_time': load_time,
                    'status': 'loaded'
                }
                
                print(f"成功加载模型: {model_name}，耗时: {load_time:.2f}秒")
                
            except Exception as e:
                print(f"加载模型失败 {model_name}: {str(e)}")
                self.model_info[model_name] = {
                    'path': self.get_model_path(model_name),
                    'loaded_at': None,
                    'load_time': 0,
                    'status': 'failed',
                    'error': str(e)
                }
    
    def reload_model(self, model_name):
        """重新加载指定模型"""
        print(f"重新加载模型: {model_name}")
        try:
            if model_name in self.models:
                del self.models[model_name]
            if model_name in self.scalers:
                del self.scalers[model_name]
            
            start_time = time.time()
            model_path = self.get_model_path(model_name)
            
            if not model_path or not os.path.exists(model_path):
                return False, f"模型文件不存在: {model_path}"
            
            if model_name in ['scaler_x', 'scaler_y']:
                model = joblib.load(model_path)
                self.scalers[model_name] = model
            else:
                model = tf.keras.models.load_model(model_path)
                self.models[model_name] = model
            
            load_time = time.time() - start_time
            self.load_times[model_name] = load_time
            self.model_info[model_name] = {
                'path': model_path,
                'loaded_at': timezone.now(),
                'load_time': load_time,
                'status': 'loaded'
            }
            
            return True, f"成功重新加载模型: {model_name}"
            
        except Exception as e:
            error_msg = f"重新加载模型失败 {model_name}: {str(e)}"
            print(error_msg)
            self.model_info[model_name] = {
                'path': self.get_model_path(model_name),
                'loaded_at': None,
                'load_time': 0,
                'status': 'failed',
                'error': str(e)
            }
            return False, error_msg
    
    def predict(self, model_name, features):
        """使用指定模型进行预测"""
        try:
            start_time = time.time()
            
            # 检查模型是否加载
            if model_name not in self.models:
                return None, f"模型未加载: {model_name}"
            
            # 准备输入数据
            if model_name == 'lstm':
                # LSTM需要时间序列输入 (batch, timesteps, features)
                if len(features.shape) == 2:
                    # 扩展为时间序列格式
                    features = np.repeat(features, 24, axis=0).reshape(1, 24, features.shape[1])
            
            # 归一化处理
            if 'scaler_x' in self.scalers:
                try:
                    features_scaled = self.scalers['scaler_x'].transform(features.reshape(-1, features.shape[-1])).reshape(features.shape)
                except Exception as e:
                    print(f"归一化失败: {str(e)}")
                    # 使用简单缩放作为备选
                    features_scaled = self._simple_scale(features)
            else:
                features_scaled = self._simple_scale(features)
            
            # 模型预测
            model = self.models[model_name]
            prediction = model.predict(features_scaled, verbose=0)
            
            # 反归一化
            if 'scaler_y' in self.scalers:
                try:
                    prediction = self.scalers['scaler_y'].inverse_transform(prediction)
                except Exception as e:
                    print(f"反归一化失败: {str(e)}")
                    # 使用简单缩放作为备选
                    prediction = prediction * 100
            else:
                prediction = prediction * 100
            
            # 结果处理
            prediction = max(0, round(float(prediction[0][0])))
            prediction_time = time.time() - start_time
            
            return prediction, prediction_time
            
        except Exception as e:
            error_msg = f"预测失败 {model_name}: {str(e)}"
            print(error_msg)
            return None, error_msg
    
    def _simple_scale(self, features):
        """简单特征缩放"""
        # 特征维度：[骑行时长、里程、温度、湿度、风速、降雨量、时段编码、区域编码、天气编码、人口密度、商圈类型]
        scale_factors = np.array([60, 20, 50, 100, 10, 100, 3, 3, 2, 5000, 1])
        
        # 确保features是二维数组
        if len(features.shape) == 3:
            return features / scale_factors.reshape(1, 1, -1)
        else:
            return features / scale_factors
    
    def get_model_status(self):
        """获取所有模型状态"""
        status = {}
        for model_name, info in self.model_info.items():
            status[model_name] = {
                'status': info.get('status', 'not_loaded'),
                'loaded_at': info.get('loaded_at'),
                'load_time': info.get('load_time', 0),
                'path': info.get('path'),
                'error': info.get('error')
            }
        return status
    
    def get_best_model(self):
        """获取最佳可用模型"""
        # 优先使用LSTM，其次使用BP
        if 'lstm' in self.models:
            return 'lstm'
        elif 'bp' in self.models:
            return 'bp'
        else:
            return None
    
    def compare_models(self, features):
        """比较多个模型的预测结果"""
        results = {}
        
        for model_name in ['lstm', 'bp']:
            if model_name in self.models:
                prediction, time_taken = self.predict(model_name, features)
                if prediction is not None:
                    results[model_name] = {
                        'prediction': prediction,
                        'time_taken': time_taken,
                        'status': 'success'
                    }
                else:
                    results[model_name] = {
                        'prediction': None,
                        'time_taken': 0,
                        'status': 'failed'
                    }
        
        return results

# 全局模型服务实例
model_service = ModelService()
