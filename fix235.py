from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

if len(lines) >= 235:
    line = lines[234]
    stripped = line.lstrip(" ")
    if stripped.startswith("render_report_view("):
        eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        lines[234] = "    " + stripped.rstrip("\r\n") + eol

p.write_text("".join(lines), encoding="utf-8")