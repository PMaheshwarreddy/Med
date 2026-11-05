"""Builds docs/code-guide/map/*.md: every backend file, its functions and
classes with exact line ranges and docstrings, and for each API route the
frontend files that call it."""
import ast, re, sys
from pathlib import Path

ROOT = Path(sys.argv[1]); OUT = ROOT / "docs/code-guide/map"; OUT.mkdir(parents=True, exist_ok=True)
FRONT = list((ROOT / "frontend/lib").rglob("*.dart"))
front_text = {f: f.read_text(errors="replace") for f in FRONT}

def callers(path: str) -> list[str]:
    # '/api/admin/knowledge/uploads/{upload_id}/{action}' -> regex on the fixed start
    fixed = re.split(r"\{", path)[0].rstrip("/")
    tails = [fixed]
    for prefix in ("/api/hospital", "/api/doctor", "/api/admin/knowledge", "/api/admin"):
        if fixed.startswith(prefix) and len(fixed) > len(prefix):
            tails.append(fixed[len(prefix):])  # clients add their own prefix
    hits = set()
    for f, t in front_text.items():
        for tail in tails:
            if len(tail) > 3 and ("'" + tail in t or '"' + tail in t or tail + "'" in t or tail + "/" in t or tail + "$" in t):
                hits.add(str(f.relative_to(ROOT)))
    return sorted(hits)

def first_line(doc):
    return " ".join((doc or "").strip().split("\n\n")[0].split())

def describe(node, depth, lines, prefixes):
    out = []
    for n in node.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(n, ast.ClassDef) else ("async def" if isinstance(n, ast.AsyncFunctionDef) else "def")
            start = (n.decorator_list[0].lineno if n.decorator_list else n.lineno)
            route = ""
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("get","post","put","patch","delete","websocket") and d.args and isinstance(d.args[0], ast.Constant):
                    owner = d.func.value.id if isinstance(d.func.value, ast.Name) else ""
                    route = f"{d.func.attr.upper()} {prefixes.get(owner, '')}{d.args[0].value}"
            doc = first_line(ast.get_docstring(n))
            ind = "  " * depth
            text = f"{ind}- **L{start}–{n.end_lineno}** `{kind} {n.name}`"
            if route:
                text += f" — route `{route}`"
                c = callers(route.split(" ",1)[1])
                text += f"; called from: {', '.join('`'+x+'`' for x in c) if c else 'no frontend file (API clients / tests)'}"
            if doc: text += f"  \n{ind}  {doc}"
            out.append(text)
            if isinstance(n, ast.ClassDef):
                out += describe(n, depth + 1, lines, prefixes)
    return out

def module_parts(path: Path):
    src = path.read_text(); tree = ast.parse(src)
    prefixes = dict(re.findall(r'(\w+)\s*=\s*APIRouter\([^)]*?prefix="([^"]+)"', src))
    doc = ast.get_docstring(tree) or ""
    imports = sorted({(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level})
    consts = [f"- **L{n.lineno}** `{t.id}`" for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name) and t.id.isupper()]
    return src.count("\n") + 1, doc, imports, consts, describe(tree, 0, src.splitlines(), prefixes)

groups = {}
for area in ("app", "eval", "tests"):
    for f in sorted((ROOT / "backend" / area).rglob("*.py")):
        if "__pycache__" in f.parts: continue
        rel = f.relative_to(ROOT / "backend")
        key = "/".join(rel.parts[:2]) if rel.parts[0] == "app" and len(rel.parts) > 2 else rel.parts[0]
        groups.setdefault(key, []).append(f)

index = ["# Backend map (generated)", "", "Every backend file with its functions and classes and their exact line numbers. "
         "Regenerate after code changes so the numbers stay right.", ""]
for key, files in groups.items():
    name = key.replace("/", "-") + ".md"
    md = [f"# `{key}`", ""]
    for f in files:
        n, doc, imports, consts, items = module_parts(f)
        rel = f.relative_to(ROOT)
        md += [f"## `{rel}` ({n} lines)", ""]
        if doc: md += [doc.strip(), ""]
        if imports: md += ["Uses (inside the app): " + ", ".join(f"`{i}`" for i in imports if i), ""]
        if consts: md += ["Settings and constants:", *consts, ""]
        md += (["Functions and classes:", *items, ""] if items else ["(no functions)", ""])
    (OUT / name).write_text("\n".join(md))
    index.append(f"- [{key}]({name}): " + ", ".join(f"`{f.name}`" for f in files))
(OUT / "README.md").write_text("\n".join(index) + "\n")
print("ok", len(groups))
