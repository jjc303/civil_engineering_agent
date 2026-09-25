# Smart_Construction (智能工地安全帽与危险区域检测系统) 详细总结文档

## 1. 项目概述与背景

### 1.1 项目定位
**Smart_Construction** 是一个面向**土木工程与智能施工现场（Smart Construction Site）安全监控**的计算机视觉应用系统。该系统基于深度学习目标检测算法，聚焦于施工现场最核心的两大安全生产隐患：
1. **施工人员安全防护装备佩戴合规性检测**：重点检测工人是否规范佩戴安全帽（Safety Helmet）。
2. **危险作业区域越界与人员入侵防范**：针对临边洞口、吊装作业区、深基坑边缘等高危区域建立数字“电子围栏”，实时监测未授权人员的闯入行为。

### 1.2 解决的工程痛点
- **传统人工巡查盲区大、频次低**：施工场地广阔、人员流动性强，专职安全员无法实现7×24小时全覆盖监督。
- **事后取证滞后，缺乏实时预警**：普通监控摄像头仅用于事后调阅，缺乏实时的违规识别与越界声光预警机制。
- **标注数据源单一与类别缺失**：公开的安全帽数据集往往缺少完整的人体目标标注，导致无法建立“人-头-帽”联合防范上下文关联。

---

## 2. 系统技术架构与工作流程

### 2.1 整体技术栈
- **核心算法框架**：PyTorch (`1.5.x`)、YOLOv5 (`v2.x`)
- **计算机视觉库**：OpenCV (`4.5.x`)、Pillow
- **GUI 交互界面**：PyQt5 (`5.15.x`)、PyQtChart (用于 GPU 动态波形监控)
- **系统硬件监控**：GPUtil (实时获取 GPU 利用率与显存)
- **部署与格式转换**：ONNX、TorchScript、PyInstaller (Windows exe 打包)

### 2.2 系统架构拓扑图

```mermaid
flowchart TD
    subgraph DataEngine["数据处理引擎 (Data Engineering)"]
        D1["开源数据集 (SHWD / VOC)"] --> D2["格式清洗与归一化 (gen_head_helmet.py)"]
        D3["YOLOv5x 预训练大模型"] --> D4["自动推理伪标签 (person)"]
        D2 --> D5["标签融合 (merge_data.py)"]
        D4 --> D5
        D5 --> D6["标准化数据集 (custom_data.yaml)"]
    end

    subgraph ModelEngine["模型训练与推理层 (Model Engine)"]
        D6 --> M1["模型结构配置 (custom_yolov5.yaml)"]
        M1 --> M2["网络训练与评估 (train.py / test.py)"]
        M2 --> M3["权重文件 (weights/*.pt)"]
        M3 --> M4["模型导出 (models/export.py -> ONNX/TorchScript)"]
    end

    subgraph BusinessLogic["核心业务应用 (Applications)"]
        M3 --> A1["通用目标检测 (detect.py)"]
        M3 --> A2["危险区域入侵预警 (area_detect.py)"]
        A2 --> A21["电子围栏多边形解析 (JSON)"]
        A2 --> A22["PNPoly 射线法点面包含判定"]
    end

    subgraph Presentation["可视化客户端系统 (GUI & Monitoring)"]
        M3 --> V1["可视化推理核心 (detect_visual.py)"]
        V1 --> V2["PyQt5 多线程主界面 (visual_interface.py)"]
        V2 --> V21["双路视频/图片同步对比展示"]
        V2 --> V22["多线程异步日志上报与 FPS 统计"]
        V2 --> V23["GPUtil + PyQtChart 显卡状态实时曲线"]
    end
```

---

## 3. 核心功能与模块原理深度剖析

### 3.1 目标分类体系
系统重定义并训练了 3 个检测类别：
- `person` (0)：人体整体目标，用于统计在场人数及作为危险区域闯入判断的主体。
- `head` (1)：未佩戴安全帽的头部，作为**违规安全隐患**目标重点报警。
- `helmet` (2)：规范佩戴安全帽的头部，作为合规施工目标。

### 3.2 危险区域入侵与电子围栏检测 (`area_detect.py` & `utils/custom_util.py`)

#### 1) 危险多边形区域标注与解析
系统支持使用标注工具（如精灵标注助手）在图像上标注任意凸/凹多边形危险区域，并将坐标保存为 JSON 格式（位于 `area_dangerous/area_labels/*.json`）。
JSON 数据结构提取关键顶点集合：
```json
{
  "outputs": {
    "object": [
      {
        "name": "dangerous",
        "polygon": {
          "x1": 402, "y1": 234,
          "x2": 497, "y2": 182,
          ...
          "xn": ..., "yn": ...
        }
      }
    ]
  }
}
```
`load_poly_area_data(img_name)` 函数自动读取对应图像的 JSON 标注，组装成二维顶点数组 `[[x1,y1], [x2,y2], ..., [xn,yn]]`。

