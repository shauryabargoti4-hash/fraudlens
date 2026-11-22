from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

for i, line in enumerate(lines):
    s = line.lstrip(" ")
    if s.startswith(("if ", "elif ", "else:", "for ", "while ", "with ", "def ", "class ")):
        # Handle single-line or multi-line header ending in ':'
        end_idx = i
        while end_idx < len(lines) and not lines[end_idx].rstrip().endswith(":"):
            end_idx += 1
        if end_idx >= len(lines):
            continue
        base = len(line) - len(s)
        j = end_idx + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines):
            nxt = lines[j]
            ns = nxt.lstrip(" ")
            if (len(nxt) - len(ns)) <= base:
                eol = "\r\n" if nxt.endswith("\r\n") else ("\n" if nxt.endswith("\n") else "")
                lines[j] = (" " * (base + 4)) + ns.rstrip("\r\n") + eol

p.write_text("".join(lines), encoding="utf-8")