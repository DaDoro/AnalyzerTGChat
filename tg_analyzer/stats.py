"""
Статистика слов по CSV-экспорту чата.

Параметры min_len и top_n берутся из Config (.env).
Результат сохраняется в data/stats/<chat_slug>.md (а не в консоль).
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from .config import Config
from .paths import chat_slug_from_csv


_WORD_RE = re.compile(r"\b[а-яёА-ЯЁa-zA-Z]+\b")
_MENTION_RE = re.compile(r"@\w+")


def _format_md(
    csv_name: str,
    min_len: int,
    top_n: int,
    word_counter: Counter,
    user_counters: dict[str, Counter],
) -> str:
    total_words = sum(word_counter.values())
    unique_words = len(word_counter)

    lines: list[str] = []
    lines.append(f"# Статистика слов: {csv_name}")
    lines.append("")
    lines.append("## Общая статистика")
    lines.append("")
    lines.append(f"- **Файл:** `{csv_name}`")
    lines.append(f"- **Минимальная длина слова:** {min_len}")
    lines.append(f"- **Всего слов (с повторами):** {total_words:,}".replace(",", " "))
    lines.append(f"- **Уникальных слов:** {unique_words:,}".replace(",", " "))
    lines.append(f"- **Участников чата:** {len(user_counters)}")
    lines.append("")

    lines.append(f"## ТОП-{top_n} слов во всём чате (от {min_len} символов)")
    lines.append("")
    lines.append("| # | Слово | Кол-во |")
    lines.append("|---:|---|---:|")
    for i, (word, count) in enumerate(
        sorted(word_counter.items(), key=lambda x: -x[1])[:top_n], 1
    ):
        lines.append(f"| {i} | {word} | {count} |")
    lines.append("")

    lines.append("## Статистика по участникам")
    lines.append("")

    for sender in sorted(user_counters.keys(), key=lambda s: -sum(user_counters[s].values())):
        counter = user_counters[sender]
        total = sum(counter.values())
        short_name = sender.split("(")[0].strip() if "(" in sender else sender

        lines.append(f"### {short_name}")
        lines.append("")
        lines.append(f"- Всего слов: **{total:,}**".replace(",", " "))
        lines.append("")
        lines.append(f"Топ-{top_n}:")
        lines.append("")
        lines.append("| # | Слово | Кол-во |")
        lines.append("|---:|---|---:|")
        for i, (word, count) in enumerate(
            sorted(counter.items(), key=lambda x: -x[1])[:top_n], 1
        ):
            lines.append(f"| {i} | {word} | {count} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def run_stats(cfg: Config, csv_path: Path) -> Path:
    """Анализ слов в CSV. Записывает .md в cfg.stats_dir и возвращает путь к нему."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Файл не найден: {csv_path}")

    cfg.ensure_dirs()

    min_len = cfg.min_len
    top_n = cfg.top_n

    word_counter: Counter[str] = Counter()
    user_counters: dict[str, Counter[str]] = {}

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text", "")
            sender = row.get("sender_name", "Unknown")

            if not text:
                continue

            text_clean = _MENTION_RE.sub("", text)
            words = _WORD_RE.findall(text_clean.lower())
            words = [w for w in words if len(w) >= min_len]

            word_counter.update(words)
            user_counters.setdefault(sender, Counter()).update(words)

    md = _format_md(csv_path.name, min_len, top_n, word_counter, user_counters)

    out_path = cfg.stats_dir / f"{chat_slug_from_csv(csv_path)}.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"Готово. Статистика сохранена: {out_path}")
    print(f"  Всего слов: {sum(word_counter.values()):,}".replace(",", " "))
    print(f"  Уникальных: {len(word_counter):,}".replace(",", " "))
    print(f"  Участников: {len(user_counters)}")

    # Авто-генерация HTML рядом
    from .html_render import render_md_to_html_safe
    html_path = render_md_to_html_safe(out_path)
    if html_path is not None:
        print(f"  HTML:       {html_path}")

    return out_path
