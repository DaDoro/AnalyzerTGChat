"""
Утилиты для построения путей под отдельный чат.

Имя CSV-файла из exporter: chat_export_<TITLE>_<TIMESTAMP>.csv.
Slug чата = имя файла без расширения и без префикса 'chat_export_'.
Такой slug используется как имя подпапки в data/parts и data/reports,
чтобы разные чаты не смешивались.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config


_EXPORT_PREFIX = "chat_export_"


def chat_slug_from_csv(csv_path: Path) -> str:
    """Превратить путь к CSV-экспорту в slug подпапки."""
    stem = csv_path.stem  # без .csv
    if stem.startswith(_EXPORT_PREFIX):
        stem = stem[len(_EXPORT_PREFIX):]
    # Чистим: оставляем буквы/цифры/подчёркивания/дефисы/точки/пробелы.
    safe = "".join(c if c.isalnum() or c in (" ", "-", "_", ".") else "_" for c in stem)
    safe = safe.strip().replace(" ", "_")
    return safe or "chat"


def parts_subdir_for(cfg: Config, csv_path: Path) -> Path:
    return cfg.parts_dir / chat_slug_from_csv(csv_path)


def reports_subdir_for_parts(cfg: Config, parts_subdir: Path) -> Path:
    """Папка отчётов, соответствующая папке частей."""
    return cfg.reports_dir / parts_subdir.name


def list_parts_subdirs(cfg: Config) -> list[Path]:
    """Все подпапки в data/parts/, в которых есть part_*.txt."""
    if not cfg.parts_dir.exists():
        return []
    out = []
    for d in sorted(cfg.parts_dir.iterdir()):
        if d.is_dir() and any(d.glob("part_*.txt")):
            out.append(d)
    return out


def list_reports_subdirs(cfg: Config) -> list[Path]:
    """Все подпапки в data/reports/, в которых есть part_*.md."""
    if not cfg.reports_dir.exists():
        return []
    out = []
    for d in sorted(cfg.reports_dir.iterdir()):
        if d.is_dir() and any(d.glob("part_*.md")):
            out.append(d)
    return out