#### 2) PNPoly (Point Inclusion in Polygon) 射线交叉判别算法
在 `custom_util.py` 中实现了经典的 **PNPoly** 算法（由 W. Randolph Franklin 提出），通过计算测试点向某一方向发射的水平射线与多边形各边相交次数的奇偶性，判断点是否在多边形内部：
```python
def is_poi_in_poly(pt, poly):
    nvert = len(poly)
    vertx = [item[0] for item in poly]
    verty = [item[1] for item in poly]
    testx, testy = pt[0], pt[1]

    j = nvert - 1
    res = False
    for i in range(nvert):
        if (verty[j] - verty[i]) == 0:
            j = i
            continue
        # 计算水平射线与边 (i, j) 的交点 x 坐标
        x = (vertx[j] - vertx[i]) * (testy - verty[i]) / (verty[j] - verty[i]) + vertx[i]
        if ((verty[i] > testy) != (verty[j] > testy)) and (testx < x):
            res = not res
        j = i
    return res
```

#### 3) 人员入侵告警过滤逻辑
在推理循环中：
1. 提取所有预测为 `person` 的边界框坐标 $(x_1, y_1, x_2, y_2)$；
2. 计算人体包围框中心点坐标 $c_x = x_1 + \frac{w}{2}, c_y = y_1 + \frac{h}{2}$；
3. 将 $(c_x, c_y)$ 输入 `person_in_poly_area_dangerous()` 进行判定；
4. **过滤机制**：只有中心点位于危险区域多边形内部的人体，才会被绘制高亮告警框；位于危险区域外的普通作业人员则予以忽略，多边形危险区域则以醒目的红色线框标注。

---

### 3.3 数据工程与多源标签融合机制 (`data/gen_data/`)

#### 1) 坐标系归一化转换 (`gen_head_helmet.py`)
将标准 VOC 格式的 XML 绝对像素坐标 $(x_1, y_1, x_2, y_2)$ 转换为 Darknet/YOLO 格式的归一化中心点与长宽 $(x_c, y_c, w, h) \in [0, 1]$：
$$x_c = \frac{x_1 + x_2}{2 \times W}, \quad y_c = \frac{y_1 + y_2}{2 \times H}, \quad w = \frac{x_2 - x_1}{W}, \quad h = \frac{y_2 - y_1}{H}$$

#### 2) 基于大模型的弱监督伪标签补充 (`merge_data.py`)
原始开源安全帽数据集（如 SHWD）中的 XML 标注多将头部标注为 `person`，缺少真正的人体身体标注。本项目提出创新的半自动打标方案：
1. 先利用在大规模通用数据集（如 COCO）上训练的高精度大模型 `yolov5x.pt` 对未标定人体的图像执行推理：
   ```bash
   python detect.py --save-txt --source <数据集图片路径> --weights ./weights/yolov5x.pt
   ```
2. 推理结果中自动筛选出属于类别 0 (`person`) 的检测框；
3. 运行 `merge_data.py` 将提取出的 `person` 框追加回原始的安全帽标签文件中，实现无需人工重复标注即可构建三类别联合数据集。

---

### 3.4 现代化 PyQt5 可视化交互软件 (`visual_interface.py` & `detect_visual.py`)

#### 1) 稳健的多线程高响应架构
为了避免模型推理和多媒体解码等耗时任务造成 GUI 界面卡死或未响应，系统采用了基于 Qt 信号与槽的**多线程隔离设计**：
- **GUI 主线程 (`MainWindow`)**：负责渲染主窗口界面、响应按钮事件、驱动图表定时器。
- **模型推理线程 (`PredictHandlerThread`)**：在独立工作线程中运行 `YOLOPredict.detect()`，负责图像帧的预处理、CUDA 推理、NMS 过滤及结果落盘。
- **信息流中继线程 (`PredictDataHandlerThread`)**：实时捕获推理过程中的阶段信息、耗时和识别类别，通过 `pyqtSignal(str)` 发送到主窗口的文本日志控件中。

#### 2) 关键功能特性
- **双媒体播放器同播系统**：采用 `QMediaPlayer` + `QVideoWidget`，左侧显示原始施工视频/图片，右侧显示模型推理渲染后的视频/图片，支持同步播放与暂停联动。
- **动态帧率计算与进度条反馈**：解析推理输出日志，实时计算当前处理的 `FPS`（$1 / t_{cost}$）并驱动百分比进度条。
- **GPU 资源实时动态监控**：通过 `GPUtil` 模块和 `QTimer` 定时器以 1Hz 频率轮询显卡核心负载和显存占比，使用 `QtChart.QSplineSeries` 绘制随时间推移的显卡利用率平滑曲线。
- **PyInstaller 打包兼容性优化**：针对 PyTorch 与 PyInstaller 打包时容易出现的 `Can't get source for jit` 错误，在源码入口通过 Monkey-Patching 修正了 `torch.jit.script` 与 `torch.jit.script_method`。

