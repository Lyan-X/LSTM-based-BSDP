import os
import shutil

# 清理 data_process 应用的迁移文件
data_process_migrations_dir = 'bike_dispatch_platform/data_process/migrations'

# 保留 __init__.py 文件，删除其他迁移文件
for file in os.listdir(data_process_migrations_dir):
    if file != '__init__.py':
        file_path = os.path.join(data_process_migrations_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
            print(f"删除文件: {file_path}")

print("清理完成！")