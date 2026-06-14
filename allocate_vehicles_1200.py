"""
1200 辆车辆分配方案生成器
按照指定的比例和规则分配车辆
"""
import pandas as pd
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

class VehicleAllocator:
    """车辆分配器"""
    
    def __init__(self):
        self.total_vehicles = 1200
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
        
        # 类型分配比例
        self.type_allocation = {
            'academic': 396,    # 33%
            'residential': 372,  # 31%
            'comprehensive': 372, # 31%
            'transit': 60        # 5%
        }
    
    def allocate_vehicles(self):
        """分配车辆"""
        print("开始分配 1200 辆车辆...")
        
        # 按类型分组
        stations_by_type = {}
        for item in self.mapping_data:
            ysu_type = item[2]
            if ysu_type not in stations_by_type:
                stations_by_type[ysu_type] = []
            stations_by_type[ysu_type].append(item)
        
        # 分配结果
        allocation_result = []
        
        # 分配学术办公型（396 辆）
        print("\n分配学术办公型站点（396 辆）...")
        academic_stations = stations_by_type['academic']
        academic_stations.sort(key=lambda x: x[8])
        
        # 核心教学楼（前6个）
        core_academic = academic_stations[:6]
        for i, station in enumerate(core_academic):
            if i < 3:  # 前3个核心教学楼
                allocation = 25
            else:  # 后3个核心教学楼
                allocation = 22
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 普通学术站点（中间16个）
        normal_academic = academic_stations[6:22]
        for station in normal_academic:
            allocation = 19
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 边缘学术站点（最后8个）
        edge_academic = academic_stations[22:]
        for station in edge_academic:
            allocation = 10
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 分配居住型（372 辆）
        print("\n分配居住型站点（372 辆）...")
        residential_stations = stations_by_type['residential']
        residential_stations.sort(key=lambda x: x[8])
        
        # 核心生活区（前4个）
        core_residential = residential_stations[:4]
        for i, station in enumerate(core_residential):
            if i == 0:  # 学生公寓8号楼
                allocation = 30
            else:  # 其他核心生活区
                allocation = 25
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 普通居住站点（中间6个）
        normal_residential = residential_stations[4:10]
        for station in normal_residential:
            allocation = 22
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 边缘居住站点（最后3个）
        edge_residential = residential_stations[10:]
        for station in edge_residential:
            allocation = 18
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 分配综合商业型（372 辆）
        print("\n分配综合商业型站点（372 辆）...")
        comprehensive_stations = stations_by_type['comprehensive']
        comprehensive_stations.sort(key=lambda x: x[8])
        
        # 核心食堂（前4个）
        core_comprehensive = comprehensive_stations[:4]
        for i, station in enumerate(core_comprehensive):
            if i == 0:  # 西区大食堂东侧
                allocation = 30
            else:  # 其他核心食堂
                allocation = 25
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 普通综合商业站点（中间5个）
        normal_comprehensive = comprehensive_stations[4:9]
        for station in normal_comprehensive:
            allocation = 22
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 边缘综合商业站点（最后4个）
        edge_comprehensive = comprehensive_stations[9:]
        for station in edge_comprehensive:
            allocation = 18
            allocation_result.append({
                '映射ID': station[0],
                '燕大站点': station[1],
                '类型': station[2],
                '华盛顿站点': station[4],
                '优先级': station[8],
                '分配车辆数': allocation
            })
        
        # 分配交通枢纽型（60 辆）
        print("\n分配交通枢纽型站点（60 辆）...")
        transit_stations = stations_by_type['transit']
        transit_stations.sort(key=lambda x: x[8])
        
        # 西北门
        allocation_result.append({
            '映射ID': transit_stations[0][0],
            '燕大站点': transit_stations[0][1],
            '类型': transit_stations[0][2],
            '华盛顿站点': transit_stations[0][4],
            '优先级': transit_stations[0][8],
            '分配车辆数': 40
        })
        
        # 5号门
        allocation_result.append({
            '映射ID': transit_stations[1][0],
            '燕大站点': transit_stations[1][1],
            '类型': transit_stations[1][2],
            '华盛顿站点': transit_stations[1][4],
            '优先级': transit_stations[1][8],
            '分配车辆数': 20
        })
        
        # 精确调整分配，确保总数准确
        total_allocated = sum(s['分配车辆数'] for s in allocation_result)
        diff = 1200 - total_allocated
        
        if diff != 0:
            print(f"\n调整分配：总分配 {total_allocated} 辆，需要调整 {diff} 辆")
            
            # 按优先级和车辆数排序，优先调整车辆数较多的站点
            allocation_result.sort(key=lambda x: (x['优先级'], -x['分配车辆数']))
            
            for i in range(abs(diff)):
                if i < len(allocation_result):
                    if diff > 0:
                        # 增加车辆时优先给核心站点
                        if allocation_result[i]['优先级'] <= 3:
                            allocation_result[i]['分配车辆数'] += 1
                    else:
                        # 减少车辆时优先从边缘站点减少
                        if allocation_result[i]['分配车辆数'] > 10:
                            allocation_result[i]['分配车辆数'] -= 1
                        else:
                            # 如果边缘站点已经达到最小值，从普通站点减少
                            for j in range(len(allocation_result)):
                                if allocation_result[j]['分配车辆数'] > 15:
                                    allocation_result[j]['分配车辆数'] -= 1
                                    break
        
        # 重新计算总数
        final_total = sum(s['分配车辆数'] for s in allocation_result)
        print(f"\n最终分配总数：{final_total} 辆")
        
        return allocation_result
    
    def generate_report(self, allocation_result):
        """生成报告"""
        print("\n=== 1200 辆车辆分配总表 ===")
        print("-" * 120)
        print(f"| {'映射ID':<5} | {'燕大站点':<20} | {'类型':<10} | {'华盛顿站点':<30} | {'优先级':<6} | {'分配车辆数':<8} |")
        print("-" * 120)
        
        for item in sorted(allocation_result, key=lambda x: x['映射ID']):
            print(f"| {item['映射ID']:<5} | {item['燕大站点']:<20} | {item['类型']:<10} | {item['华盛顿站点'][:28]:<30} | {item['优先级']:<6} | {item['分配车辆数']:<8} |")
        
        print("-" * 120)
        
        # 按类型统计
        type_stats = {}
        for item in allocation_result:
            ysu_type = item['类型']
            if ysu_type not in type_stats:
                type_stats[ysu_type] = 0
            type_stats[ysu_type] += item['分配车辆数']
        
        print("\n=== 按类型分配统计表 ===")
        print("-" * 80)
        print(f"| {'类型':<15} | {'分配车辆数':<10} | {'占比':<8} |")
        print("-" * 80)
        
        for ysu_type, count in type_stats.items():
            percentage = (count / 1200) * 100
            print(f"| {ysu_type:<15} | {count:<10} | {percentage:<8.1f}% |")
        
        print("-" * 80)
        print(f"| {'总计':<15} | {sum(type_stats.values()):<10} | 100.0% |")
        print("-" * 80)
        
        # 验证
        print("\n=== 验证结果 ===")
        total = sum(item['分配车辆数'] for item in allocation_result)
        min_vehicles = min(item['分配车辆数'] for item in allocation_result)
        avg_vehicles = total / len(allocation_result)
        
        core_stations = [s for s in allocation_result if s['优先级'] <= 3]
        min_core_vehicles = min(s['分配车辆数'] for s in core_stations) if core_stations else 0
        
        print(f"总车辆数：{total} 辆")
        print(f"站点数量：{len(allocation_result)} 个")
        print(f"平均每站车辆数：{avg_vehicles:.2f} 辆")
        print(f"最少车辆数：{min_vehicles} 辆")
        print(f"核心站点最少车辆数：{min_core_vehicles} 辆")
        
        # 检查约束
        constraints_met = True
        if total != 1200:
            print("❌ 总车辆数不等于 1200")
            constraints_met = False
        if min_vehicles < 10:
            print("❌ 存在站点车辆数小于 10")
            constraints_met = False
        if min_core_vehicles < 20:
            print("❌ 核心站点车辆数小于 20")
            constraints_met = False
        
        if constraints_met:
            print("✅ 所有约束条件均满足")
        
        # 保存结果
        output_path = BASE_DIR / 'vehicle_allocation_1200.csv'
        df = pd.DataFrame(allocation_result)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n分配结果已保存至：{output_path}")
    
    def run(self):
        """执行分配"""
        try:
            allocation_result = self.allocate_vehicles()
            self.generate_report(allocation_result)
            print("\n✅ 车辆分配完成！")
            return allocation_result
        except Exception as e:
            print(f"❌ 分配失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return None


if __name__ == '__main__':
    allocator = VehicleAllocator()
    allocator.run()
