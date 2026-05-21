# 🏭 1688 包装厂家爆款信息采集工具 - 图片AI分析版

每天**北京时间 09:00** 自动搜索 1688 平台上的包装类厂家产品，采集爆款主图，**AI自动分析图片特点**（颜色、形状、材质、风格），并**自动分类归纳**生成可视化报告。

## ✨ 功能特点

### 采集功能
- 🤖 **自动登录** - 支持自动/手动登录 1688，保存登录状态复用
- 🔍 **智能搜索** - 自动搜索 20+ 包装类关键词（纸箱、礼盒、食品袋等）
- 📸 **主图下载** - 自动下载产品主图到本地
- 📋 **详情采集** - 提取产品标题、价格、规格参数、详情描述
- 🏷️ **自动分类** - 按纸箱/礼盒/食品袋/手提袋等类别自动归类

### 🎨 图片AI分析（新增）
- 🔴 **主色调分析** - K-means聚类识别主色调，判断暖/冷/中性色调
- 📐 **形状检测** - 轮廓识别：方盒型、圆筒型、袋型、异型
- 🧵 **材质识别** - 纸质/塑料/金属/布料分析，光泽度检测
- ✨ **烫金检测** - 自动识别烫金/烫银工艺
- 🏷️ **风格归类** - 简约白盒/高端奢华/自然环保/多彩设计等
- 🔥 **爆款特征总结** - 自动生成市场趋势分析

### 报告生成
- 📊 **HTML 图文报告** - 产品卡片 + 图片视觉分析区（含柱状图）
- 📊 **Excel 报表** - 产品总览表 + 分类汇总表
- 📊 **分析统计数据** - JSON格式，可导入BI工具

### 自动部署（新增）
- ⏰ **Windows 计划任务** - 每天 09:00 自动运行
- 🐙 **GitHub Actions** - 云端每天自动采集 + 分析
- 📤 **自动提交报告** - 分析结果自动 push 到仓库

## 📁 项目结构

```
1688-packaging-scraper/
├── config.py                 # 配置文件（关键词、账号、采集参数）
├── login.py                  # 1688 登录模块
├── scraper.py                # 1688 信息采集模块
├── image_analyzer.py         # 🆕 AI图片分析模块（OpenCV + PIL）
├── reporter.py               # HTML + Excel 报告生成（含分析报告）
├── main.py                   # 主入口脚本（集成分析流程）
├── batch_analyze.py          # 🆕 批量图片分析工具（独立运行）
├── setup_scheduler.py        # Windows 计划任务设置
├── run_scheduled.ps1         # PowerShell 启动脚本
├── requirements.txt          # Python 依赖
├── .gitignore
├── .github/workflows/
│   └── daily_scrape.yml      # 🆕 GitHub Actions 每日工作流
├── login_state/              # 登录状态缓存
│   └── 1688_login.json
└── output/
    ├── images/               # 下载的产品主图
    ├── products_YYYY-MM-DD.json          # 原始采集数据
    ├── analyzed_YYYY-MM-DD.json          # 🆕 含分析结果的数据
    └── reports/
        ├── report_YYYY-MM-DD.html        # HTML 报告（含视觉分析）
        ├── report_YYYY-MM-DD.xlsx        # Excel 报表
        └── analysis_YYYY-MM-DD.json      # 🆕 分析统计 JSON
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 配置账号

编辑 `config.py`，填写您的1688账号：

```python
USERNAME = "您的1688账号（手机号/邮箱）"
PASSWORD = "您的1688密码"
```

> 💡 **推荐首次手动登录**：不填账号密码时，脚本会打开浏览器让您手动扫码登录，并保存登录状态。

### 3. 首次运行

```bash
python main.py
```

首次运行会打开浏览器，请在浏览器中手动登录1688，成功后脚本自动保存登录状态并开始采集和分析。

### 4. 仅执行图片分析（无需爬取）

若已有采集数据，可直接分析图片：

```bash
python batch_analyze.py
```

### 5. 设置 Windows 定时任务

```bash
python setup_scheduler.py
```

然后按提示以管理员身份运行命令创建计划任务。

## 🐙 GitHub 云端自动运行

### 步骤一：创建 GitHub 仓库

```bash
# 在项目目录初始化 git
cd 1688-packaging-scraper
git init
git add .
git commit -m "初始化：1688包装采集+AI图片分析"
# 在 GitHub 新建仓库后：
git remote add origin https://github.com/你的用户名/1688-packaging-scraper.git
git push -u origin main
```

### 步骤二：配置 Secrets（仓库 Settings > Secrets and variables > Actions）

| Secret 名称 | 说明 | 是否必须 |
|------------|------|---------|
| `USERNAME` | 1688 账号 | 推荐 |
| `PASSWORD` | 1688 密码 | 推荐 |
| `LOGIN_STATE_JSON` | 登录状态 JSON（本地执行 `save_login.py` 后，将 `login_state/1688_login.json` 内容粘贴） | 可选，更稳定 |

### 步骤三：启用 Actions

- 仓库 Actions 标签页会显示 `每日1688包装爆款采集+图片分析` 工作流
- 默认每天北京时间 09:00 自动运行
- 也可以手动触发（点 `Run workflow`）

### 步骤四：查看结果

每次运行后：
- HTML 报告被自动提交到仓库 `output/reports/` 目录
- 可直接在 GitHub 上预览 HTML 报告（用 `https://htmlpreview.github.io/?https://github.com/你的用户名/1688-packaging-scraper/blob/main/output/reports/report_2026-05-21.html`）
- 分析统计 JSON 也可在仓库中查看

