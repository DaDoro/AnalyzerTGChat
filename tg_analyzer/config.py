"""
Единая конфигурация инструмента.

Все настройки берутся из .env (через python-dotenv) либо из переменных окружения.
Если параметр не задан — используется разумный дефолт.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _get_str(name: str, default: str = "") -> str:
    val = os.environ.get(name, "")
    return val.strip() if val.strip() else default


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    # Убираем пробелы и нижние подчёркивания (на случай "250_000")
    raw = raw.replace("_", "").replace(" ", "")
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"Переменная окружения {name}={raw!r} должна быть целым числом"
        )


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "y", "on"):
        return True
    if raw in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError(
        f"Переменная окружения {name}={raw!r} должна быть True/False"
    )


@dataclass
class Config:
    """Единый объект конфигурации, передаваемый в модули."""

    # Корни проекта
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path = field(init=False)
    exports_dir: Path = field(init=False)
    parts_dir: Path = field(init=False)        # корень: внутри подпапки на каждый чат
    reports_dir: Path = field(init=False)      # корень: внутри подпапки на каждый чат
    stats_dir: Path = field(init=False)        # md-файлы статистики
    prompts_dir: Path = field(init=False)
    session_path: Path = field(init=False)
    last_chat_path: Path = field(init=False)

    # Telegram
    api_id: str = ""
    api_hash: str = ""

    # chat_word_stats
    min_len: int = 3
    top_n: int = 30

    # split_chat
    max_chars_per_part: int = 250_000
    merge_bursts_minutes: int = 0
    min_text_len: int = 1
    normalize_laughter: bool = False
    split_by: str = "quarter"  # "quarter" или "month"
    drop_url_only: bool = True

    # analyze_parts
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    model_parts: str = "claude-sonnet-4-6"
    model_final: str = "claude-opus-4-7"
    parallel_workers: int = 4
    max_tokens_part: int = 64_000
    max_tokens_final: int = 32_000

    @classmethod
    def from_env(cls) -> "Config":
        """Создать Config из переменных окружения / .env."""
        cfg = cls(
            api_id=_get_str("API_ID"),
            api_hash=_get_str("API_HASH"),
            min_len=_get_int("MIN_LEN", 3),
            top_n=_get_int("TOP_N", 30),
            max_chars_per_part=_get_int("MAX_CHARS_PER_PART", 250_000),
            merge_bursts_minutes=_get_int("MERGE_BURSTS_MINUTES", 0),
            min_text_len=_get_int("MIN_TEXT_LEN", 1),
            normalize_laughter=_get_bool("NORMALIZE_LAUGHTER", False),
            split_by=_get_str("SPLIT_BY", "quarter").lower(),
            drop_url_only=_get_bool("DROP_URL_ONLY", True),
            anthropic_api_key=_get_str("ANTHROPIC_API_KEY"),
            anthropic_base_url=_get_str("ANTHROPIC_BASE_URL"),
            model_parts=_get_str("MODEL_PARTS", "claude-sonnet-4-6"),
            model_final=_get_str("MODEL_FINAL", "claude-opus-4-7"),
            parallel_workers=_get_int("PARALLEL_WORKERS", 4),
            max_tokens_part=_get_int("MAX_TOKENS_PART", 64_000),
            max_tokens_final=_get_int("MAX_TOKENS_FINAL", 32_000),
        )

        # Базовая папка данных
        base_raw = _get_str("OUTPUT_DIR_BASE", "")
        if base_raw:
            base = Path(base_raw)
            if not base.is_absolute():
                base = cfg.project_root / base
        else:
            base = cfg.project_root / "data"
        cfg.data_dir = base
        cfg.exports_dir = base / "exports"
        cfg.parts_dir = base / "parts"
        cfg.reports_dir = base / "reports"
        cfg.stats_dir = base / "stats"
        cfg.session_path = base / "telegram_session"
        cfg.last_chat_path = base / ".last_chat.json"

        # Папка с промптами
        prompts_raw = _get_str("PROMPTS_DIR", "")
        if prompts_raw:
            prompts = Path(prompts_raw)
            if not prompts.is_absolute():
                prompts = cfg.project_root / prompts
        else:
            prompts = cfg.project_root / "prompts"
        cfg.prompts_dir = prompts

        # Валидация
        if cfg.split_by not in ("quarter", "month"):
            raise ValueError(
                f"SPLIT_BY должен быть 'quarter' или 'month', получено: {cfg.split_by!r}"
            )
        if cfg.parallel_workers < 1:
            raise ValueError("PARALLEL_WORKERS должен быть >= 1")

        return cfg

    def ensure_dirs(self) -> None:
        """Создать все рабочие директории, если их нет."""
        for d in (
            self.data_dir,
            self.exports_dir,
            self.parts_dir,
            self.reports_dir,
            self.stats_dir,
            self.prompts_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def require_telegram(self) -> tuple[int, str]:
        """Проверка наличия Telegram credentials. Возвращает (api_id_int, api_hash)."""
        if not self.api_id or not self.api_hash:
            raise RuntimeError(
                "API_ID и API_HASH не заданы в .env. "
                "Получите их на https://my.telegram.org и пропишите в .env "
                "(см. .env.example)."
            )
        try:
            api_id_int = int(self.api_id)
        except ValueError as e:
            raise RuntimeError(f"API_ID должен быть числом, получено: {self.api_id!r}") from e
        return api_id_int, self.api_hash

    def require_anthropic(self) -> str:
        """Проверка наличия ANTHROPIC_API_KEY. Возвращает ключ."""
        if not self.anthropic_api_key or self.anthropic_api_key.startswith("sk-ant-..."):
            raise RuntimeError(
                "ANTHROPIC_API_KEY не задан в .env (или оставлен placeholder). "
                "Получите ключ на https://console.anthropic.com и пропишите в .env."
            )
        return self.anthropic_api_key

    @property
    def anthropic_base_url_or_none(self) -> Optional[str]:
        """Вернуть base_url, если он отличается от дефолтного, иначе None."""
        if not self.anthropic_base_url:
            return None
        if self.anthropic_base_url.rstrip("/") == "https://api.anthropic.com":
            return None
        return self.anthropic_base_url
