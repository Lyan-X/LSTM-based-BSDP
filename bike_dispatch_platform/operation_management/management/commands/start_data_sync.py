import time
import threading
from django.core.management.base import BaseCommand
from operation_management.services.data_sync_service import DataSyncService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '启动数据同步服务，定时30秒刷新数据'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.sync_thread = None
    
    def handle(self, *args, **options):
        self.stdout.write('启动数据同步服务...')
        self.stdout.write('按 Ctrl+C 停止服务')
        
        self.running = True
        self.sync_thread = threading.Thread(target=self.sync_loop)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write('正在停止数据同步服务...')
            self.running = False
            if self.sync_thread:
                self.sync_thread.join(timeout=5)
            self.stdout.write('数据同步服务已停止')
    
    def sync_loop(self):
        """数据同步循环"""
        sync_interval = 30  # 30秒同步一次
        
        while self.running:
            start_time = time.time()
            
            try:
                # 运行数据同步
                result = DataSyncService.run_sync_cycle()
                
                # 计算同步耗时
                sync_duration = time.time() - start_time
                
                # 输出同步结果
                self.stdout.write(f'数据同步完成: 车辆同步={result["vehicle_sync"]}, 预测同步={result["prediction_sync"]}, 生成任务={result["tasks_created"]}, 耗时={sync_duration:.2f}秒')
                
            except Exception as e:
                logger.error(f'数据同步失败: {str(e)}')
                self.stdout.write(f'数据同步失败: {str(e)}')
            
            # 等待下一次同步
            remaining_time = max(0, sync_interval - (time.time() - start_time))
            time.sleep(remaining_time)