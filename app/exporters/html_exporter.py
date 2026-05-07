"""HTML report export with modern brand-styled output."""

from __future__ import annotations

import html
import re
from datetime import datetime

from app.config import settings
from app.utils.file_utils import ensure_parent, make_job_id, safe_filename


_BRAND_CSS = """
:root {
  color-scheme: light dark;
  --primary: #0F766E;
  --primary-dark: #134E4A;
  --primary-soft: #CCFBF1;
  --accent: #F59E0B;
  --success: #16A34A;
  --danger: #DC2626;
  --ink-900: #0F172A;
  --ink-700: #334155;
  --ink-500: #64748B;
  --ink-300: #CBD5E1;
  --bg: #F8FAFC;
  --bg-soft: #F1F5F9;
  --card: #FFFFFF;
  --border: #E2E8F0;
  --shadow: 0 14px 38px rgba(15, 23, 42, .08);
  --radius: 14px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0B1120;
    --bg-soft: #111827;
    --card: #0F172A;
    --border: #1E293B;
    --ink-900: #F8FAFC;
    --ink-700: #CBD5E1;
    --ink-500: #94A3B8;
    --ink-300: #475569;
    --primary-soft: #134E4A;
    --shadow: 0 14px 38px rgba(0, 0, 0, .55);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background:
    radial-gradient(1200px 600px at 100% -200px, rgba(15, 118, 110, .15), transparent 60%),
    radial-gradient(900px 500px at -200px 100%, rgba(245, 158, 11, .08), transparent 50%),
    var(--bg);
  color: var(--ink-700);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.page { max-width: 1100px; margin: 0 auto; padding: 36px 24px 56px; }
.hero {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: #fff;
  padding: 36px 38px;
  border-radius: var(--radius);
  margin-bottom: 24px;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}
.hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(600px 200px at 100% 0%, rgba(255,255,255,.18), transparent 60%),
    radial-gradient(400px 160px at 0% 100%, rgba(255,255,255,.12), transparent 60%);
  pointer-events: none;
}
.hero .eyebrow {
  text-transform: uppercase;
  letter-spacing: 2px;
  font-size: 11px;
  opacity: .85;
  margin-bottom: 8px;
  font-weight: 600;
}
.hero h1 { margin: 0; font-size: 30px; font-weight: 700; letter-spacing: -.02em; line-height: 1.18; }
.hero .meta { margin-top: 14px; font-size: 13px; opacity: .9; }
.content {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 32px 38px;
  box-shadow: var(--shadow);
  color: var(--ink-700);
}
h1, h2, h3, h4 { color: var(--ink-900); letter-spacing: -.01em; line-height: 1.3; }
h1 { font-size: 26px; margin: 0 0 18px; font-weight: 700; }
h2 {
  font-size: 19px;
  margin: 32px 0 14px;
  padding: 0 0 10px;
  border-bottom: 1px solid var(--border);
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 10px;
}
h2::before {
  content: '';
  width: 4px;
  height: 18px;
  background: var(--primary);
  border-radius: 4px;
}
h3 { font-size: 15px; margin: 22px 0 10px; font-weight: 600; color: var(--primary-dark); }
p { line-height: 1.65; margin: 10px 0; font-size: 14.5px; }
ul { margin: 10px 0 18px; padding-left: 22px; }
li { margin: 7px 0; line-height: 1.6; font-size: 14.5px; }
li::marker { color: var(--primary); }
strong { color: var(--ink-900); font-weight: 600; }
em { color: var(--ink-500); }
code {
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 2px 7px;
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  color: var(--primary-dark);
}
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 18px 0 20px;
  font-size: 13.5px;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}
th {
  background: linear-gradient(180deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: #fff;
  font-weight: 600;
  text-align: left;
  padding: 11px 14px;
  letter-spacing: .01em;
  text-transform: uppercase;
  font-size: 11.5px;
}
td { padding: 11px 14px; border-top: 1px solid var(--border); color: var(--ink-700); }
tr:nth-child(even) td { background: var(--bg-soft); }
tr:hover td { background: var(--primary-soft); transition: background .15s ease; }
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: .02em;
  text-transform: uppercase;
}
.badge-success { background: rgba(22, 163, 74, .14); color: var(--success); }
.badge-warn { background: rgba(245, 158, 11, .14); color: var(--accent); }
.badge-danger { background: rgba(220, 38, 38, .14); color: var(--danger); }
hr { border: 0; border-top: 1px dashed var(--border); margin: 28px 0; }
footer { margin-top: 28px; text-align: center; font-size: 12px; color: var(--ink-500); }
@media (max-width: 720px) {
  .page { padding: 20px 14px 36px; }
  .hero, .content { padding: 22px 20px; border-radius: 10px; }
  .hero h1 { font-size: 22px; }
  table { font-size: 12.5px; }
  th, td { padding: 9px 10px; }
}
@media print {
  body { background: #fff; }
  .hero { background: var(--primary); color: #fff; box-shadow: none; }
  .content { box-shadow: none; border-color: #ddd; }
}
""".strip()


def export_html(title: str, body_markdown: str, name: str, job_id: str | None = None) -> str:
    job = job_id or make_job_id("report")
    output = settings.REPORT_DIR / job / f"{safe_filename(name)}.html"
    ensure_parent(output)
    body = _markdown_to_html(body_markdown)
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    content = f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>{_BRAND_CSS}</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">HR Intelligence Report</div>
      <h1>{html.escape(title)}</h1>
      <div class="meta">Hazırlanma: {html.escape(generated_at)}</div>
    </section>
    <section class="content">{body}</section>
    <footer>Survey & Excel Intelligence — otomatik üretildi</footer>
  </main>
</body>
</html>
"""
    output.write_text(content, encoding="utf-8")
    return str(output.resolve())


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines: list[str] = []
    in_ul = False
    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_table:
                html_lines.append("</tbody></table>")
                in_table = False
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= {"-", ":"} for cell in cells):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                html_lines.append("<table><tbody>")
                in_table = True
            html_lines.append("<tr>" + "".join(f"<{tag}>{_inline(cell)}</{tag}>" for cell in cells) + "</tr>")
            continue
        if in_table:
            html_lines.append("</tbody></table>")
            in_table = False
        if stripped.startswith("#"):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            level = min(len(stripped) - len(stripped.lstrip("#")), 4)
            text = stripped[level:].strip()
            html_lines.append(f"<h{level}>{_inline(text)}</h{level}>")
        elif stripped.startswith("- "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline(stripped[2:])}</li>")
        elif stripped.startswith("---"):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append("<hr>")
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<p>{_inline(stripped)}</p>")
    if in_ul:
        html_lines.append("</ul>")
    if in_table:
        html_lines.append("</tbody></table>")
    return "\n".join(html_lines)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped
