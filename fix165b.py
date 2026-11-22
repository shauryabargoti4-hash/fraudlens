from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

if len(lines) >= 170:
    # Find the matching `try:` above line 165
    try_idx = 163
    while try_idx >= 0 and not lines[try_idx].lstrip(" ").startswith("try:"):
        try_idx -= 1
    try_indent = (len(lines[try_idx]) - len(lines[try_idx].lstrip(" "))) if try_idx >= 0 else 4

    # Align `except Exception:` at line 165 (index 164) to `try_indent`
    e_line = lines[164]
    e_eol = "\r\n" if e_line.endswith("\r\n") else ("\n" if e_line.endswith("\n") else "")
    lines[164] = (" " * try_indent) + e_line.lstrip(" ").rstrip("\r\n") + e_eol

    # Indent lines 166-170 (indices 165-169) inside `except Exception:`
    for idx in range(165, 170):
        l = lines[idx]
        s = l.lstrip(" ")
        if s.strip():
            eol = "\r\n" if l.endswith("\r\n") else ("\n" if l.endswith("\n") else "")
            lines[idx] = (" " * (try_indent + 4)) + s.rstrip("\r\n") + eol

p.write_text("".join(lines), encoding="utf-8")