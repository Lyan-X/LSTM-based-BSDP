"""
基于新映射关系重新确定固定车辆数量
"""
import pandas as pd
import numpy as np
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

class VehicleCountCalculator:
    """车辆数量计算器"""
    
    def __init__(self):
        self.washington_stations_path = BASE_DIR / 'washington_stations_complete.csv'
        self.mapping_data = [
            [1, '西区第一教学楼', 'academic', 33200.0, '17th St & New York Ave NW', 'academic', '类型 + 潮汐 + 最高流量匹配核心教学楼', 3726.99, 1],
            [2, '西区第二教学楼', 'academic', 32418, 'West Hyattsville Metro', 'academic', '类型 + 潮汐 + 高流量匹配核心教学楼', 1885.34, 2],
            [3, '西区第三教学楼', 'academic', 32420, 'Prince George\'s Plaza Metro', 'academic', '类型 + 潮汐 + 高流量匹配核心教学楼', 1510.00, 3],
            [4, '东区第一教学楼', 'academic', 32255.0, 'Hartland Rd & Harte Pl', 'academic', '类型 + 潮汐 + 高流量匹配核心教学楼', 337.33, 4],
            [5, '东区第二教学楼', 'academic', 32260.0, 'Vienna Metro South', 'academic', '类型 + 潮汐 + 高流量匹配核心教学楼', 238.99, 5],
            [6, '东区第三教学楼', 'academic', 32258.0, 'Reston Town Center Metro South', 'academic', '类型 + 潮汐 + 高流量匹配核心教学楼', 146.34, 6],
            [7, '新图书馆西侧', 'academic', 32409, 'Southern Ave Metro', 'academic', '类型 + 潮汐 + 高流量匹配核心图书馆', 145.67, 7],
            [8, '新图书馆东侧', 'academic', 32289.0, 'Franconia-Springfield Metro North', 'academic', '类型 + 潮汐 + 高流量匹配核心图书馆', 119.68, 8],
            [9, '东区图书馆', 'academic', 31602, 'Park Rd & Holmead Pl NW', 'academic', '类型 + 潮汐 + 高流量匹配核心图书馆', 109.34, 9],
            [10, '信息科学与工程学院', 'academic', 31325, 'Reservoir Rd & 38th St NW', 'academic', '类型 + 潮汐 + 中高流量匹配学院楼', 85.99, 10],
            [11, '理学院', 'academic', 31318, 'Connecticut Ave & Yuma St NW', 'academic', '类型 + 潮汐 + 中高流量匹配学院楼', 32.33, 11],
            [12, '车辆与能源学院', 'academic', 31319, 'Wisconsin Ave & Brandywine St NW', 'academic', '类型 + 潮汐 + 中高流量匹配学院楼', 26.66, 12],
            [13, '文法学院', 'academic', 31320, 'American University East Campus', 'academic', '类型 + 潮汐 + 中高流量匹配学院楼', 23.33, 13],
            [14, '建筑工程与力学学院东侧', 'academic', 31315, 'Connecticut Ave & McKinley St NW', 'academic', '类型 + 潮汐 + 中高流量匹配学院楼', 22.33, 14],
            [15, '建筑工程与力学学院西侧', 'academic', 31106, 'Calvert & Biltmore St NW', 'academic', '类型 + 潮汐 + 中高流量匹配学院楼', 22.99, 15],
            [16, '东区第四教学楼北侧', 'academic', 31402, '14th St Heights / 14th & Crittenden St NW', 'academic', '类型 + 潮汐 + 中流量匹配教学楼', 21.68, 16],
            [17, '东区第四教学楼南侧', 'academic', 32040, 'Friendship Blvd & Willard Ave', 'academic', '类型 + 潮汐 + 中流量匹配教学楼', 14.00, 17],
            [18, '理学院北侧', 'academic', 31926, 'Wilson Blvd. & N. Vermont St.', 'academic', '类型 + 潮汐 + 中流量匹配学院附属楼', 13.00, 18],
            [19, '西里西亚学院', 'academic', 31301, 'Ward Circle / American University', 'academic', '类型 + 潮汐 + 中流量匹配学院楼', 15.99, 19],
            [20, '西区第五教学楼', 'academic', 31411, 'Georgia & Missouri Ave NW', 'academic', '类型 + 潮汐 + 中流量匹配教学楼', 15.33, 20],
            [21, '西区第一教学楼北侧', 'academic', 31801, 'Anacostia Metro', 'academic', '类型 + 潮汐 + 中流量匹配教学楼附属楼', 11.34, 21],
            [22, '电气工程学院东', 'academic', 31719, 'Oklahoma Ave & Benning Rd NE', 'academic', '类型 + 潮汐 + 中流量匹配学院楼', 10.34, 22],
            [23, '电气工程学院西', 'academic', 31935, 'National Airport', 'academic', '类型 + 潮汐 + 中流量匹配学院楼', 10.00, 23],
            [24, '材料学院 A 楼', 'academic', 31309, 'Fessenden St & Wisconsin Ave NW', 'academic', '类型 + 潮汐 + 中流量匹配学院楼', 9.99, 24],
            [25, '里仁教学楼西侧', 'academic', 31412, '3rd St & Riggs Rd NE', 'academic', '类型 + 潮汐 + 中流量匹配教学楼', 9.99, 25],
            [26, '里仁教学楼东南侧', 'academic', 32036, 'Fenton St & Ellsworth Dr', 'academic', '类型 + 潮汐 + 中流量匹配教学楼', 9.00, 26],
            [27, '至明楼', 'academic', 31919, 'Carlin Springs Rd & N Thomas St', 'academic', '类型 + 潮汐 + 中低流量匹配行政教学楼', 8.67, 27],
            [28, '至博楼', 'academic', 31807, 'Pleasant St & MLK Ave SE', 'academic', '类型 + 潮汐 + 中低流量匹配行政教学楼', 8.34, 28],
            [29, '艺术学院', 'academic', 32000, 'Norfolk Ave & Fairmont St', 'academic', '类型 + 潮汐 + 中低流量匹配学院楼', 4.33, 29],
            [30, '继续教育学院', 'academic', 32067, 'Shady Grove Metro East', 'academic', '类型 + 潮汐 + 中低流量匹配学院楼', 5.00, 30],
            [31, '材料学院 C 楼', 'academic', 31936, 'Fern St & Army Navy Dr', 'academic', '类型 + 潮汐 + 低流量匹配学院附属楼', 3.33, 31],
            [32, '体育学院东侧', 'academic', 31705, 'Benning Branch Library', 'academic', '类型 + 潮汐 + 低流量匹配学院楼', 2.66, 32],
            [33, '体育学院西侧', 'academic', 31812, '16th & Q St SE / Anacostia HS', 'academic', '类型 + 潮汐 + 低流量匹配学院楼', 2.66, 33],
            [34, '建筑系', 'academic', 32062, 'Wheaton Metro / Georgia Ave & Reedie Dr', 'academic', '类型 + 潮汐 + 低流量匹配学院楼', 2.66, 34],
            [35, '学生公寓 8 号楼', 'residential', 32421, 'Riverdale Park Town Center', 'residential', '类型 + 潮汐 + 最高流量匹配核心学生公寓', 1746.67, 1],
            [36, '中快餐厅 2 食堂', 'residential', 32606, 'N Roosevelt St & Roosevelt Blvd', 'residential', '类型 + 潮汐 + 高流量匹配生活区食堂', 1177.66, 2],
            [37, '西区超市', 'residential', 32609, 'W Columbia St & N Washington St', 'residential', '类型 + 潮汐 + 高流量匹配生活区商业', 1020.01, 3],
            [38, '燕园餐厅', 'residential', 32416, 'Chillum Rd & Riggs Rd / Riggs Plaza', 'residential', '类型 + 潮汐 + 高流量匹配生活区食堂', 1012.00, 4],
            [39, '东区学生生活服务楼东侧', 'residential', 32600, 'George Mason High School / Haycock Rd & Leesburg Pike', 'residential', '类型 + 潮汐 + 中高流量匹配生活区服务楼', 916.01, 5],
            [40, '东区学生生活服务楼西侧', 'residential', 32607, 'S Maple Ave & S Washington St', 'residential', '类型 + 潮汐 + 中高流量匹配生活区服务楼', 861.00, 6],
            [41, '东区学生生活服务楼东北侧', 'residential', 32408, 'Oglethorpe St & 42nd Ave', 'residential', '类型 + 潮汐 + 中高流量匹配生活区服务楼', 858.00, 7],
            [42, '西区浴池', 'residential', 32404, 'Perry & 35th St', 'residential', '类型 + 潮汐 + 中流量匹配生活区配套', 852.33, 8],
            [43, '10 组图', 'residential', 32602, 'N Oak St & W Broad St', 'residential', '类型 + 潮汐 + 中流量匹配生活区组团', 827.68, 9],
            [44, '11 组图', 'residential', 32608, 'Falls Church City Hall / Park Ave & Little Falls St', 'residential', '类型 + 潮汐 + 中流量匹配生活区组团', 797.67, 10],
            [45, '12 组图', 'residential', 32243.0, 'Fairway Dr & Hook Rd', 'residential', '类型 + 潮汐 + 中流量匹配生活区组团', 765.00, 11],
            [46, '至雅楼北侧', 'residential', 32603, 'Pennsylvania Ave & Park Ave', 'residential', '类型 + 潮汐 + 中低流量匹配学生公寓', 738.67, 12],
            [47, '至雅楼南侧', 'residential', 32604, 'E Fairfax St & S Washington St', 'residential', '类型 + 潮汐 + 中低流量匹配学生公寓', 554.67, 13],
            [48, '西区大食堂东侧', 'comprehensive', 32423, 'National Harbor Carousel', 'comprehensive', '类型 + 潮汐 + 最高流量匹配核心食堂', 4169.66, 1],
            [49, '西区大食堂西侧', 'comprehensive', 32402, 'Baltimore Ave & Van Buren St / Riverdale Park Station', 'comprehensive', '类型 + 潮汐 + 高流量匹配核心食堂', 1660.33, 2],
            [50, '燕鸣湖餐厅西南侧', 'comprehensive', 32415, 'Tanger Outlets', 'comprehensive', '类型 + 潮汐 + 高流量匹配核心食堂', 1501.65, 3],
            [51, '燕鸣湖餐厅西北侧', 'comprehensive', 32403, 'Baltimore Ave & Jefferson St', 'comprehensive', '类型 + 潮汐 + 高流量匹配核心食堂', 1425.67, 4],
            [52, '第四体育场', 'comprehensive', 32406, 'Fleet St & Waterfront St', 'comprehensive', '类型 + 潮汐 + 高流量匹配大型文体设施', 1101.34, 5],
            [53, '第二体育场', 'comprehensive', 32422, 'The Mall at Prince Georges', 'comprehensive', '类型 + 潮汐 + 高流量匹配大型文体设施', 1023.33, 6],
            [54, '西区大学生活动中心', 'comprehensive', 32413, 'Rhode Island Ave & 39th St / Brentwood Arts Exchange', 'comprehensive', '类型 + 潮汐 + 中高流量匹配学生活动中心', 771.00, 7],
            [55, '体育学院南侧', 'comprehensive', 32417, 'Hyattsville Library / Adelphi Rd & Toledo Rd', 'comprehensive', '类型 + 潮汐 + 中流量匹配文体配套', 413.33, 8],
            [56, '后勤管理处', 'comprehensive', 32424.0, 'Roosevelt Center & Crescent Rd', 'comprehensive', '类型 + 潮汐 + 中流量匹配行政配套', 329.67, 9],
            [57, '1 组图', 'comprehensive', 32401, 'Largo Town Center Metro', 'comprehensive', '类型 + 潮汐 + 中流量匹配园区组团', 326.33, 10],
            [58, '2 组图', 'comprehensive', 32419.0, 'Capitol Heights Metro', 'comprehensive', '类型 + 潮汐 + 中低流量匹配园区组团', 210.67, 11],
            [59, '3 组图', 'comprehensive', 32407, 'Oxon Hill Park & Ride', 'comprehensive', '类型 + 潮汐 + 中低流量匹配园区组团', 195.01, 12],
            [60, '4 组图', 'comprehensive', 32400, '1301 McCormick Dr / Wayne K. Curry Admin Bldg', 'comprehensive', '类型 + 潮汐 + 低流量匹配园区组团', 135.33, 13],
            [61, '西北门', 'transit', 32402, 'Baltimore Ave & Van Buren St / Riverdale Park Station', 'transit', '类型 + 潮汐 + 最高流量匹配主校门交通枢纽', 1660.33, 1],
            [62, '5 号门', 'transit', 32265.0, 'Pimmit Dr & Los Pueblos Ln', 'transit', '类型 + 潮汐 + 次高流量匹配次校门交通枢纽', 298.33, 2]
        ]
    
    def load_washington_stations(self):
        """加载华盛顿站点信息"""
        print("加载华盛顿站点信息...")
        
        if not self.washington_stations_path.exists():
            raise FileNotFoundError(f"文件不存在：{self.washington_stations_path}")
        
        df = pd.read_csv(self.washington_stations_path)
        print(f"成功加载 {len(df)} 个华盛顿站点")
        return df
    
    def calculate_vehicle_count(self):
        """计算合理的车辆总数"""
        print("计算合理的车辆总数...")
        
        # 使用映射表中的流量数据计算
        total_flow = 0
        flow_data = []
        
        for item in self.mapping_data:
            mapping_id, ysu_name, ysu_type, wash_id, wash_name, wash_type, match_dim, wash_flow, priority = item
            total_flow += wash_flow
            flow_data.append({
                'mapping_id': mapping_id,
                'ysu_name': ysu_name,
                'ysu_type': ysu_type,
                'wash_id': wash_id,
                'wash_name': wash_name,
                'wash_flow': wash_flow,
                'priority': priority
            })
            print(f"{ysu_name} -> {wash_name}: 流量 {wash_flow:.2f}")
        
        # 基于流量计算车辆总数
        # 假设每100单位流量对应1辆车辆
        suggested_count = int(round(total_flow / 100))
        # 调整为合理的整数，考虑系统运行
        final_count = max(500, min(2000, suggested_count))
        
        print(f"\n=== 车辆数量计算结果 ===")
        print(f"基于映射站点的总流量：{total_flow:.2f}")
        print(f"建议的固定车辆总数：{suggested_count} 辆")
        print(f"最终确定的固定车辆总数：{final_count} 辆")
        
        # 计算每个站点的分配车辆数
        print(f"\n=== 站点车辆分配方案 ===")
        station_allocation = []
        allocation_total = 0
        
        for item in self.mapping_data:
            mapping_id, ysu_name, ysu_type, wash_id, wash_name, wash_type, match_dim, wash_flow, priority = item
            
            # 按流量比例分配
            allocation = max(1, int(round(wash_flow * final_count / total_flow)))
            allocation_total += allocation
            
            station_allocation.append({
                '映射ID': mapping_id,
                '燕大站点': ysu_name,
                '类型': ysu_type,
                '华盛顿站点': wash_name,
                '华盛顿站点ID': wash_id,
                '流量': wash_flow,
                '分配车辆数': allocation
            })
        
        # 调整分配，确保总数准确
        if allocation_total != final_count:
            diff = final_count - allocation_total
            # 按优先级调整
            station_allocation.sort(key=lambda x: x['分配车辆数'], reverse=True)
            for i in range(abs(diff)):
                if i < len(station_allocation):
                    if diff > 0:
                        station_allocation[i]['分配车辆数'] += 1
                    else:
                        if station_allocation[i]['分配车辆数'] > 1:
                            station_allocation[i]['分配车辆数'] -= 1
        
        # 重新计算总数
        final_allocation_total = sum(s['分配车辆数'] for s in station_allocation)
        
        # 输出分配结果
        print(f"\n最终车辆分配（总数：{final_allocation_total} 辆）：")
        print("-" * 120)
        print(f"| {'映射ID':<5} | {'燕大站点':<20} | {'类型':<10} | {'华盛顿站点':<30} | {'流量':<10} | {'分配车辆数':<8} |")
        print("-" * 120)
        
        for item in sorted(station_allocation, key=lambda x: x['映射ID']):
            print(f"| {item['映射ID']:<5} | {item['燕大站点']:<20} | {item['类型']:<10} | {item['华盛顿站点'][:28]:<30} | {item['流量']:<10.2f} | {item['分配车辆数']:<8} |")
        
        print("-" * 100)
        
        # 按类型统计
        type_stats = {}
        for item in station_allocation:
            ysu_type = item['类型']
            if ysu_type not in type_stats:
                type_stats[ysu_type] = 0
            type_stats[ysu_type] += item['分配车辆数']
        
        print(f"\n=== 按类型统计 ===")
        for ysu_type, count in type_stats.items():
            print(f"{ysu_type}: {count} 辆")
        
        return final_count, station_allocation
    
    def run(self):
        """执行计算"""
        try:
            final_count, allocation = self.calculate_vehicle_count()
            print(f"\n✅ 计算完成！")
            print(f"✅ 建议的固定车辆总数：{final_count} 辆")
            return final_count
        except Exception as e:
            print(f"❌ 计算失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return None


if __name__ == '__main__':
    calculator = VehicleCountCalculator()
    final_count = calculator.run()
