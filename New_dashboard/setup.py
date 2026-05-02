"""
New_dashboard/setup.py — 主入口

用法：
  python setup.py                        # 安裝所有組件
  python setup.py bus_stop_by_district   # 只安裝指定組件

新增組件方式：
  在 New_dashboard/ 下建立新子目錄，放入：
    setup.py          — 該組件的完整安裝腳本
    patch_manager.sql — 該組件的 dashboardmanager SQL patch
  下次執行 python setup.py 時會自動被偵測並執行。
"""
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).parent

# 自動偵測所有子目錄組件（排除以 . 或 _ 開頭的目錄）
all_components = sorted(
    d for d in HERE.iterdir()
    if d.is_dir() and not d.name.startswith((".", "_"))
)

if not all_components:
    print("[警告] 找不到任何組件子目錄，結束。")
    sys.exit(0)

# 若有傳入參數，只跑指定組件
if len(sys.argv) > 1:
    target = sys.argv[1]
    to_run = [HERE / target]
    if not to_run[0].is_dir():
        print(f"[錯誤] 找不到組件目錄：{target}")
        print(f"可用組件：{[d.name for d in all_components]}")
        sys.exit(1)
else:
    to_run = all_components

print(f"\n{'='*52}")
print(f"  New_dashboard 安裝程式")
print(f"  準備安裝 {len(to_run)} 個組件：{[d.name for d in to_run]}")
print(f"{'='*52}")

for comp_dir in to_run:
    setup_script = comp_dir / "setup.py"
    if not setup_script.exists():
        print(f"[跳過] {comp_dir.name}：找不到 setup.py")
        continue

    print(f"\n▶ 開始安裝組件：{comp_dir.name}")
    result = subprocess.run(
        [sys.executable, str(setup_script)],
        check=False,
    )
    if result.returncode != 0:
        print(f"[錯誤] {comp_dir.name} 安裝失敗（exit code {result.returncode}），繼續下一個。")
    else:
        print(f"[完成] {comp_dir.name} 安裝成功")

print(f"\n{'='*52}")
print("  全部完成！重新整理瀏覽器即可看到新 Dashboard。")
print("  pgAdmin : http://localhost:8889")
print(f"{'='*52}\n")
