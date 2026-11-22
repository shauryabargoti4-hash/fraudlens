from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

for i, line in enumerate(lines):
    if line.lstrip(" ").startswith(("except ", "except:")):
        base = len(line) - len(line.lstrip(" "))
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            s = nxt.lstrip(" ")
            if s.strip() and (len(nxt) - len(s)) <= base:
                eol = "\r\n" if nxt.endswith("\r\n") else ("\n" if nxt.endswith("\n") else "")
                lines[i + 1] = (" " * (base + 4)) + s.rstrip("\r\n") + eol

p.write_text("".join(lines), encoding="utf-8")