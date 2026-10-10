# 评委快速运行

本仓库提供真实业务前后端源码。GitHub 链接用于下载项目；运行后在评委自己的电脑打开网页。独立讲解 HTML 和讲解视频不属于业务项目，旧 `/demo`、`/materials` 跳转至 `/dashboard`。

## 1. 准备环境和文件

- Python 3.11 或 3.12、Git、Node.js 22.12+。Windows 使用 PowerShell；Linux/macOS 使用相应虚拟环境激活命令。
- 一个可用的 DeepSeek API Key。只填写到自己的 `.env`，不要填写在前端、截图或提交到 GitHub。
- 完整监控需要项目兼容的已训练检测权重 `helmet_head_person_s.pt`，放在 `perception/weights/`。默认加载器为项目的 YOLOv5 适配器，不保证任意同名权重可用。
- 把视频压缩包解压到 `runs/input/videos/`，不是把 ZIP 当作摄像头。规范解压到 `knowledge/standard/`。安全帽图片和测试前后图片可以作为离线核验素材保留；它们不是视频源，也不会自动生成业务事件。
- 规范检索还需要完整的 `bge-small-zh-v1.5` 本地 embedding 模型目录（模型权重、配置及 tokenizer 文件），放在 `runs/models/bge-small-zh-v1.5/`。这与检测模型不同。该路线只使用 DeepSeek 对话 Key；若改用 DashScope embedding，须另配它自己的 Key。

这些私有文件、模型、API Key 和运行数据库不随仓库发布。首次运行是空业务数据，需先接入视频再产生事件。

## 2. 安装和配置

```powershell
git clone https://github.com/jjc303/civil_engineering_agent.git
cd civil_engineering_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-agent.txt
python -m scripts.start_review --init
```

Linux/macOS 将激活命令替换为 `source .venv/bin/activate`。若 Windows 禁止激活脚本，可直接用 `.\.venv\Scripts\python.exe` 替代后续 `python`，不需要修改全局执行策略。Linux 的 PDF 导出使用 WeasyPrint，需要其系统依赖及中文字体；Windows 导出使用系统宋体和 ReportLab。

编辑新生成的 `.env`，填写 `AGENT_LLM_API_KEY`，按自己的账号选择可用的 `AGENT_LLM_MODEL`。初始化会生成内部令牌及加密 Key，并拒绝覆盖已有 `.env`。默认 SQLite 无需安装 MySQL。若已有部署配置，先按 `.env.review.example` 核对，不能覆盖原数据库和令牌。

如果已准备完整 embedding 模型与规范，把 `AGENT_RAG_ENABLED` 改为 `true`。首批索引需等待，在学习中心检查解析与入库状态；纯扫描 PDF 需要先 OCR，不会因为文件上传就自动获得可检索文本。规范版本有效性须人工核实。

## 3. 启动网页

只查看页面、问答和业务管理（不启动 CV）：

```powershell
python -m scripts.start_review --build
```

已放好检测权重与视频，完整运行：

```powershell
python -m scripts.start_review --build --with-cv
```

打开 **http://127.0.0.1:8000/dashboard**。首次 `--build` 会执行 `npm ci` 和生产构建，前后端同端口、真实 API、模拟数据关闭。后续没有修改前端可省略 `--build`。终端须保持运行；Ctrl+C 只停止本命令启动的进程。端口被占用会拒绝启动，不会停止已有服务。改端口时同时修改 `.env` 中 Agent 地址、CORS 和培训公开地址。

完整启动会注册一个本地 CV 节点。重复启动保留既有节点，不能恢复丢失的 CV Token；若凭据或控制地址改变，请在“摄像头与节点”中核对节点配置。脚本不自动创建摄像头或覆盖已有数据。

## 4. 按业务闭环查看

1. **摄像头与节点**：确认 `review-local` 在线，新增文件摄像头，选择 `runs/input/videos/` 下的视频。
2. **区域标定**：选择摄像头、绘制并保存危险区域。需要区域告警时应先完成这一步。
3. **现场监控**：启动摄像头，查看视频及实际识别状态。CPU 推理速度取决于电脑配置，建议先开一路。
4. **违规事件**：查看抓拍、发生时间、区域与处理状态，复核误报。
5. **安全智能助手**：提问“汇总最近的安全帽违规”“查询未完成整改任务”。问答会调用实际接口；天气等外部信息取决于对应服务是否可用，不能用生成文字代替事实。
6. **整改任务**：由页面或助手提出操作，经人工确认创建；完成与关闭需实际提交，不能把提议当作已执行。
7. **学习中心**：核对规范入库状态，按已有事件生成、审阅和确认安全报告，再生成并发布培训。查看引用页码及导出 PDF。
8. **培训反馈**：打开发布后的学习链接、答题并查看统计。默认链接供本机使用；跨设备访问需另行部署并设置 `LEARNING_PUBLIC_BASE_URL` 为可访问地址。

出现空列表时先检查是否已接入并启动视频；出现降级提示时查看终端和 API 服务状态，不能把降级答案当作正常模型回复。视频循环回放的事件计数不代表真实人数、识别准确率或安全改善。

此启动方案仅监听本机，不包含公网发布、身份访问控制、HTTPS 或云端托管。需要外网展示时另行部署业务服务并配置访问保护。
