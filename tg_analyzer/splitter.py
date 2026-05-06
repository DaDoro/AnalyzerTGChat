"""
Чистка и разбиение CSV-экспорта чата на части для последующего анализа ИИ.

Все настройки берутся из Config (.env): SPLIT_BY, MAX_CHARS_PER_PART,
MERGE_BURSTS_MINUTES, MIN_TEXT_LEN, NORMALIZE_LAUGHTER, DROP_URL_ONLY.

Выход — папка cfg.parts_dir с part_*.txt, index.md, participants.md, stats.json.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .config import Config
from .paths import parts_subdir_for


URL_RE = re.compile(r"^\s*https?://\S+\s*$|^\s*t\.me/\S+\s*$", re.IGNORECASE)
LAUGH_RE = re.compile(r"\b([ахпы])\1{3,}([ахпы]\1*)*\b", re.IGNORECASE)


def _clean_text(text: str, normalize_laughter: bool) -> str:
    if text is None:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if normalize_laughter:
        text = LAUGH_RE.sub(lambda m: m.group(0)[:4], text)
    return text


def _is_url_only(text: str) -> bool:
    return bool(URL_RE.match(text))


def _parse_input(path: Path, normalize_laughter: bool) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                dt = datetime.strptime(f"{r['date']} {r['time']}", "%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                continue
            rows.append({
                "id": r.get("message_id", ""),
                "dt": dt,
                "sender": (r.get("sender_name") or "").strip(),
                "sender_id": r.get("sender_id", ""),
                "text": _clean_text(r.get("text", ""), normalize_laughter),
            })
    return rows


def _filter_rows(rows: list[dict], cfg: Config) -> tuple[list[dict], Counter]:
    out: list[dict] = []
    dropped: Counter = Counter()
    for r in rows:
        if not r["text"] or len(r["text"]) < cfg.min_text_len:
            dropped["empty"] += 1
            continue
        if cfg.drop_url_only and _is_url_only(r["text"]):
            dropped["url_only"] += 1
            continue
        out.append(r)
    return out, dropped


def _merge_bursts(rows: list[dict], minutes: int) -> list[dict]:
    if minutes <= 0 or not rows:
        return rows
    merged = [rows[0].copy()]
    gap = minutes * 60
    for r in rows[1:]:
        last = merged[-1]
        same_author = r["sender_id"] == last["sender_id"] and r["sender"] == last["sender"]
        delta = (r["dt"] - last["dt"]).total_seconds()
        if same_author and 0 <= delta <= gap:
            last["text"] = last["text"] + " " + r["text"]
        else:
            merged.append(r.copy())
    return merged


def _part_key(dt: datetime, split_by: str) -> str:
    if split_by == "month":
        return f"{dt.year}-{dt.month:02d}"
    if split_by == "quarter":
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{q}"
    raise ValueError(f"Неизвестная стратегия split_by={split_by}")


def _format_message(r: dict) -> str:
    return f"[{r['dt'].strftime('%Y-%m-%d %H:%M')}] {r['sender']}: {r['text']}"


def _split_oversized(part_rows: list[dict], max_chars: int) -> list[list[dict]]:
    text_len = sum(len(_format_message(r)) + 1 for r in part_rows)
    if max_chars <= 0 or text_len <= max_chars or len(part_rows) < 2:
        return [part_rows]
    mid = len(part_rows) // 2
    left, right = part_rows[:mid], part_rows[mid:]
    return _split_oversized(left, max_chars) + _split_oversized(right, max_chars)


def run_split(cfg: Config, csv_path: Path) -> Path:
    """Разбивает CSV на части и пишет их в подпапку cfg.parts_dir/<chat_slug>.

    Возвращает путь к подпапке.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Не найден входной файл: {csv_path}")

    cfg.ensure_dirs()
    output_dir = parts_subdir_for(cfg, csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Очищаем старые части и метаданные (на случай повторного запуска с другими параметрами)
    for old in output_dir.glob("part_*.txt"):
        try:
            old.unlink()
        except OSError:
            pass
    for meta_name in ("index.md", "participants.md", "stats.json"):
        meta = output_dir / meta_name
        if meta.exists():
            try:
                meta.unlink()
            except OSError:
                pass

    print(f"[1/5] Читаю {csv_path.name}...")
    rows = _parse_input(csv_path, cfg.normalize_laughter)
    print(f"      Прочитано строк: {len(rows):,}")

    print("[2/5] Сортирую по времени и фильтрую мусор...")
    rows.sort(key=lambda r: r["dt"])
    rows, dropped = _filter_rows(rows, cfg)
    print(f"      После очистки: {len(rows):,}  (выкинуто: {dict(dropped)})")

    if cfg.merge_bursts_minutes > 0:
        before = len(rows)
        rows = _merge_bursts(rows, cfg.merge_bursts_minutes)
        print(f"[3/5] Склейка burst-сообщений (<{cfg.merge_bursts_minutes} мин): "
              f"{before:,} -> {len(rows):,}")
    else:
        print("[3/5] Склейка burst-сообщений отключена.")

    if not rows:
        print("Нет сообщений после очистки — нечего делить.")
        return output_dir

    print(f"[4/5] Группирую по '{cfg.split_by}'...")
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[_part_key(r["dt"], cfg.split_by)].append(r)

    final_parts: list[tuple[str, list[dict]]] = []
    for key in sorted(groups.keys()):
        chunks = _split_oversized(groups[key], cfg.max_chars_per_part)
        if len(chunks) == 1:
            final_parts.append((key, chunks[0]))
        else:
            for i, ch in enumerate(chunks, 1):
                final_parts.append((f"{key}_part{i}", ch))

    print(f"      Получилось частей: {len(final_parts)}")

    print("[5/5] Пишу файлы...")
    index_lines = ["# Index of chat parts\n"]
    participants_total: Counter = Counter()
    stats: dict = {"parts": [], "participants": {}, "total_messages": len(rows)}

    for idx, (label, part_rows) in enumerate(final_parts, 1):
        fname = f"part_{idx:02d}_{label}.txt"
        fpath = output_dir / fname

        per_user = Counter(r["sender"] for r in part_rows)
        participants_total.update(per_user)

        header = (
            f"# Часть {idx}: {label}\n"
            f"# Период: {part_rows[0]['dt']:%Y-%m-%d} — {part_rows[-1]['dt']:%Y-%m-%d}\n"
            f"# Сообщений: {len(part_rows)}\n"
            f"# Активные участники: "
            + ", ".join(f"{n} ({c})" for n, c in per_user.most_common())
            + "\n\n"
        )
        body = "\n".join(_format_message(r) for r in part_rows)
        fpath.write_text(header + body, encoding="utf-8")

        size_kb = fpath.stat().st_size / 1024
        index_lines.append(
            f"- **{fname}** — {part_rows[0]['dt']:%Y-%m-%d} → "
            f"{part_rows[-1]['dt']:%Y-%m-%d}, "
            f"{len(part_rows)} сообщ., {size_kb:.1f} KB"
        )
        stats["parts"].append({
            "file": fname,
            "label": label,
            "from": part_rows[0]["dt"].isoformat(),
            "to": part_rows[-1]["dt"].isoformat(),
            "messages": len(part_rows),
            "size_kb": round(size_kb, 1),
            "per_user": dict(per_user),
        })

    (output_dir / "index.md").write_text("\n".join(index_lines), encoding="utf-8")

    participants_md = ["# Участники чата\n", "| Участник | Сообщений |", "|---|---:|"]
    for name, c in participants_total.most_common():
        participants_md.append(f"| {name} | {c} |")
    (output_dir / "participants.md").write_text("\n".join(participants_md), encoding="utf-8")

    stats["participants"] = dict(participants_total)
    (output_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\nГотово.")
    print(f"  Папка с результатами: {output_dir}")
    print(f"  Частей создано:       {len(final_parts)}")
    print(f"  Всего сообщений:      {len(rows):,}")
    print(f"  Участников:           {len(participants_total)}")
    print(f"  Смотри index.md, participants.md, stats.json")

    return output_dir
