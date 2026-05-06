"""
Прогон всех частей чата через Claude API + сборка финального отчёта.

Каждый чат живёт в своей подпапке: cfg.parts_dir/<slug>/part_*.txt.
Соответствующие отчёты пишутся в cfg.reports_dir/<slug>/:
    part_*.md       — отчёты по каждой части
    final_report.md — итоговый сводный отчёт

Все настройки берутся из Config (.env): MODEL_PARTS, MODEL_FINAL,
PARALLEL_WORKERS, MAX_TOKENS_PART, MAX_TOKENS_FINAL,
ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL.

Промпты — из prompts/*.md (см. tg_analyzer.prompts).
"""

from __future__ import annotations

import concurrent.futures as cf
import sys
import time
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    sys.exit("Установи библиотеку: pip install anthropic")

from .config import Config
from .html_render import render_md_to_html_safe
from .paths import reports_subdir_for_parts
from .prompts import load_system_prompt_final, load_system_prompt_part


def _make_client(cfg: Config) -> Anthropic:
    api_key = cfg.require_anthropic()
    base_url = cfg.anthropic_base_url_or_none
    if base_url:
        print(f"[INFO] Использую кастомный base_url: {base_url}")
        return Anthropic(api_key=api_key, base_url=base_url)
    return Anthropic(api_key=api_key)


def _analyze_part(
    client: Anthropic,
    cfg: Config,
    system_prompt: str,
    part_path: Path,
    report_path: Path,
) -> tuple[str, bool, str]:
    """Анализ одной части. Возвращает (имя_файла, успех, сообщение)."""
    if report_path.exists():
        return (part_path.name, True, "пропущено (уже есть отчёт)")

    text = part_path.read_text(encoding="utf-8")
    user_msg = f"Вот часть переписки для анализа:\n\n```\n{text}\n```"

    try:
        chunks: list[str] = []
        with client.messages.stream(
            model=cfg.model_parts,
            max_tokens=cfg.max_tokens_part,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_msg}],
        ) as stream:
            for piece in stream.text_stream:
                chunks.append(piece)
            final_msg = stream.get_final_message()

        content = "".join(chunks)
        report_path.write_text(content, encoding="utf-8")
        usage = final_msg.usage
        cache_info = ""
        if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
            cache_info = f", cache_read={usage.cache_read_input_tokens}"
        stop_warn = ""
        if final_msg.stop_reason == "max_tokens":
            stop_warn = " ⚠️ УПЁРСЯ В max_tokens — отчёт обрезан!"
        return (
            part_path.name,
            True,
            f"in={usage.input_tokens}, out={usage.output_tokens}{cache_info}{stop_warn}",
        )
    except Exception as e:
        return (part_path.name, False, f"ОШИБКА: {e}")


def _build_final_report(client: Anthropic, cfg: Config, reports_subdir: Path) -> None:
    reports = sorted(reports_subdir.glob("part_*.md"))
    if not reports:
        print(f"Нет промежуточных отчётов в {reports_subdir}, пропускаю финал.")
        return

    final_path = reports_subdir / "final_report.md"

    print(f"\n[FINAL] Собираю финальный отчёт из {len(reports)} промежуточных "
          f"(чат: {reports_subdir.name})...")

    combined = []
    for r in reports:
        combined.append(f"\n\n=== {r.name} ===\n\n{r.read_text(encoding='utf-8')}")
    user_msg = "Промежуточные отчёты по периодам:" + "".join(combined)

    system_prompt = load_system_prompt_final(cfg)

    try:
        chunks: list[str] = []
        printed = 0
        with client.messages.stream(
            model=cfg.model_final,
            max_tokens=cfg.max_tokens_final,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        ) as stream:
            for piece in stream.text_stream:
                chunks.append(piece)
                printed += len(piece)
                if printed >= 500:
                    print(".", end="", flush=True)
                    printed = 0
            final_msg = stream.get_final_message()
        print()

        final_path.write_text("".join(chunks), encoding="utf-8")
        final_html = render_md_to_html_safe(final_path)
        usage = final_msg.usage
        print(f"[FINAL] Готово: {final_path}")
        if final_html is not None:
            print(f"        HTML:   {final_html}")
        print(f"        in={usage.input_tokens}, out={usage.output_tokens}")
        if final_msg.stop_reason == "max_tokens":
            print("        ⚠️  Уперлись в max_tokens — финальный отчёт обрезан, "
                  "увеличь MAX_TOKENS_FINAL")
    except Exception as e:
        print(f"[FINAL] ОШИБКА: {e}")


def run_analyze(cfg: Config, parts_subdir: Path) -> None:
    """Анализ всех частей в указанной подпапке + сборка финального отчёта.

    parts_subdir — конкретная папка вида data/parts/<slug>.
    Отчёты пишутся в data/reports/<slug>/.
    """
    if not parts_subdir.exists():
        raise FileNotFoundError(
            f"Нет папки {parts_subdir}. Сначала запусти разделение чата."
        )

    parts = sorted(parts_subdir.glob("part_*.txt"))
    if not parts:
        raise FileNotFoundError(
            f"Нет файлов part_*.txt в {parts_subdir}. Сначала запусти разделение чата."
        )

    cfg.ensure_dirs()
    reports_subdir = reports_subdir_for_parts(cfg, parts_subdir)
    reports_subdir.mkdir(parents=True, exist_ok=True)

    client = _make_client(cfg)
    system_prompt = load_system_prompt_part(cfg)

    print(f"Чат: {parts_subdir.name}")
    print(f"Найдено {len(parts)} частей. Запускаю в {cfg.parallel_workers} потоков...")
    t0 = time.time()

    with cf.ThreadPoolExecutor(max_workers=cfg.parallel_workers) as ex:
        futures = {}
        for p in parts:
            report_path = reports_subdir / (p.stem + ".md")
            futures[ex.submit(_analyze_part, client, cfg, system_prompt, p, report_path)] = p.name

        done = 0
        for fut in cf.as_completed(futures):
            name, ok, msg = fut.result()
            done += 1
            mark = "OK " if ok else "ERR"
            print(f"  [{done:>2}/{len(parts)}] {mark}  {name}  ({msg})")

    print(f"\nЭтап анализа частей завершён за {time.time() - t0:.1f}с")
    _build_final_report(client, cfg, reports_subdir)


def run_final_only(cfg: Config, reports_subdir: Path) -> None:
    """Только пересборка финального отчёта из существующих part_*.md в указанной подпапке."""
    if not reports_subdir.exists():
        raise FileNotFoundError(f"Нет папки {reports_subdir}.")
    cfg.ensure_dirs()
    client = _make_client(cfg)
    _build_final_report(client, cfg, reports_subdir)
