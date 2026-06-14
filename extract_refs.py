# -*- coding: utf-8 -*-
from pathlib import Path
from pypdf import PdfReader

files = [
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\3901326E70F248C73C96BCE4426A5861.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\applsci-12-01161-v2.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\College of Computer Science Researcher Provides New Data on Machine Learning (Sh (1).pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\College of Computer Science Researcher Provides New Data on Machine Learning (Sh.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\Optimized Demand Forecasting for Bike Sharing Stations Through Multi Method Fusi.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\Predicting travel demand of a bike sharing system using graph convolutional neur.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\qy_Real-Time Forecasting of Dockless Scooter-Sharing Demand  A Spatio-Temporal M.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\The Impact of Weather on Shared Bikes.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\北京市共享单车出行的时空规律与需求预测研究.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\城市公共自行车智能需求预测及调度管理系统.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\基于深度学习的共享单车需求预测及调度方法研究.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\基于时空图的共享单车流量预测.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\基于长短期记忆网络的共享单车真实需求预测方法.pdf",
    r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\引用文献\一种基于Voronoi图的混合公共自行车调度需求预测方法.pdf",
]

out = Path(r"E:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\BSDP\refs_extract.txt")
with out.open('w', encoding='utf-8') as f:
    for path in files:
        f.write('=' * 80 + '\n')
        f.write(Path(path).name + '\n')
        try:
            reader = PdfReader(path)
            text = ''
            for page in reader.pages[:3]:
                text += (page.extract_text() or '') + '\n'
            f.write(text[:12000])
        except Exception as e:
            f.write('ERROR: ' + repr(e))
        f.write('\n\n')
print(out)
