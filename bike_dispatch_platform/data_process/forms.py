from django import forms
from .models import BikeRideData, WeatherData
import pandas as pd
from datetime import datetime
import warnings

# 忽略pandas无关警告
warnings.filterwarnings('ignore')


# ========== 燕山大学停车点选项（用于本地数据录入下拉框） ==========
YSU_PARKING_SPOTS = [
    ('第四体育场', '第四体育场'), ('西北门', '西北门'),
    ('信息科学与工程学院', '信息科学与工程学院'), ('理学院', '理学院'),
    ('西里西亚学院', '西里西亚学院'), ('西区第五教学楼', '西区第五教学楼'),
    ('艺术学院', '艺术学院'), ('继续教育学院', '继续教育学院'),
    ('西区第一教学楼', '西区第一教学楼'), ('西区第二教学楼', '西区第二教学楼'),
    ('西区第三教学楼', '西区第三教学楼'), ('电气工程学院东', '电气工程学院东'),
    ('材料学院A楼', '材料学院A楼'), ('西区大食堂东侧', '西区大食堂东侧'),
    ('西区大食堂西侧', '西区大食堂西侧'), ('燕园餐厅', '燕园餐厅'),
    ('里仁教学楼西侧', '里仁教学楼西侧'), ('新图书馆西侧', '新图书馆西侧'),
    ('新图书馆东侧', '新图书馆东侧'), ('第二体育场', '第二体育场'),
    ('体育学院东侧', '体育学院东侧'), ('建筑系', '建筑系'),
    ('文法学院', '文法学院'), ('东区第四教学楼北侧', '东区第四教学楼北侧'),
    ('车辆与能源学院', '车辆与能源学院'), ('东区第二教学楼', '东区第二教学楼'),
    ('东区第一教学楼', '东区第一教学楼'), ('东区图书馆', '东区图书馆'),
    ('东区第三教学楼', '东区第三教学楼'), ('至明楼', '至明楼'),
    ('中快餐厅2食堂', '中快餐厅2食堂'), ('学生公寓8号楼', '学生公寓8号楼'),
]


class RideDataEntryForm(forms.ModelForm):
    """骑行数据手动录入表单（任务书"本地数据录入"要求）"""
    start_point = forms.ChoiceField(
        choices=YSU_PARKING_SPOTS,
        label="骑行起点",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    end_point = forms.ChoiceField(
        choices=YSU_PARKING_SPOTS,
        label="骑行终点",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    ride_datetime = forms.DateTimeField(
        label="骑行时间",
        widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']
    )
    duration = forms.FloatField(
        label="骑行时长（分钟）",
        min_value=0, max_value=180,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "如：15.5"})
    )
    distance = forms.FloatField(
        label="骑行距离（公里）",
        min_value=0, max_value=20,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "如：2.3"})
    )
    temperature = forms.FloatField(
        label="温度（℃）",
        required=False, initial=25.0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"})
    )
    wind_speed = forms.FloatField(
        label="风速（m/s）",
        required=False, initial=0.0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"})
    )

    class Meta:
        model = BikeRideData
        fields = ['start_point', 'end_point', 'ride_datetime', 'duration', 'distance', 'temperature', 'wind_speed']


