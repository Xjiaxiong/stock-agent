#!/usr/bin/env python3
"""分享卡片的排版自检（重叠 / 越界 / 字号）。

卡片是 Canvas 手绘的：字号、折行、间距全靠自己算，"某段文字压到下一块""数值溢出格子"
这类问题肉眼未必马上发现，改版式时也很容易回归。这个脚本用无头 Chrome 真正渲染一遍，
再对元素的包围盒做碰撞检测，把问题打成清单。

用法（在 frontend 目录下）：
    ../.venv/bin/python scripts/card-audit.py /tmp/card.json

参数：card.json —— 后端 SSE report 事件里的 card 字段（结构化摘要），
      可以先用 market/daily_review.build_card() 生成一份来调试。
依赖：本机装了 Google Chrome；脚本会自动编译 lib/shareCard.ts 再渲染。
"""

import html as html_mod
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.dirname(HERE)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

AUDIT_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>audit</title>
<style>html,body{margin:0;background:#fff}canvas{display:block;width:1080px;height:auto;background:#fff}</style>
</head><body>
<canvas id="c"></canvas>
<pre id="out"></pre>
<script>var exports = {};</script>
<script src="./shareCard.js"></script>
<script>
  const data = %s;
  const canvas = document.getElementById("c");
  const boxes = exports.drawShareCard(canvas, data);
  const payload = {width: canvas.width, height: canvas.height, boxes: boxes};
  document.getElementById("out").textContent = JSON.stringify(payload)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
</script>
</body></html>"""


def compile_card(workdir: str) -> None:
    """把 lib/shareCard.ts 编译成浏览器可直接引用的 JS（用全局 exports 兜住 CJS）。"""
    subprocess.run(
        [
            "npx", "tsc", "lib/shareCard.ts",
            "--outDir", workdir,
            "--target", "es2020",
            "--module", "commonjs",
            "--moduleResolution", "node",
            "--skipLibCheck",
        ],
        cwd=FRONTEND, check=True, capture_output=True, text=True,
    )


def render(workdir: str, card: dict) -> dict:
    html_path = os.path.join(workdir, "audit.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(AUDIT_HTML % json.dumps(card, ensure_ascii=False))

    # Chrome 渲染完经常不退出（后台联网重试），所以不等它自然结束：
    # 一边读 stdout 一边等 </pre> 出现，拿到就杀掉。
    proc = subprocess.Popen(
        [
            CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--disable-background-networking", "--disable-component-update",
            "--disable-sync", "--disable-default-apps", "--no-pings",
            "--host-resolver-rules=MAP * ~NOTFOUND",
            f"--user-data-dir={os.path.join(workdir, 'profile')}",
            "--virtual-time-budget=3000", "--dump-dom", f"file://{html_path}",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    chunks: list[str] = []

    def drain() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            chunks.append(line)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    deadline = time.time() + 45
    while time.time() < deadline:
        if "</pre>" in "".join(chunks):
            break
        time.sleep(0.2)
    proc.kill()
    reader.join(timeout=2)
    stdout = "".join(chunks)

    match = re.search(r'<pre id="out">(.*?)</pre>', stdout, re.S)
    if not match:
        raise RuntimeError("没拿到元素包围盒，请确认 Chrome 可用：\n" + stdout[:400])
    return json.loads(html_mod.unescape(match.group(1)))


def overlap(a: dict, b: dict) -> float:
    x1, y1 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x2 = min(a["x"] + a["w"], b["x"] + b["w"])
    y2 = min(a["y"] + a["h"], b["y"] + b["h"])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def contains(a: dict, b: dict) -> bool:
    """a 是否完整包住 b（容器套内容属于正常，不算重叠）。"""
    return (
        b["x"] >= a["x"] - 1
        and b["y"] >= a["y"] - 1
        and b["x"] + b["w"] <= a["x"] + a["w"] + 1
        and b["y"] + b["h"] <= a["y"] + a["h"] + 1
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        card = json.load(f)

    workdir = tempfile.mkdtemp(prefix="card-audit-")
    try:
        compile_card(workdir)
        payload = render(workdir, card)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    boxes = payload["boxes"]
    width, height = payload["width"] / 2, payload["height"] / 2
    print(f"画布：{width:.0f}×{height:.0f} 逻辑像素（导出 {payload['width']}×{payload['height']}，"
          f"长宽比 1:{height / width:.2f}）")

    oob = [
        box for box in boxes
        if box["x"] < -0.5 or box["x"] + box["w"] > width + 0.5
        or box["y"] < -0.5 or box["y"] + box["h"] > height + 0.5
    ]
    problems = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            area = overlap(a, b)
            if area > 4 and not contains(a, b) and not contains(b, a):
                problems.append((area, a, b))

    print(f"元素 {len(boxes)} 个；越界 {len(oob)} 处；重叠 {len(problems)} 处")
    for box in oob:
        print(f"  ✗ 越界 {box['label']} x={box['x']:.0f} y={box['y']:.0f}")
    for area, a, b in sorted(problems, key=lambda item: -item[0]):
        print(f"  ✗ 重叠 {area:7.0f}px² {a['label']} <-> {b['label']}")

    sizes = sorted({box["size"] for box in boxes if box.get("size")})
    print(f"字号（逻辑 px）：{sizes}")
    return 1 if (problems or oob) else 0


if __name__ == "__main__":
    raise SystemExit(main())
