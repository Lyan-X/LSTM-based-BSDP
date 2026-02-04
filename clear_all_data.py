import os
import shutil

# 定义所有需要清理的数据目录、文件后缀
CLEAN_DIRS = [
    "./data",
    "./cache",
    "./output",
    "./models",
    "./temp",
    "./results",
    "./test_data",
    "./station_info"
]

CLEAN_SUFFIX = [
    ".csv",
    ".json",
    ".h5",
    ".cache",
    ".xlsx",
    ".txt",
    ".html",
    ".png"
]

# 需要删除的特定文件
DELETE_FILES = [
    "./ysu_bike_data.csv",
    "./ysu_bike_geo_distribution.html",
    "./ysu_lstm_bsdp_model.h5",
    "./clean_data.py"
]

def clear_all_system_data():
    print("===== 开始全量清空系统数据 =====")
    
    # 1. 删除整个数据目录，重建空文件夹
    for dir_path in CLEAN_DIRS:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        os.makedirs(dir_path, exist_ok=True)
        print(f"目录重置完成: {dir_path}")
    
    # 2. 删除根目录下所有数据类文件
    for file_name in os.listdir("."):
        for suffix in CLEAN_SUFFIX:
            if file_name.endswith(suffix):
                try:
                    os.remove(file_name)
                    print(f"删除数据文件: {file_name}")
                except Exception as e:
                    print(f"删除失败 {file_name}: {str(e)}")
    
    # 3. 删除特定文件
    for file_path in DELETE_FILES:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"删除特定文件: {file_path}")
            else:
                print(f"文件不存在: {file_path}")
        except Exception as e:
            print(f"删除失败 {file_path}: {str(e)}")
    
    # 4. 空数据标记文件，告知后端接口返回空数据
    with open("./data/empty_flag.txt", "w", encoding="utf-8") as f:
        f.write("system_data_cleared: true")
    
    print("===== 数据清理完成，系统数据集为空 =====")

if __name__ == "__main__":
    clear_all_system_data()