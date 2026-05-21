"""
批量图片分析工具 - 对已下载的图片批量执行视觉分析
无需重新爬取，可直接分析 output/images/ 中的图片
"""
import json
import sys
from pathlib import Path
from datetime import datetime

import config


def find_existing_data() -> list:
    """查找最近的 products JSON 数据"""
    output_files = sorted(config.OUTPUT_DIR.glob("products_*.json"))
    if not output_files:
        print("⚠️  未找到产品数据文件 (output/products_*.json)")
        return []
    latest = output_files[-1]
    print(f"📂 加载数据：{latest}")
    data = json.loads(latest.read_text(encoding="utf-8"))
    print(f"   共 {len(data)} 条产品记录")
    return data


def main():
    print("=" * 60)
    print("  🎨 1688 包装图片批量分析工具")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        from image_analyzer import analyze_all_images, summarize_analysis
    except ImportError as e:
        print(f"❌ 图片分析库未安装：{e}")
        print("   请运行: pip install opencv-python pillow scikit-image")
        sys.exit(1)

    # 加载数据
    products = find_existing_data()
    if not products:
        print("❌ 没有可分析的数据")
        return

    # 检查图片是否存在
    has_images = sum(1 for p in products if p.get("main_image_local") and Path(p["main_image_local"]).exists())
    print(f"📸 有本地图片的产品：{has_images}/{len(products)}")

    if has_images == 0:
        print("⚠️  没有发现已下载的本地图片，请先运行 main.py 采集数据")
        return

    # 执行分析
    products = analyze_all_images(products)

    # 保存结果
    today_str = datetime.now().strftime("%Y-%m-%d")
    analyzed_path = config.OUTPUT_DIR / f"analyzed_{today_str}.json"
    analyzed_path.write_text(
        json.dumps(products, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"📊 分析结果已保存：{analyzed_path}")

    # 生成汇总报告
    try:
        from reporter import generate_analysis_report
        generate_analysis_report(products, config.REPORTS_DIR / f"analysis_{today_str}.json")
    except Exception as e:
        print(f"⚠️  生成汇总报告出错：{e}")

    # 打印摘要
    summary = summarize_analysis(products)
    print(f"\n{'='*50}")
    print(f"  📊 图片分析汇总")
    print(f"{'='*50}")
    print(f"  分析图片数：{summary.get('total_analyzed', 0)}/{summary.get('total_products', 0)}")

    print(f"\n  📊 视觉风格分布：")
    for cat, count in sorted(summary.get("visual_categories", {}).items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count} 件")

    print(f"\n  🔥 爆款特征趋势：")
    for feat, count in summary.get("trending_features", {}).items():
        print(f"    {feat}: {count} 件")

    print(f"\n  🏷️ 热门风格标签：")
    for tag, count in summary.get("style_tags_rank", {}).items()[:5]:
        print(f"    {tag}: x{count}")

    print(f"\n✅ 分析完成！")


if __name__ == "__main__":
    main()