---

## 4. 模型性能指标对比

基于开源数据集并在三类目标（`person`, `head`, `helmet`）上分别训练 YOLOv5 不同规模的主干网络，在测试集上的表现如下：

| 网络规模 | 训练轮次 (Epoch) | 类别 (Class) | 精确率 (Precision) | 召回率 (Recall) | 平均精度 (mAP@0.5) | 综合推荐部署场景 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **YOLOv5s** | 50 | **总体 (All)** | **0.884** | **0.899** | **0.888** | 边缘计算盒子、工控机、端侧 IPC (算力受限环境) |
| | | 人体 (person) | 0.846 | 0.893 | 0.877 | |
| | | 头部 (head) | 0.889 | 0.883 | 0.871 | |
| | | 安全帽 (helmet)| 0.917 | 0.921 | 0.917 | |
| **YOLOv5m** | 100 | **总体 (All)** | **0.886** | **0.915** | **0.901** | 工地现场中高端工作站、边缘服务器 (平衡型首选) |
| | | 人体 (person) | 0.844 | 0.906 | 0.887 | |
| | | 头部 (head) | 0.900 | 0.911 | 0.900 | |
| | | 安全帽 (helmet)| 0.913 | 0.929 | 0.916 | |
| **YOLOv5l** | 100 | **总体 (All)** | **0.892** | **0.919** | **0.906** | 智慧工地云端服务器、高精度质检中心 |
| | | 人体 (person) | 0.856 | 0.914 | 0.897 | |
| | | 头部 (head) | 0.893 | 0.913 | 0.901 | |
| | | 安全帽 (helmet)| 0.927 | 0.929 | 0.919 | |

> **指标分析**：
> 1. 三种规模模型对 **安全帽（helmet）** 的识别精度最高（mAP@0.5 超过 0.917~0.919），表明模型能敏锐捕捉安全帽的颜色、轮廓特征；
> 2. YOLOv5m 相比 YOLOv5s 在总体 mAP@0.5 上提升了 1.3%，尤其在未佩戴安全帽的头部（head）召回率提升显著；
> 3. YOLOv5l 整体表现最为稳定，但模型参数量较大，推荐在云端大批量视频汇聚处理时使用。

---

## 5. 项目代码结构与文件索引

```text
Smart_Construction/
├── area_dangerous/                  # 危险区域检测示例样本与标签
│   ├── 1.jpg, 2.jpg                 # 测试施工场地图片
│   └── area_labels/                 # 对应的多边形区域 JSON 标注文件
├── data/
│   ├── custom_data.yaml             # 数据集配置（类别数、标签名称、路径）
│   └── gen_data/
│       ├── gen_head_helmet.py       # VOC XML 转 YOLO 标注脚本
│       └── merge_data.py            # 伪标签合并脚本（整合人体类别）
├── doc/                             # 项目图片与可视化工具教程
│   └── Visualize_Tool_Tutorial.md   # 可视化工具使用说明文档
├── models/
│   ├── custom_yolov5.yaml           # 本项目定制的模型结构配置 (nc=3)
│   ├── common.py, yolo.py           # YOLOv5 核心网络组件与 Head 定义
│   └── export.py                    # 模型导出为 ONNX / TorchScript 脚本
├── UI/
│   ├── icon/                        # GUI 界面图标素材 (play, pause, icon.ico)
│   ├── main_window.ui               # Qt Designer 原始界面设计文件
│   └── main_window.py               # pyuic5 编译生成的 UI 布局代码
├── utils/
│   ├── custom_util.py               # 电子围栏算法、多边形加载与包含判定
│   ├── datasets.py                  # 数据加载、图像增强与流媒体处理
│   ├── torch_utils.py, utils.py     # 矩阵计算、NMS、绘图等通用工具
│   └── activations.py               # 激活函数定义
├── area_detect.py                   # 危险区域入侵检测主程序
├── detect.py                        # 标准单图/视频/网络流目标检测推理主程序
├── detect_visual.py                 # 面向 GUI 界面的封装推理类 (YOLOPredict)
├── visual_interface.py              # PyQt5 可视化桌面端主程序
├── train.py                         # 模型训练启动入口
├── test.py                          # 模型测试与性能评估入口
└── requirements.txt                 # 项目 Python 依赖库列表
```

---

## 6. 快速开始与使用指南

### 6.1 运行环境搭建
推荐在 Python 3.7+ 及 PyTorch 1.5+ 环境下运行：
```bash
# 1. 建议使用 conda 新建虚拟环境
conda create -n smart_construction python=3.8 -y
conda activate smart_construction

# 2. 安装核心依赖
pip install -r requirements.txt
```

