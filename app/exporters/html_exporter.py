"""HTML report export."""

from __future__ import annotations

import html
import re

from app.config import settings
from app.utils.file_utils import ensure_parent, make_job_id, safe_filename


def export_html(title: str, body_markdown: str, name: str, job_id: str | None = None) -> str:
    job = job_id or make_job_id("report")
    output = settings.REPORT_DIR / job / f"{safe_filename(name)}.html"
    ensure_parent(output)
    body = _markdown_to_html(body_markdown)
    content = f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7fb; color: #1f2937; }}
    .page {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 48px; }}
    .hero {{ background: #0f172a; color: white; padding: 28px 32px; border-radius: 8px; margin-bottom: 22px; }}
    .hero h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    .content {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 28px 32px; box-shadow: 0 10px 28px rgba(15, 23, 42, .08); }}
    h1, h2, h3 {{ letter-spacing: 0; line-height: 1.25; }}
    h1 {{ font-size: 28px; margin: 0 0 18px; }}
    h2 {{ font-size: 20px; margin: 28px 0 12px; padding-top: 18px; border-top: 1px solid #edf0f5; }}
    h3 {{ font-size: 16px; margin: 18px 0 10px; }}
    p {{ line-height: 1.58; margin: 9px 0; }}
    ul {{ margin: 8px 0 16px; padding-left: 20px; }}
    li {{ margin: 7px 0; line-height: 1.5; }}
    strong {{ color: #0f172a; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 9px 10px; text-align: left; }}
    th {{ background: #f8fafc; }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 12px 32px; }}
      .hero, .content {{ padding: 20px; }}
      .hero h1 {{ font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero"><h1>{html.escape(title)}</h1></section>
    <section class="content">{body}</section>
  </main>
</body>
</html>
"""
    output.write_text(content, encoding="utf-8")
    return str(output.resolve())


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines = []
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
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            text = stripped[level:].strip()
            html_lines.append(f"<h{level}>{_inline(text)}</h{level}>")
        elif stripped.startswith("- "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline(stripped[2:])}</li>")
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
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
