from pathlib import Path
p = Path("streamlit_app.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

for idx, line in enumerate(lines):
    s = line.lstrip(" ")
    if s.startswith("try:"):
        base = len(line) - len(s)
        j = idx + 1
        while j < len(lines):
            sj = lines[j].lstrip(" ")
            if not sj.strip():
                j += 1
                continue
            if sj.startswith(("except", "finally")):
                eol = "\r\n" if lines[j].endswith("\r\n") else ("\n" if lines[j].endswith("\n") else "")
                lines[j] = (" " * base) + sj.rstrip("\r\n") + eol
                k = j + 1
                while k < len(lines):
                    sk = lines[k].lstrip(" ")
                    if not sk.strip():
                        k += 1
                        continue
                    cur_k = len(lines[k]) - len(sk)
                    if cur_k <= base and not sk.startswith(("#", "st.", "with ", "if ", "elif ", "else:", "for ", "while ", "def ", "class ")):
                        keol = "\r\n" if lines[k].endswith("\r\n") else ("\n" if lines[k].endswith("\n") else "")
                        lines[k] = (" " * (base + 4)) + sk.rstrip("\r\n") + keol
                        k += 1
                    else:
                        break
                break
            cur_j = len(lines[j]) - len(sj)
            if cur_j <= base:
                jeol = "\r\n" if lines[j].endswith("\r\n") else ("\n" if lines[j].endswith("\n") else "")
                lines[j] = (" " * (base + 4)) + sj.rstrip("\r\n") + jeol
            j += 1

p.write_text("".join(lines), encoding="utf-8")