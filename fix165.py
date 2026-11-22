from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
if len(lines) >= 165:
    # Look back to nearest non-empty line with a valid indent
    prev = 163
    while prev >= 0 and not lines[prev].strip():
        prev -= 1
    target_indent = 0
    if prev >= 0:
        s_prev = lines[prev].lstrip(" ")
        target_indent = len(lines[prev]) - len(s_prev)
        if s_prev.rstrip().endswith(":"):
            target_indent += 4
    line = lines[164]
    eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
    lines[164] = (" " * target_indent) + line.lstrip(" ").rstrip("\r\n") + eol
p.write_text("".join(lines), encoding="utf-8")