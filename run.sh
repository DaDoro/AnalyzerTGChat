#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# === 1. Создаём .env, если его нет ===
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo
        echo "Создан файл .env из .env.example."
        echo "Откройте .env, заполните API_ID, API_HASH и ANTHROPIC_API_KEY,"
        echo "затем запустите ./run.sh снова."
        echo
        exit 0
    else
        echo "Не найден .env.example — повреждена установка."
        exit 1
    fi
fi

# === 2. Создаём venv, если его нет ===
if [ ! -x ".venv/bin/python" ]; then
    echo "Создаю виртуальное окружение .venv ..."
    python3 -m venv .venv
fi

# === 3. Активируем venv и ставим зависимости ===
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -d ".venv/lib/python"*"/site-packages/anthropic" ] 2>/dev/null; then
    echo "Устанавливаю зависимости..."
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
fi

# === 4. Запуск ===
python main.py
