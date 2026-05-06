"""
Интерактивное меню и хелперы выбора файлов/подпапок.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import Config
from .paths import list_parts_subdirs, list_reports_subdirs


MENU = """\
============================================================
   AnalyzerTGChat — анализ Telegram-чатов
============================================================
1. Экспортировать чат из Telegram
2. Статистика слов по CSV-экспорту (сохранение в .md + HTML)
3. Разделить CSV на части для ИИ
4. Проанализировать части через Claude (+ финальный отчёт)
5. Полный пайплайн (1 → 3 → 4)
6. Только финальный отчёт (пересобрать из готовых part_*.md)
0. Выход
============================================================
"""


def print_menu() -> None:
    print(MENU)


def ask_choice() -> str:
    return input("Выбор: ").strip()


def list_exports(cfg: Config) -> list[Path]:
    """Список CSV-файлов в exports_dir, отсортированный от свежих к старым."""
    if not cfg.exports_dir.exists():
        return []
    files = sorted(
        cfg.exports_dir.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files


def pick_csv(cfg: Config) -> Optional[Path]:
    """Предложить пользователю выбрать CSV из exports/ (по умолчанию — самый свежий)."""
    files = list_exports(cfg)
    if not files:
        print(f"\nВ {cfg.exports_dir} нет CSV-файлов. Сначала запустите экспорт (пункт 1).")
        return None

    print("\n" + "=" * 60)
    print("Выберите CSV-файл (Enter = самый свежий):")
    print("=" * 60)
    for i, p in enumerate(files, 1):
        size_kb = p.stat().st_size / 1024
        print(f"  {i:3}. {p.name}  ({size_kb:,.1f} KB)")
    print("=" * 60)

    choice = input("Номер: ").strip()
    if not choice:
        return files[0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            return files[idx]
    except ValueError:
        pass

    print("Неверный номер.")
    return None


def pick_parts_subdir(cfg: Config) -> Optional[Path]:
    """Выбор подпапки с частями (data/parts/<slug>) — по одной на каждый чат."""
    subs = list_parts_subdirs(cfg)
    if not subs:
        print(f"\nВ {cfg.parts_dir} нет подпапок с part_*.txt. "
              f"Сначала запустите разделение CSV (пункт 3).")
        return None

    if len(subs) == 1:
        print(f"\nИспользую единственную папку с частями: {subs[0].name}")
        return subs[0]

    print("\n" + "=" * 60)
    print("Выберите чат для анализа (Enter = самый свежий):")
    print("=" * 60)
    # Сортируем по mtime: свежий — наверху
    subs_sorted = sorted(subs, key=lambda p: p.stat().st_mtime, reverse=True)
    for i, d in enumerate(subs_sorted, 1):
        n_parts = len(list(d.glob("part_*.txt")))
        print(f"  {i:3}. {d.name}  ({n_parts} частей)")
    print("=" * 60)

    choice = input("Номер: ").strip()
    if not choice:
        return subs_sorted[0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(subs_sorted):
            return subs_sorted[idx]
    except ValueError:
        pass

    print("Неверный номер.")
    return None


def pick_reports_subdir(cfg: Config) -> Optional[Path]:
    """Выбор подпапки с готовыми part_*.md (для пересборки финального отчёта)."""
    subs = list_reports_subdirs(cfg)
    if not subs:
        print(f"\nВ {cfg.reports_dir} нет подпапок с part_*.md. "
              f"Сначала запустите анализ (пункт 4).")
        return None

    if len(subs) == 1:
        print(f"\nИспользую единственную папку с отчётами: {subs[0].name}")
        return subs[0]

    print("\n" + "=" * 60)
    print("Выберите чат для пересборки финального отчёта (Enter = самый свежий):")
    print("=" * 60)
    subs_sorted = sorted(subs, key=lambda p: p.stat().st_mtime, reverse=True)
    for i, d in enumerate(subs_sorted, 1):
        n_md = len(list(d.glob("part_*.md")))
        print(f"  {i:3}. {d.name}  ({n_md} отчётов по частям)")
    print("=" * 60)

    choice = input("Номер: ").strip()
    if not choice:
        return subs_sorted[0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(subs_sorted):
            return subs_sorted[idx]
    except ValueError:
        pass

    print("Неверный номер.")
    return None


def pause() -> None:
    input("\nНажмите Enter для возврата в меню...")
