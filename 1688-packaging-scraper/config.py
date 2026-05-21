"""
1688 包装厂家爆款信息采集工具 - 配置文件
"""
from pathlib import Path

# ── 项目路径 ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
REPORTS_DIR = OUTPUT_DIR / "reports"
LOGIN_STATE_DIR = BASE_DIR / "login_state"

# ── 1688 账号配置 ────────────────────────────────────────────────────
# 请填写您的1688账号信息（账号密码用于自动登录）
# 或者在首次运行时选择手动登录浏览器（推荐）
USERNAME = "温州冠创包装有限公司"        # 1688 账号（手机号/邮箱）
PASSWORD = "ALBB123456"        # 1688 密码

# ── 搜索关键词（定制包装厂家） ──────────────────────────────────────────
# 系统会自动轮流搜索这些关键词
PACKAGING_KEYWORDS = [
    "手提盒定制厂家",
    "礼品盒定制厂家",
    "精品包装盒定制",
    "化妆品包装盒定制",
    "珠宝首饰盒定制",
    "酒盒定制厂家",
    "茶叶包装盒定制",
    "礼品袋定制",
    "抽屉盒定制厂家",
    "天地盖盒定制",
    "精装盒定制",
    "皮盒定制厂家",
    "绒布盒定制",
    "展示盒定制",
    "包装内托定制",
    "纸卡定制",
    "吊牌定制",
    "礼盒包装厂家",
    "彩盒定制厂家",
    "高端礼品盒定制",
]


# ── 搜索配置 ──────────────────────────────────────────────────────────
MAX_PRODUCTS_PER_KEYWORD = 10    # 每个关键词采集的产品数
MAX_PRODUCTS_TOTAL = 50          # 每日总采集上限
HEADLESS = False                 # 是否无头模式（False能看到浏览器操作）
PAGE_LOAD_TIMEOUT = 60000        # 页面加载超时(ms)
SCROLL_PAUSE_TIME = 2.0          # 滚动后等待秒数

# ── 输出配置 ──────────────────────────────────────────────────────────
DOWNLOAD_IMAGES = True           # 是否下载主图到本地
IMAGE_MAX_WIDTH = 800            # 图片最大宽度
REPORT_TITLE = "1688 包装厂家爆款信息日报"

# ── 图片分析配置 ─────────────────────────────────────────────────────
ENABLE_IMAGE_ANALYSIS = True     # 是否启用图片视觉分析
ANALYSIS_IMAGE_MAX_SIZE = 800    # 分析时缩放到此尺寸加速
GENERATE_ANALYSIS_REPORT = True  # 是否生成分析报告章节
GENERATE_TRENDING_REPORT = True  # 是否生成爆款特征总结报告
