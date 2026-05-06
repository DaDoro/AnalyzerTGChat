"""
Чтение шаблонов промптов из papki prompts/.

Шаблоны: company_context.md, part_analysis.md, final_report.md.
В part_analysis.md и final_report.md плейсхолдер {company_context}
заменяется содержимым company_context.md.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config


_COMPANY_PLACEHOLDER = "{company_context}"


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"Не найден файл промпта: {path}. "
            f"Восстановите его из репозитория или создайте вручную."
        )
    return path.read_text(encoding="utf-8").strip()


def load_company_context(cfg: Config) -> str:
    return _read(cfg.prompts_dir / "company_context.md")


def load_system_prompt_part(cfg: Config) -> str:
    template = _read(cfg.prompts_dir / "part_analysis.md")
    company = load_company_context(cfg)
    return template.replace(_COMPANY_PLACEHOLDER, company)


def load_system_prompt_final(cfg: Config) -> str:
    template = _read(cfg.prompts_dir / "final_report.md")
    company = load_company_context(cfg)
    return template.replace(_COMPANY_PLACEHOLDER, company)
