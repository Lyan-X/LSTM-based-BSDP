from django.shortcuts import render, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import WeatherDataUploadForm  # 导入天气数据上传表单

# ========== 关键修改1：补充WeatherData导入 ==========
from .models import BikeRideData, WeatherData
from .services.data_service import data_service


@login_required
def data_upload(request):
    """
    数据上传界面（任务书"公开数据集导入+本地数据录入"核心功能）
    支持Excel/CSV文件上传，自动清洗后入库
    """
    # 处理POST请求（文件上传）
    if request.method == 'POST':
        # 1. 检查是否有文件上传
        if 'data_file' not in request.FILES:
            messages.error(request, "请选择要上传的Excel/CSV文件")
            return redirect('data_process:data_upload')

        file = request.FILES['data_file']

        # 2. 使用数据服务验证文件
        valid, message = data_service.validate_file(file)
        if not valid:
            messages.error(request, message)
            return redirect('data_process:data_upload')

        # 3. 使用数据服务读取文件
        df, error = data_service.read_file(file)
        if error:
            messages.error(request, error)
            return redirect('data_process:data_upload')

        # 4. 使用数据服务处理骑行数据
        count, error = data_service.process_ride_data(df, request.user)
        if error:
            messages.error(request, f"处理骑行数据失败：{error}")
            return redirect('data_process:data_upload')

        if count > 0:
            messages.success(request, f"成功导入{count}条清洗后的骑行数据")
            return redirect(f'/data/upload/?success=1&count={count}')
        else:
            messages.warning(request, "清洗后无有效数据，请检查文件内容")
            return redirect('data_process:data_upload')

    # GET请求：返回上传页面
    return render(request, 'data_process/data_upload.html')


@login_required
def data_list(request):
    """
    数据仓库列表（支持筛选、查看）
    仅显示当前登录用户上传的数据
    """
    # 查询当前用户的骑行数据，按上传时间倒序排列
    data_list = BikeRideData.objects.filter(upload_user=request.user).order_by('-id')
    # 传递数据到模板
    context = {
        'data_list': data_list,
        'total_count': data_list.count()  # 数据总数，便于页面展示
    }
    return render(request, 'data_process/data_list.html', context)


@login_required
def weather_data_upload(request):
    """天气数据上传视图（毕设"数据上传模块"核心接口）"""
    if request.method == "POST":
        if 'weather_file' not in request.FILES:
            messages.error(request, "请选择要上传的Excel/CSV文件")
            return redirect("data_process:weather_upload")

        file = request.FILES['weather_file']

        # 使用数据服务验证文件
        valid, message = data_service.validate_file(file)
        if not valid:
            messages.error(request, message)
            return redirect("data_process:weather_upload")

        # 使用数据服务读取文件
        df, error = data_service.read_file(file)
        if error:
            messages.error(request, error)
            return redirect("data_process:weather_upload")

        # 使用数据服务处理天气数据
        count, error = data_service.process_weather_data(df)
        if error:
            messages.error(request, f"处理天气数据失败：{error}")
            return redirect("data_process:weather_upload")

        if count > 0:
            messages.success(request, f"✅ 成功导入{count}条天气数据！")
        else:
            messages.warning(request, "清洗后无有效数据，请检查文件内容")
        
        return redirect("data_process:weather_upload")  # 上传后刷新页面
    else:
        form = WeatherDataUploadForm()

    # 传入已有的天气数据，方便查看（可选，提升体验）
    weather_list = WeatherData.objects.all().order_by("-date")[:10]
    return render(
        request,
        "data_process/weather_upload.html",
        {"form": form, "weather_list": weather_list}
    )


@login_required
def data_manage_view(request):
    """
    数据管理页面视图
    包含初始数据导入、数据闭环日志、滚动窗口数据预览三个标签页
    """
    # 传递基础数据到模板
    context = {
        'page_title': '数据管理 - 共享单车需求预测系统'
    }
    return render(request, 'data_process/data_manage.html', context)