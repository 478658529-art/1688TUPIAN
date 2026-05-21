"""
Windows 任务计划程序设置脚本
每天 09:00 自动运行 1688 采集工具
"""
import os
import sys
import subprocess
from pathlib import Path
import config


def generate_ps1_script() -> str:
    """生成 PowerShell 启动脚本内容"""
    python_exe = sys.executable
    script_path = str(Path(__file__).parent / "main.py")
    work_dir = str(Path(__file__).parent)
    log_file = str(config.OUTPUT_DIR / "scheduler.log")

    lines = [
        '# 启动1688采集工具 - 每天9:00自动运行',
        f'$pythonExe = "{python_exe}"',
        f'$scriptPath = "{script_path}"',
        f'$workDir = "{work_dir}"',
        f'$logFile = "{log_file}"',
        '',
        '$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"',
        '"[$timestamp] 任务启动" | Out-File -FilePath $logFile -Append -Encoding utf8',
        '',
        '# 设置工作目录',
        'Set-Location $workDir',
        '',
        '# 运行脚本',
        'try {',
        '    $process = Start-Process -FilePath $pythonExe -ArgumentList "`"$scriptPath`"" -NoNewWindow -Wait -PassThru',
        '    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"',
        '    "[$timestamp] 任务完成，退出代码: $($process.ExitCode)" | Out-File -FilePath $logFile -Append -Encoding utf8',
        '} catch {',
        '    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"',
        '    "[$timestamp] 错误: $_" | Out-File -FilePath $logFile -Append -Encoding utf8',
        '}',
    ]
    return "\n".join(lines)


def setup_windows_task():
    """创建 Windows 计划任务，每天9:00运行"""
    ps_path = Path(__file__).parent / "run_scheduled.ps1"
    task_name = "1688PackagingScraper"

    # 生成 PS1 启动脚本
    ps_content = generate_ps1_script()
    ps_path.write_text(ps_content, encoding="utf-8")
    print("📝 已生成 PowerShell 启动脚本：" + str(ps_path))

    print("\n" + "=" * 60)
    print("  ⏰ Windows 计划任务设置")
    print("=" * 60)
    print(f"\n任务名称：{task_name}")
    print(f"执行时间：每天 09:00")
    print(f"执行脚本：{ps_path}")
    print(f"日志文件：{config.OUTPUT_DIR / 'scheduler.log'}")

    print(f"\n📌 为创建计划任务，请以管理员身份运行：")
    print(f"\n    schtasks /Create /SC DAILY /TN \"{task_name}\" /TR \"powershell -ExecutionPolicy Bypass -File \\\"{ps_path}\\\"\" /ST 09:00 /F")
    print()
    print("📌 或手动设置：")
    print("   1. 按 Win+R，输入 taskschd.msc 回车")
    print("   2. 点击右侧「创建基本任务...」")
    print("   3. 名称：1688包装采集日报")
    print("   4. 触发器：每天，09:00")
    print("   5. 操作：启动程序 -> powershell")
    print(f"      参数: -ExecutionPolicy Bypass -File \"{ps_path}\"")
    print("   6. 完成")


def main():
    print("=" * 60)
    print("  ⏰ 1688 包装采集工具 - 定时任务设置")
    print("=" * 60)
    setup_windows_task()


if __name__ == "__main__":
    main()