### 6.2 模型训练
1. 准备按 YOLO 格式存放的数据集，并在 `data/custom_data.yaml` 中配置好训练集与验证集路径。
2. 运行训练脚本：
```bash
python train.py --img 640 \
                --batch 16 \
                --epochs 50 \
                --data ./data/custom_data.yaml \
                --cfg ./models/custom_yolov5.yaml \
                --weights ./weights/yolov5s.pt
```
训练过程生成的最佳权重和评估曲线将保存在 `./runs/exp*/weights/best.pt`。

### 6.3 运行常规检测 (`detect.py`)
支持本地图片、本地视频、目录批量测试以及 RTSP/HTTP 监控摄像头网络流：
```bash
# 检测本地图片
python detect.py --source ./data/images/test.jpg --weights ./weights/helmet_head_person_s.pt

# 检测 RTSP 监控视频流
python detect.py --source "rtsp://admin:password@192.168.1.100/live" --weights ./weights/helmet_head_person_s.pt
```
推理结果将默认自动保存在 `inference/output/` 目录下。

### 6.4 运行危险区域越界检测 (`area_detect.py`)
```bash
python area_detect.py --source ./area_dangerous --weights ./weights/helmet_head_person_s.pt
```
程序将自动扫描 `area_dangerous/area_labels/` 下对应的 JSON 文件，绘制危险区域并针对区域内的工人报警。

### 6.5 运行可视化交互界面 (`visual_interface.py`)
1. 确保在 `weights/` 目录下放置所需测试的 `.pt` 权重文件（保留一个激活权重）。
2. 启动 GUI 应用：
```bash
python visual_interface.py
```
3. 在软件界面中点击 **Import** 导入待检测的现场视频或施工照片；
4. 点击 **Predict** 启动检测并实时查看推理 FPS 与进度；
5. 推理完成后点击 **Play** 实现原始视频与标注视频画面的双路同步回放。

### 6.6 导出部署与打包
- **导出为 ONNX 模型**：
  ```bash
  python ./models/export.py --weights ./weights/helmet_head_person_s.pt --img 640 --batch 1
  ```
- **使用 PyInstaller 编译为 Windows 独立执行程序**：
  ```bash
  pyinstaller -D -w --icon=./UI/icon/icon.ico visual_interface.py
  ```

---

## 7. 架构优势、现存局限性及进阶演进建议

### 7.1 系统亮点与优势
1. **业务结合度高**：紧扣“智慧工地”实景需求，不仅仅停留在模型识别层面，更打通了从“识别模型”到“业务逻辑（危险区域过滤）”再到“桌面端交付产品（PyQt GUI）”的完整闭环。
2. **多源数据融合思路巧妙**：通过大模型弱监督推理自动弥补开源数据集中人体标签缺失的问题，大幅降低了工程落地前期的数据标注成本。
3. **软硬件协同设计良好**：在可视化端集成了实时显存与 GPU 算力监测，便于工程部署时直观评估边缘端设备的负载压力。

### 7.2 局限性与改进空间
1. **代码跨平台兼容性**：
   - 现状：部分工具脚本（如 `custom_util.py`, `merge_data.py`）中硬编码了 Windows 风格的双反斜杠路径（如 `\\`）和绝对盘符路径（如 `E:\AI_Project\...`）。
   - 优化：应全面采用 Python 标准库 `pathlib.Path` 或 `os.path.join` 替代硬编码路径，以保障 Linux 服务器与 Docker 容器环境无缝运行。
2. **入侵判定几何精度**：
   - 现状：当前采用包围框几何中心点 $(c_x, c_y)$ 判定人员是否处于多边形内。若工人身体倾斜或下半身已越界但中心点仍在外部，可能导致漏报。
   - 优化：推荐改进为**脚底触地点判定**（取包围框底边中点 $(c_x, y_2)$）或计算人体框与多边形掩膜的重叠面积比例（IOU Overlap Threshold）。
3. **缺少多目标追踪（MOT）**：
   - 现状：目前按单帧独立检测处理，无法掌握人员运动轨迹。
   - 优化：可集成 **ByteTrack** 或 **DeepSORT** 算法，跟踪进入危险区域人员的停留时长、移动速度，实现从“单帧瞬时报警”到“连续行为异常分析”（如高空逗留预警、徘徊预警）的升级。
4. **模型框架代际演进**：
   - 现状：基于早期 YOLOv5 v2.x 版本构建。
   - 优化：后续可平滑迁移至 YOLOv8 / YOLOv11 / RT-DETR 等具备 Anchor-Free 架构与更好小目标检测能力的现代检测器，进一步提升工地复杂遮挡、强逆光条件下的检测准确率。
