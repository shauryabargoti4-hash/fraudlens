from pathlib import Path
import ast

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

text = text.replace("\n    st.markdown(\n    \"\"\"", "\nst.markdown(\n    \"\"\"")
text = text.replace('\n    st.markdown("---")', '\nst.markdown("---")')

lines = text.splitlines(keepends=True)
fixed = []
for line in lines:
    stripped = line.lstrip(" ")
    leading = len(line) - len(stripped)
    if leading == 4 and stripped.startswith(("st.", "render_", "col_demo", "with col_demo")):
        fixed.append(stripped)
    else:
        fixed.append(line)

new_text = "".join(fixed)
path.write_text(new_text, encoding="utf-8")
ast.parse(new_text, filename=str(path))
print("streamlit_app.py parsed cleanly with zero syntax/indentation errors!")