"""
Конвертация Markdown-файлов, создаваемых инструментом, в HTML.

Использует markdown-it-py с включённой поддержкой GFM-таблиц.
Каждый .md превращается в .html с тем же именем, лежащий рядом
(например, data/reports/<chat>/final_report.md -> .../final_report.html).

CSS — встроенный, со светлой темой по умолчанию и автоматической
тёмной через @media (prefers-color-scheme: dark).
"""

from __future__ import annotations

import html as html_lib
import re
from pathlib import Path

try:
    from markdown_it import MarkdownIt
except ImportError as e:
    raise ImportError(
        "Модуль markdown-it-py не установлен. Установите зависимости: "
        "pip install -r requirements.txt"
    ) from e

from .config import Config


# ============================================================
# CSS — светлая + автоматическая тёмная тема
# ============================================================
_CSS = """\
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --fg: #2d2d2d;
  --muted: #6a6a6a;
  --border: #e1e4e8;
  --code-bg: #f4f4f4;
  --code-fg: #24292e;
  --quote-bg: transparent;
  --quote-border: #d0d7de;
  --quote-fg: #57606a;
  --link: #0969da;
  --table-header-bg: #f6f8fa;
  --hr: #d8dee4;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117;
    --fg: #e6edf3;
    --muted: #8b949e;
    --border: #30363d;
    --code-bg: #161b22;
    --code-fg: #e6edf3;
    --quote-bg: transparent;
    --quote-border: #30363d;
    --quote-fg: #8b949e;
    --link: #58a6ff;
    --table-header-bg: #161b22;
    --hr: #30363d;
  }
}

* { box-sizing: border-box; }
html, body { background: var(--bg); color: var(--fg); }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
               'Helvetica Neue', Arial, sans-serif;
  line-height: 1.65;
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 20px 80px;
  font-size: 16px;
}

h1, h2, h3, h4, h5, h6 {
  margin-top: 1.6em;
  margin-bottom: 0.6em;
  line-height: 1.25;
  color: var(--fg);
}
h1 { font-size: 2em; border-bottom: 1px solid var(--hr); padding-bottom: 0.3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid var(--hr); padding-bottom: 0.25em; }
h3 { font-size: 1.2em; }
h4 { font-size: 1.05em; }

p { margin: 0.8em 0; }

a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }

code {
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
  font-size: 0.92em;
}
pre {
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 14px 16px;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
  font-size: 0.92em;
  line-height: 1.5;
  margin: 1em 0;
}
pre code { background: transparent; padding: 0; }

blockquote {
  border-left: 4px solid var(--quote-border);
  background: var(--quote-bg);
  margin: 1em 0;
  padding: 0.4em 1em;
  color: var(--quote-fg);
  font-style: italic;
}
blockquote p { margin: 0.4em 0; }

table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
  display: block;
  overflow-x: auto;
}
th, td {
  border: 1px solid var(--border);
  padding: 8px 12px;
  text-align: left;
  vertical-align: top;
}
th {
  background: var(--table-header-bg);
  font-weight: 600;
}

ul, ol { margin: 0.8em 0; padding-left: 2em; }
li { margin: 0.35em 0; }

hr { border: 0; border-top: 1px solid var(--hr); margin: 2em 0; }

img { max-width: 100%; height: auto; }

::selection { background: rgba(88, 166, 255, 0.3); }
"""


# ============================================================
# Подбор заголовка для <title>
# ============================================================
_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)
_EMOJI_PREFIX_RE = re.compile(r"^[^\w\d\s]+\s*", flags=re.UNICODE)


def _extract_title(md_text: str, fallback: str) -> str:
    """Возвращает текст первого H1 (без emoji-префикса), либо fallback."""
    m = _H1_RE.search(md_text)
    if not m:
        return fallback
    title = m.group(1).strip()
    # Убираем ведущие emoji/звёзды/прочие символы (например, "📜 Хроника..." -> "Хроника...")
    cleaned = _EMOJI_PREFIX_RE.sub("", title).strip()
    return cleaned or title


def _make_md() -> "MarkdownIt":
    """Создать парсер с включёнными таблицами и переносами строк."""
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": False})
    md.enable("table")
    md.enable("strikethrough")
    return md


def _wrap_html(title: str, body_html: str) -> str:
    safe_title = html_lib.escape(title)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
{_CSS}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""


def render_md_to_html(md_path: Path, html_path: Path | None = None) -> Path:
    """
    Конвертировать один .md в .html.

    html_path — куда писать. Если None: тот же путь, расширение заменяется на .html.
    Возвращает фактический путь к созданному HTML.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown-файл не найден: {md_path}")

    md_text = md_path.read_text(encoding="utf-8")
    md = _make_md()
    body_html = md.render(md_text)

    title = _extract_title(md_text, fallback=md_path.stem)
    html_doc = _wrap_html(title, body_html)

    if html_path is None:
        html_path = md_path.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_doc, encoding="utf-8")
    return html_path


def render_md_to_html_safe(md_path: Path) -> Path | None:
    """То же, но не падает при ошибке — печатает её и возвращает None.

    Удобно для авто-вызова из stats/analyzer: даже если HTML
    не сгенерируется, основной результат (.md) уже сохранён.
    """
    try:
        return render_md_to_html(md_path)
    except Exception as e:  # noqa: BLE001
        print(f"  [HTML] Не удалось сконвертировать {md_path.name}: "
              f"{type(e).__name__}: {e}")
        return None


def render_all(cfg: Config) -> tuple[int, int]:
    """
    Прогнать ВСЕ .md, созданные инструментом, через рендер.

    Покрывает:
      - data/stats/*.md
      - data/reports/<chat>/*.md (включая final_report.md)
      - data/parts/<chat>/index.md и participants.md (тоже Markdown)

    Возвращает (успешно, всего).
    """
    cfg.ensure_dirs()

    targets: list[Path] = []
    targets.extend(sorted(cfg.stats_dir.glob("*.md")))

    if cfg.reports_dir.exists():
        for sub in sorted(cfg.reports_dir.iterdir()):
            if sub.is_dir():
                targets.extend(sorted(sub.glob("*.md")))

    if cfg.parts_dir.exists():
        for sub in sorted(cfg.parts_dir.iterdir()):
            if sub.is_dir():
                targets.extend(sorted(sub.glob("*.md")))

    if not targets:
        print("Не найдено .md-файлов для конвертации.")
        return (0, 0)

    print(f"Конвертирую {len(targets)} .md-файлов в HTML...")
    ok = 0
    for src in targets:
        out = render_md_to_html_safe(src)
        if out is not None:
            ok += 1
            try:
                rel = out.relative_to(cfg.project_root)
            except ValueError:
                rel = out
            print(f"  OK  {rel}")
    print(f"\nГотово: {ok}/{len(targets)} файлов.")
    return (ok, len(targets))
