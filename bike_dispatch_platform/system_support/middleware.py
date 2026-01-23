from django.utils.deprecation import MiddlewareMixin
from .models import SystemLog
from django.utils import timezone


class OperationLogMiddleware(MiddlewareMixin):
    """操作日志中间件（任务书"系统日志记录"要求）"""
    
    # 排除的URL路径（不需要记录日志）
    EXCLUDE_PATHS = [
        '/static/',
        '/media/',
        '/admin/jsi18n/',
        '/favicon.ico',
    ]
    
    def process_request(self, request):
        """请求处理前"""
        # 排除静态文件和媒体文件
        path = request.path
        if any(path.startswith(exclude) for exclude in self.EXCLUDE_PATHS):
            return None
        
        # 记录请求信息到session（用于process_response）
        request._log_action = None
        request._log_description = None
        
        return None
    
    def process_response(self, request, response):
        """请求处理后"""
        # 排除静态文件和媒体文件
        path = request.path
        if any(path.startswith(exclude) for exclude in self.EXCLUDE_PATHS):
            return response
        
        # 只记录已登录用户的操作
        if not request.user.is_authenticated:
            return response
        
        # 如果视图函数已经记录了日志，则跳过
        if hasattr(request, '_log_action') and request._log_action:
            return response
        
        # 自动记录关键操作
        action = None
        description = None
        
        # 根据URL路径判断操作类型
        if '/data/upload' in path and request.method == 'POST':
            action = 'upload'
            description = f'上传数据文件：{request.FILES.get("data_file", {}).name if hasattr(request, "FILES") else "未知"}'
        elif '/predict' in path and request.method == 'POST':
            action = 'predict'
            description = '执行需求预测'
        elif '/schedule' in path and request.method == 'POST':
            action = 'schedule'
            description = '创建调度任务'
        
        # 记录错误操作（4xx, 5xx状态码）
        if response.status_code >= 400:
            action = 'error'
            description = f'操作错误：{path}，状态码：{response.status_code}'
        
        # 记录日志
        if action:
            try:
                SystemLog.objects.create(
                    user=request.user,
                    action=action,
                    description=description or f'访问：{path}',
                    ip_address=self._get_client_ip(request)
                )
            except Exception:
                pass  # 日志记录失败不影响正常响应
        
        return response
    
    def _get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