## ⚙️ 自定义配置

在 `config.py` 中可调整的关键参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `PACKAGING_KEYWORDS` | 搜索关键词列表 | 20个包装类关键词 |
| `MAX_PRODUCTS_PER_KEYWORD` | 每个关键词采集数 | 10 |
| `MAX_PRODUCTS_TOTAL` | 每日总采集上限 | 50 |
| `DOWNLOAD_IMAGES` | 是否下载图片 | True |
| `ENABLE_IMAGE_ANALYSIS` | 是否启用图片AI分析 | True |
| `GENERATE_ANALYSIS_REPORT` | 是否在HTML报告中生成分析区 | True |

## 🎨 图片AI分析算法说明

| 分析维度 | 使用的算法 | 输出内容 |
|---------|-----------|---------|
| 主色调 | K-means 聚类 (k=5) + HSV | 前5种主色的名称、比例、色温 |
| 形状 | Canny边缘检测 + 轮廓近似 | 方盒型/圆筒型/异型、对称性、圆角 |
| 材质 | 纹理方差 + 高光检测 + HSV | 纸质/塑料/金属、光泽度、烫金检测 |
| 风格归类 | 综合决策树 | 简约白盒/高端奢华/自然环保/多彩设计等 |
| 趋势特征 | 规则引擎 | "烫金工艺提升档次感"、"简约设计符合现代审美"等 |

## 📝 输出示例

HTML 报告中新增的 **图片视觉分析** 区域包含：
- 📊 视觉风格分布（柱状比例图）
- 🔥 爆款特征趋势（热度柱状图）
- 🏷️ 设计风格标签云
- 🎨 主色调分布
- 🧵 材质分析
- 📐 形状分析

## 📅 更新日志

### v2.0 (2026-05-21)
- ✨ 新增 `image_analyzer.py` - AI图片视觉分析模块
- ✨ 新增 `batch_analyze.py` - 独立批量分析工具
- ✨ 更新 `reporter.py` - HTML报告集成视觉分析图表
- ✨ 创建 `.github/workflows/daily_scrape.yml` - GitHub Actions自动部署
- ✨ 创建 `requirements.txt` - 统一依赖管理
- 🔧 优化 `main.py` - 集成图片分析流水线
- 📝 更新 README - 完善使用说明
