from django import forms
from .models import WeatherData
import pandas as pd
from datetime import datetime


class WeatherDataUploadForm(forms.Form):
    """天气数据上传表单（毕设“多源数据集成”核心表单）"""
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
        """验证文件格式，避免上传非CSV/Excel文件"""
        file = self.cleaned_data.get("file")
        if not file.name.endswith((".csv", ".xlsx", ".xls")):
            raise forms.ValidationError("仅支持CSV、XLSX、XLS格式的文件！")
        return file

    def process_file(self):
        """解析文件并批量入库（核心逻辑）"""
        file = self.cleaned_data["file"]
        # 读取文件（自动适配CSV/Excel）
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file, encoding="utf-8")
            else:
                df = pd.read_excel(file)
        except Exception as e:
            raise forms.ValidationError(f"文件解析失败：{str(e)}")

        # 字段映射（适配常见的表头命名，你可以根据自己的测试文件调整）
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
        # 重命名列，只保留需要的字段
        df = df.rename(columns=column_map)[list(column_map.values())]

        # 数据清洗：转换日期格式、处理空值
        df["date"] = pd.to_datetime(df["date"]).dt.date  # 转为date类型
        df = df.fillna({"rainfall": 0.0, "weather_type": "sunny"})  # 空值填充

        # 批量入库（跳过重复数据，避免unique_together报错）
        weather_list = []
        for _, row in df.iterrows():
            if not WeatherData.objects.filter(area=row["area"], date=row["date"]).exists():
                weather_list.append(WeatherData(
                    area=row["area"],
                    date=row["date"],
                    temperature=row["temperature"],
                    humidity=row["humidity"],
                    wind_speed=row["wind_speed"],
                    rainfall=row["rainfall"],
                    weather_type=row["weather_type"]
                ))
        WeatherData.objects.bulk_create(weather_list)
        return len(weather_list)  # 返回成功导入的条数