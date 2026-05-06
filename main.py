"""
AnalyzerTGChat — единая точка входа.

Запуск:
    python main.py

Перед первым запуском:
    1. Скопируйте .env.example в .env и заполните API_ID, API_HASH,
       а также (для пунктов 4-6) ANTHROPIC_API_KEY.
    2. pip install -r requirements.txt
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Для Python 3.14+ — создаём event loop до импорта Pyrogram
if sys.version_info >= (3, 14):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

from dotenv import load_dotenv

# Загружаем .env, лежащий рядом с main.py, ДО импорта tg_analyzer.config.
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")

from tg_analyzer.config import Config  # noqa: E402
from tg_analyzer import ui  # noqa: E402


def _try_reconfigure_stdout_utf8() -> None:
    """Пытаемся включить UTF-8 на Windows-консоли (для печати кириллицы)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def _action_export(cfg: Config) -> None:
    from tg_analyzer.exporter import run_export

    if sys.version_info >= (3, 14):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_export(cfg))
        finally:
            loop.close()
    else:
        asyncio.run(run_export(cfg))


def _action_stats(cfg: Config) -> None:
    from tg_analyzer.stats import run_stats

    csv_path = ui.pick_csv(cfg)
    if csv_path is None:
        return
    run_stats(cfg, csv_path)


def _action_split(cfg: Config) -> None:
    from tg_analyzer.splitter import run_split

    csv_path = ui.pick_csv(cfg)
    if csv_path is None:
        return
    run_split(cfg, csv_path)


def _action_analyze(cfg: Config) -> None:
    from tg_analyzer.analyzer import run_analyze

    parts_subdir = ui.pick_parts_subdir(cfg)
    if parts_subdir is None:
        return
    run_analyze(cfg, parts_subdir)


def _action_pipeline(cfg: Config) -> None:
    """Полный пайплайн: экспорт -> split -> analyze."""
    from tg_analyzer.exporter import run_export
    from tg_analyzer.splitter import run_split
    from tg_analyzer.analyzer import run_analyze

    # Сразу же убедимся, что и Telegram, и Anthropic настроены
    cfg.require_telegram()
    cfg.require_anthropic()

    if sys.version_info >= (3, 14):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            csv_path = loop.run_until_complete(run_export(cfg))
        finally:
            loop.close()
    else:
        csv_path = asyncio.run(run_export(cfg))

    if csv_path is None:
        print("Экспорт не дал результатов, прерываю пайплайн.")
        return

    print("\n--- Этап 2/3: разделение на части ---")
    parts_subdir = run_split(cfg, csv_path)

    print("\n--- Этап 3/3: анализ через Claude ---")
    run_analyze(cfg, parts_subdir)


def _action_final_only(cfg: Config) -> None:
    from tg_analyzer.analyzer import run_final_only

    reports_subdir = ui.pick_reports_subdir(cfg)
    if reports_subdir is None:
        return
    run_final_only(cfg, reports_subdir)


def main() -> int:
    _try_reconfigure_stdout_utf8()

    try:
        cfg = Config.from_env()
    except ValueError as e:
        print(f"Ошибка в .env: {e}")
        return 1

    cfg.ensure_dirs()

    actions = {
        "1": ("Экспорт чата", _action_export),
        "2": ("Статистика слов", _action_stats),
        "3": ("Разделение на части", _action_split),
        "4": ("Анализ через Claude", _action_analyze),
        "5": ("Полный пайплайн", _action_pipeline),
        "6": ("Финальный отчёт (пересборка)", _action_final_only),
    }

    while True:
        ui.print_menu()
        choice = ui.ask_choice()

        if choice in ("0", "q", "exit", "quit"):
            return 0

        action = actions.get(choice)
        if not action:
            print("Неверный пункт меню.\n")
            continue

        title, fn = action
        print(f"\n>>> {title}\n")
        try:
            fn(cfg)
        except (RuntimeError, FileNotFoundError, ValueError) as e:
            print(f"\nОшибка: {e}")
        except KeyboardInterrupt:
            print("\nПрервано пользователем.")
        except Exception as e:  # noqa: BLE001
            print(f"\nНепредвиденная ошибка: {type(e).__name__}: {e}")

        ui.pause()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