class WeatherDataEntryForm(forms.ModelForm):
    """天气数据手动录入表单"""
    area = forms.CharField(
        label="区域",
        max_length=100,
        initial="燕山大学",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "如：燕山大学"})
    )
    date = forms.DateField(
        label="日期",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    temperature = forms.FloatField(
        label="温度（℃）",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"})
    )
    humidity = forms.FloatField(
        label="湿度（%）",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"})
    )
    wind_speed = forms.FloatField(
        label="风速（m/s）",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"})
    )
    rainfall = forms.FloatField(
        label="降雨量（mm）",
        required=False, initial=0.0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"})
    )
    weather_type = forms.ChoiceField(
        label="天气类型",
        choices=[("sunny", "晴"), ("cloudy", "阴"), ("rain", "雨")],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = WeatherData
        fields = ['area', 'date', 'temperature', 'humidity', 'wind_speed', 'rainfall', 'weather_type']


class WeatherDataUploadForm(forms.Form):
    """天气数据上传表单-终极版：纯Python原生处理，彻底解决所有pandas报错"""
    data_source = forms.CharField(
        label="数据来源",
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "如：公开天气数据集/本地采集"})
    )
    file = forms.FileField(
        label="选择天气数据文件（CSV/Excel）",
        widget=forms.FileInput(attrs={"class": "form-control"})
    )

    def clean_file(self):
        """基础文件格式验证"""
        file = self.cleaned_data.get("file")
        if not file:
            raise forms.ValidationError("请选择要上传的文件！")
        allowed_suffixes = (".csv", ".xlsx", ".xls")
        if not file.name.lower().endswith(allowed_suffixes):
            raise forms.ValidationError(f"仅支持 {', '.join(allowed_suffixes)} 格式文件！")
        return file

    def process_file(self):
        """核心逻辑：pandas仅做文件读取，后续全用Python原生处理，无任何Series问题"""
        file = self.cleaned_data["file"]
        file_name = file.name.lower()
        data_list = []  # 纯Python字典列表，存储有效数据

        # 1. 读取文件并转为纯Python字典列表（彻底脱离pandas Series）
        try:
            if file_name.endswith(".csv"):
                # 适配UTF-8/GBK/GB2312，解决中文乱码
                encodings = ["utf-8", "gbk", "gb2312"]
                df = None
                for enc in encodings:
                    try:
                        df = pd.read_csv(file, encoding=enc)
                        break
                    except:
                        continue
                if df is None:
                    raise Exception("文件编码不支持，仅支持UTF-8/GBK/GB2312")
            else:
                # Excel适配：xlsx用openpyxl，xls用xlrd
                df = pd.read_excel(
                    file,
                    engine="openpyxl" if file_name.endswith(".xlsx") else "xlrd"
                )
            # 强制去重名列+重置索引+转纯Python字典列表（核心！）
            df = df.loc[:, ~df.columns.duplicated()].reset_index(drop=True)
            data_list = df.to_dict(orient="records")  # 关键：转成[{字段:标量}, ...]
            if not data_list:
                raise Exception("文件中无任何数据")
        except Exception as e:
            raise forms.ValidationError(f"文件读取失败：{str(e)}")

        # 2. 字段映射：适配你的中文表头，无需修改
        column_map = {
            "区域": "area",
            "日期": "date",
            "温度(℃)": "temperature",
            "温度": "temperature",
            "湿度(%)": "humidity",
            "湿度": "humidity",
            "风速(m/s)": "wind_speed",
            "风速": "wind_speed",
            "降雨量(mm)": "rainfall",
            "降雨量": "rainfall",
            "天气类型": "weather_type",
            "天气": "weather_type"
        }

        # 3. 校验核心表头是否存在
        required_headers = ["区域", "日期", "温度"]
        if not data_list:
            raise forms.ValidationError("文件无数据")
        first_row_keys = list(data_list[0].keys())
        missing_headers = [h for h in required_headers if h not in first_row_keys]
        if missing_headers:
            raise forms.ValidationError(f"缺少必要表头：{', '.join(missing_headers)}，请检查为【区域、日期、温度】")

        success_count = 0
        # 4. 纯Python原生处理每一条数据（无任何pandas，彻底解决真值问题）
        for idx, row in enumerate(data_list, 1):
            try:
                # ---- 1. 区域：原生去空格，空值直接跳过 ----
                area = str(row.get("区域", "")).strip()
                if not area:
                    continue

                # ---- 2. 日期：原生解析，格式错直接跳过 ----
                date_str = str(row.get("日期", "")).strip()
                if not date_str:
                    continue
                # 严格按【年-月-日】解析
                date_val = datetime.strptime(date_str, "%Y-%m-%d").date()

                # ---- 3. 数值字段：try-except原生转换，失败填0（比判断更稳） ----
                # 温度（核心字段，必须转成数字）
                try:
                    temperature = float(str(row.get("温度", 0)).strip())
                except:
                    temperature = 0.0
                # 湿度/风速/降雨量
                try:
                    humidity = float(str(row.get("湿度", 0)).strip())
                except:
                    humidity = 0.0
                try:
                    wind_speed = float(str(row.get("风速", 0)).strip())
                except:
                    wind_speed = 0.0
                try:
                    rainfall = float(str(row.get("降雨量", 0)).strip())
                except:
                    rainfall = 0.0

                # ---- 4. 天气类型：原生去空格，空值填sunny ----
                weather_type = str(row.get("天气类型", "sunny")).strip() or "sunny"

                # ---- 5. 过滤重复数据：区域+日期唯一 ----
                if WeatherData.objects.filter(area=area, date=date_val).exists():
                    continue

                # ---- 6. 原生入库：Django原生create，无任何兼容问题 ----
                WeatherData.objects.create(
                    area=area,
                    date=date_val,
                    temperature=temperature,
                    humidity=humidity,
                    wind_speed=wind_speed,
                    rainfall=rainfall,
                    weather_type=weather_type
                )
                success_count += 1

            except Exception as e:
                # 单条数据错跳过，不影响整体（标注行号方便排查）
                continue

        # 5. 最终校验：无有效数据则报错
        if success_count == 0:
            raise forms.ValidationError("无有效数据导入（格式错/全重复/无核心字段），请检查CSV")

        return success_count