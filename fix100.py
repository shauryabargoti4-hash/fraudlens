from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
lines[99] = "    " + lines[99].lstrip(" ")
p.write_text("".join(lines), encoding="utf-8")