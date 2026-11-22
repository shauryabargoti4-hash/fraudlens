import ast
from pathlib import Path

src = Path("streamlit_app.py").read_text(encoding="utf-8")
try:
    ast.parse(src, filename="streamlit_app.py")
    print("Clean!")
except SyntaxError as e:
    print(f"{type(e).__name__} on line {e.lineno}: {e.msg}")
    lines = src.splitlines()
    start = max(0, (e.lineno or 1) - 6)
    end = min(len(lines), (e.lineno or 1) + 5)
    for i in range(start, end):
        mark = ">>>" if i + 1 == e.lineno else "   "
        print(f"{mark} {i+1:3d}: {lines[i]!r}")