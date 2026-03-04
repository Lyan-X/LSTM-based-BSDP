#!/usr/bin/env python3
"""
导入燕山大学56个停车点信息到ParkingSpot表
"""
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_dispatch_platform'))

# 设置Django环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')

# 导入Django
import django
django.setup()

# 导入ParkingSpot模型
from operation_management.models import ParkingSpot

def import_parking_spots():
    """导入停车点信息"""
    # 燕山大学56个停车点信息
    parking_spots = [
        # 西校区停车点
        {"spot_name": "第四体育场", "longitude": 119.517816, "latitude": 39.913239, "campus_area": "西校区", "spot_type": "场馆"},
        {"spot_name": "西北门", "longitude": 119.517939, "latitude": 39.916532, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "信息科学与工程学院", "longitude": 119.521364, "latitude": 39.917036, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "理学院", "longitude": 119.521864, "latitude": 39.917012, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "理学院北侧", "longitude": 119.522728, "latitude": 39.918136, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "西里西亚学院", "longitude": 119.522482, "latitude": 39.916512, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "西区第五教学楼", "longitude": 119.520487, "latitude": 39.914483, "campus_area": "西校区", "spot_type": "教学楼"},
        {"spot_name": "艺术学院", "longitude": 119.51965, "latitude": 39.913924, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "继续教育学院", "longitude": 119.520105, "latitude": 39.913824, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "西区第一教学楼北侧", "longitude": 119.522175, "latitude": 39.911633, "campus_area": "西校区", "spot_type": "教学楼"},
        {"spot_name": "西区第一教学楼", "longitude": 119.522085, "latitude": 39.911128, "campus_area": "西校区", "spot_type": "教学楼"},
        {"spot_name": "西区第二教学楼", "longitude": 119.522642, "latitude": 39.910663, "campus_area": "西校区", "spot_type": "教学楼"},
        {"spot_name": "西区第三教学楼", "longitude": 119.523274, "latitude": 39.910163, "campus_area": "西校区", "spot_type": "教学楼"},
        {"spot_name": "电气工程学院东", "longitude": 119.522709, "latitude": 39.910029, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "电气工程学院西", "longitude": 119.521177, "latitude": 39.909753, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "材料学院 C 楼", "longitude": 119.522369, "latitude": 39.909221, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "材料学院 A 楼", "longitude": 119.52317, "latitude": 39.908501, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "1 组图", "longitude": 119.523088, "latitude": 39.904547, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "2 组图", "longitude": 119.523105, "latitude": 39.905732, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "3 组图", "longitude": 119.523138, "latitude": 39.906529, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "4 组图", "longitude": 119.521776, "latitude": 39.905351, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "西区大食堂东侧", "longitude": 119.521967, "latitude": 39.907251, "campus_area": "西校区", "spot_type": "食堂"},
        {"spot_name": "西区大食堂西侧", "longitude": 119.520043, "latitude": 39.907417, "campus_area": "西校区", "spot_type": "食堂"},
        {"spot_name": "西区浴池", "longitude": 119.519858, "latitude": 39.908508, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "西区超市", "longitude": 119.518344, "latitude": 39.908269, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "10 组图", "longitude": 119.518084, "latitude": 39.909318, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "11 组图", "longitude": 119.517912, "latitude": 39.910224, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "燕园餐厅", "longitude": 119.517918, "latitude": 39.911057, "campus_area": "西校区", "spot_type": "食堂"},
        {"spot_name": "12 组图", "longitude": 119.516213, "latitude": 39.910156, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "里仁教学楼西侧", "longitude": 119.525995, "latitude": 39.906156, "campus_area": "西校区", "spot_type": "教学楼"},
        {"spot_name": "里仁教学楼东南侧", "longitude": 119.527913, "latitude": 39.905674, "campus_area": "西校区", "spot_type": "教学楼"},
        {"spot_name": "西区大学生活动中心", "longitude": 119.526448, "latitude": 39.9052, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "新图书馆西侧", "longitude": 119.531126, "latitude": 39.910473, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "新图书馆东侧", "longitude": 119.534127, "latitude": 39.910557, "campus_area": "西校区", "spot_type": "其他"},
        {"spot_name": "5 号门", "longitude": 119.53553, "latitude": 39.909579, "campus_area": "西校区", "spot_type": "其他"},
        
        # 东校区停车点
        {"spot_name": "第二体育场", "longitude": 119.54074, "latitude": 39.911033, "campus_area": "东校区", "spot_type": "场馆"},
        {"spot_name": "体育学院东侧", "longitude": 119.540493, "latitude": 39.911157, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "体育学院西侧", "longitude": 119.539163, "latitude": 39.911104, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "体育学院南侧", "longitude": 119.53974, "latitude": 39.910715, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "建筑系", "longitude": 119.539941, "latitude": 39.910202, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "文法学院", "longitude": 119.538739, "latitude": 39.909795, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "东区第四教学楼北侧", "longitude": 119.540025, "latitude": 39.909071, "campus_area": "东校区", "spot_type": "教学楼"},
        {"spot_name": "东区第四教学楼南侧", "longitude": 119.53977, "latitude": 39.908658, "campus_area": "东校区", "spot_type": "教学楼"},
        {"spot_name": "车辆与能源学院", "longitude": 119.537491, "latitude": 39.908447, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "后勤管理处", "longitude": 119.538573, "latitude": 39.907428, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "建筑工程与力学学院东侧", "longitude": 119.540408, "latitude": 39.905247, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "东区第二教学楼", "longitude": 119.540397, "latitude": 39.905594, "campus_area": "东校区", "spot_type": "教学楼"},
        {"spot_name": "建筑工程与力学学院西侧", "longitude": 119.539722, "latitude": 39.905178, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "东区第一教学楼", "longitude": 119.539069, "latitude": 39.904948, "campus_area": "东校区", "spot_type": "教学楼"},
        {"spot_name": "东区图书馆", "longitude": 119.537932, "latitude": 39.904936, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "东区第三教学楼", "longitude": 119.537474, "latitude": 39.903952, "campus_area": "东校区", "spot_type": "教学楼"},
        {"spot_name": "至明楼", "longitude": 119.536636, "latitude": 39.901284, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "东区学生生活服务楼西侧", "longitude": 119.536302, "latitude": 39.901898, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "东区学生生活服务楼东侧", "longitude": 119.536619, "latitude": 39.901877, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "东区学生生活服务楼东北侧", "longitude": 119.536717, "latitude": 39.902048, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "至博楼", "longitude": 119.535911, "latitude": 39.901958, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "中快餐厅 2 食堂", "longitude": 119.535492, "latitude": 39.902724, "campus_area": "东校区", "spot_type": "食堂"},
        {"spot_name": "至雅楼南侧", "longitude": 119.534896, "latitude": 39.903012, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "至雅楼北侧", "longitude": 119.534947, "latitude": 39.903248, "campus_area": "东校区", "spot_type": "其他"},
        {"spot_name": "燕鸣湖餐厅西南侧", "longitude": 119.535349, "latitude": 39.903546, "campus_area": "东校区", "spot_type": "食堂"},
        {"spot_name": "燕鸣湖餐厅西北侧", "longitude": 119.535433, "latitude": 39.903957, "campus_area": "东校区", "spot_type": "食堂"},
        {"spot_name": "学生公寓 8 号楼", "longitude": 119.535337, "latitude": 39.905494, "campus_area": "东校区", "spot_type": "其他"},
    ]
    
    # 导入停车点信息
    created_count = 0
    updated_count = 0
    
    for spot in parking_spots:
        try:
            # 尝试获取现有停车点
            existing_spot = ParkingSpot.objects.filter(spot_name=spot['spot_name']).first()
            
            if existing_spot:
                # 更新现有停车点
                existing_spot.longitude = spot['longitude']
                existing_spot.latitude = spot['latitude']
                existing_spot.campus_area = spot['campus_area']
                existing_spot.spot_type = spot['spot_type']
                existing_spot.save()
                updated_count += 1
                print(f"更新停车点: {spot['spot_name']}")
            else:
                # 创建新停车点
                new_spot = ParkingSpot(
                    spot_name=spot['spot_name'],
                    longitude=spot['longitude'],
                    latitude=spot['latitude'],
                    campus_area=spot['campus_area'],
                    spot_type=spot['spot_type']
                )
                new_spot.save()
                created_count += 1
                print(f"创建停车点: {spot['spot_name']}")
        except Exception as e:
            print(f"处理停车点 {spot['spot_name']} 时出错: {str(e)}")
    
    print(f"\n导入完成！")
    print(f"创建了 {created_count} 个停车点")
    print(f"更新了 {updated_count} 个停车点")
    print(f"总停车点数量: {ParkingSpot.objects.count()}")

if __name__ == '__main__':
    print("开始导入燕山大学停车点信息...")
    import_parking_spots()
