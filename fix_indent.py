from pathlib import Path
import ast

path = Path("streamlit_app.py")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

if len(lines) >= 100 and lines[99].startswith("        "):
    lines[99] = lines[99][4:]

for _ in range(80):
    source = "".join(lines)
    try:
        ast.parse(source, filename=str(path))
        path.write_text(source, encoding="utf-8")
        print("SUCCESS: streamlit_app.py parses with zero syntax or indentation errors!")
        break
    except IndentationError as exc:
        lineno = exc.lineno
        if not lineno or lineno < 2 or lineno > len(lines):
            raise
        idx = lineno - 1
        prev_idx = idx - 1
        while prev_idx >= 0 and not lines[prev_idx].strip():
            prev_idx -= 1
        if prev_idx < 0:
            raise
        prev_indent = len(lines[prev_idx]) - len(lines[prev_idx].lstrip(" "))
        cur_stripped = lines[idx].lstrip(" ")
        eol = "\r\n" if lines[idx].endswith("\r\n") else ("\n" if lines[idx].endswith("\n") else "")
        if "expected an indented block" in exc.msg:
            lines[idx] = (" " * (prev_indent + 4)) + cur_stripped.rstrip("\r\n") + eol
        else:
            lines[idx] = (" " * prev_indent) + cur_stripped.rstrip("\r\n") + eol
    except SyntaxError as exc:
        lineno = exc.lineno
        if "expected 'except' or 'finally' block" in exc.msg and lineno and lineno >= 2:
            # Find the preceding `try:` line
            try_idx = lineno - 2
            while try_idx >= 0 and not lines[try_idx].lstrip(" ").startswith("try:"):
                try_idx -= 1
            if try_idx < 0:
                raise
            try_indent = len(lines[try_idx]) - len(lines[try_idx].lstrip(" "))
            target_indent = try_indent + 4
            # Indent subsequent lines until `except` or `finally` at `try_indent`
            for j in range(try_idx + 1, min(len(lines), try_idx + 20)):
                s = lines[j].lstrip(" ")
                if not s.strip():
                    continue
                if s.startswith(("except", "finally")):
                    eol = "\r\n" if lines[j].endswith("\r\n") else ("\n" if lines[j].endswith("\n") else "")
                    lines[j] = (" " * try_indent) + s.rstrip("\r\n") + eol
                    break
                cur_ind = len(lines[j]) - len(s)
                if cur_ind < target_indent:
                    eol = "\r\n" if lines[j].endswith("\r\n") else ("\n" if lines[j].endswith("\n") else "")
                    lines[j] = (" " * target_indent) + s.rstrip("\r\n") + eol
        else:
            raise
else:
    raise RuntimeError("Could not resolve all errors automatically.")