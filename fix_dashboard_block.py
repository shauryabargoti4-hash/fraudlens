from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

# 1-based lines 149..218 -> 0-based indices 148..217
start_idx = 148
end_idx = min(len(lines), 218)

for i in range(start_idx, end_idx):
    line = lines[i]
    if line.strip():
        eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        lines[i] = "    " + line.rstrip("\r\n") + eol

p.write_text("".join(lines), encoding="utf-8")