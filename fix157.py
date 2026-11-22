from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
if len(lines) >= 157:
    line = lines[156]
    eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
    lines[156] = line.lstrip(" ").rstrip("\r\n") + eol
p.write_text("".join(lines), encoding="utf-8")