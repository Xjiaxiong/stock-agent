"""pytest 公共配置。

market/ 里的模块是"脚本式"布局（既能从仓库根跑，也能在 market/ 里跑），
所以测试统一把仓库根与 market/ 显式加进模块搜索路径，避免依赖调用者的 cwd。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "market"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
