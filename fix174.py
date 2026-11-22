from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

idx = 173 # line 174 (0-indexed 173)
if idx < len(lines):
    line = lines[idx]
    stripped = line.lstrip(" ")
    cur_indent = len(line) - len(stripped)
    if cur_indent >= 4 and stripped.startswith("with qa1:"):
        eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        lines[idx] = (" " * (cur_indent - 4)) + stripped.rstrip("\r\n") + eol
        # Shift following lines that were indented deeper than the old `with qa1:`
        j = idx + 1
        while j < len(lines):
            lj = lines[j]
            sj = lj.lstrip(" ")
            if not sj.strip():
                j += 1
                continue
            ind_j = len(lj) - len(sj)
            if ind_j > cur_indent:
                jeol = "\r\n" if lj.endswith("\r\n") else ("\n" if lj.endswith("\n") else "")
                lines[j] = (" " * (ind_j - 4)) + sj.rstrip("\r\n") + jeol
                j += 1
            else:
                break

p.write_text("".join(lines), encoding="utf-8")