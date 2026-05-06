"""
Экспорт текстовых сообщений из Telegram-чата через Pyrogram.

API_ID/API_HASH берутся из Config (.env). Сессия Pyrogram хранится в
data/telegram_session, последний выбранный chat_id — в data/.last_chat.json.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pyrogram import Client

from .config import Config


def _load_last_chat(cfg: Config) -> Optional[str]:
    if cfg.last_chat_path.exists():
        try:
            data = json.loads(cfg.last_chat_path.read_text(encoding="utf-8"))
            return data.get("chat_id")
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_last_chat(cfg: Config, chat_id: str) -> None:
    try:
        cfg.last_chat_path.write_text(
            json.dumps({"chat_id": chat_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _clear_last_chat(cfg: Config) -> None:
    if cfg.last_chat_path.exists():
        try:
            cfg.last_chat_path.unlink()
        except OSError:
            pass


async def _select_chat_from_dialogs(client: Client) -> Optional[str]:
    """Выбор чата из списка диалогов."""
    print("\nЗагрузка списка диалогов...")

    dialogs = []
    async for dialog in client.get_dialogs():  # type: ignore[union-attr]
        chat = dialog.chat
        chat_type = chat.type.name if chat.type else "UNKNOWN"

        if chat.title:
            name = chat.title
        else:
            parts = []
            if chat.first_name:
                parts.append(chat.first_name)
            if chat.last_name:
                parts.append(chat.last_name)
            name = " ".join(parts) if parts else (chat.username or str(chat.id))

        if chat_type == "PRIVATE":
            type_label = "Личный"
        elif chat_type == "BOT":
            type_label = "Бот"
        elif chat_type in ("GROUP", "SUPERGROUP"):
            type_label = "Группа"
        elif chat_type == "CHANNEL":
            type_label = "Канал"
        else:
            type_label = chat_type

        dialogs.append({
            "id": chat.id,
            "name": name,
            "type_label": type_label,
            "username": chat.username,
        })

    if not dialogs:
        print("Диалоги не найдены.")
        return None

    print("\n" + "=" * 60)
    print("СПИСОК ДИАЛОГОВ:")
    print("=" * 60)
    for i, d in enumerate(dialogs, 1):
        username_str = f" @{d['username']}" if d["username"] else ""
        print(f"  {i:3}. [{d['type_label']:7}] {d['name']}{username_str}")
    print("=" * 60)
    print("Введите номер чата или нажмите Enter, чтобы ввести вручную")

    choice = input("Номер: ").strip()
    if not choice:
        return None

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(dialogs):
            return str(dialogs[idx]["id"])
    except ValueError:
        pass

    print("Неверный номер.")
    return None


async def _ask_chat_id(cfg: Config, client: Client) -> str:
    saved_chat_id = _load_last_chat(cfg)

    print("=" * 60)
    print("СПОСОБЫ УКАЗАТЬ ЧАТ:")
    print("=" * 60)
    print("1. Выбрать из списка диалогов (введите 'list' или 'l')")
    print("2. Username: @channel_name или просто channel_name")
    print("3. Ссылка: https://t.me/joinchat/XXXX или t.me/channel_name")
    print("4. Числовой ID: -100XXXXXXXXXX (группа/канал)")
    print("                 или положительный ID для личного чата")
    print("5. Номер телефона: +79991234567 (для личных чатов)")
    print()
    print("ВАЖНО: Для личных чатов используйте 'list', username или телефон.")
    if saved_chat_id:
        print(f"\nСохранённый: {saved_chat_id} (нажмите Enter)")
    print("=" * 60)

    chat_id_input = input("ID/Username/'list': ").strip()

    if not chat_id_input and saved_chat_id:
        return saved_chat_id

    if not chat_id_input:
        raise ValueError("ID чата не указан")

    if chat_id_input.lower() in ("list", "l", "список"):
        selected = await _select_chat_from_dialogs(client)
        if not selected:
            raise ValueError("Чат не выбран")
        return selected

    if "t.me/" in chat_id_input:
        parts = chat_id_input.split("t.me/")[-1]
        if "?" in parts:
            parts = parts.split("?")[0]
        if parts.startswith("joinchat/"):
            chat_id_input = parts
        else:
            chat_id_input = parts.replace("/", "")

    return chat_id_input


async def _resolve_chat(client: Client, chat_id: str):
    """Пытается разрешить идентификатор чата разными способами."""
    chat = None
    numeric_chat_id: Any = None

    # 1. Прямой запрос
    try:
        chat = await client.get_chat(chat_id)
    except Exception:
        pass

    # 2. Если похоже на номер телефона
    if not chat and isinstance(chat_id, str) and chat_id.startswith("+"):
        phone = chat_id

        # 2a. По контактам
        try:
            contacts = await client.get_contacts()
            if contacts:
                normalized = phone.lstrip("+")
                for contact in contacts:
                    contact_phone = (getattr(contact, "phone_number", "") or "").lstrip("+")
                    if contact_phone and contact_phone == normalized:
                        try:
                            chat = await client.get_chat(contact.id)
                            break
                        except Exception:
                            pass
        except Exception:
            pass

        # 2b. По диалогам
        if not chat:
            try:
                normalized = phone.lstrip("+")
                async for dialog in client.get_dialogs():  # type: ignore[union-attr]
                    d_chat = dialog.chat
                    d_phone = (getattr(d_chat, "phone_number", "") or "").lstrip("+")
                    if d_phone and d_phone == normalized:
                        chat = d_chat
                        break
            except Exception:
                pass

        # 2c. Импорт временного контакта
        if not chat:
            try:
                from pyrogram.raw.functions.contacts.import_contacts import ImportContacts
                from pyrogram.raw.types.input_phone_contact import InputPhoneContact
                import random

                imported = await client.invoke(ImportContacts(contacts=[
                    InputPhoneContact(  # type: ignore[arg-type]
                        client_id=random.randint(0, 2**31 - 1),
                        phone=phone,
                        first_name="ChatExport",
                        last_name="",
                    )
                ]))
                users_list = getattr(imported, "users", None)
                if users_list:
                    user_id = users_list[0].id
                    try:
                        chat = await client.get_chat(user_id)
                    except Exception:
                        pass
            except Exception as e:
                print(f"  Поиск по телефону не удался: {type(e).__name__}: {e}")
                print("  Telegram позволяет искать по номеру только если он:")
                print("    • уже у вас в контактах,")
                print("    • или у вас уже есть с ним диалог,")
                print("    • или его настройки приватности это разрешают.")
                print("  Совет: введите 'list' для выбора из списка диалогов.")

    # 3. Числовой ID — пробуем варианты
    if not chat:
        try:
            chat_id_int = int(chat_id)
            candidates: list[Any] = [chat_id_int]
            if chat_id_int < 0:
                candidates.append(f"-100{abs(chat_id_int)}")
            else:
                candidates.append(-chat_id_int)
                candidates.append(f"-100{chat_id_int}")
            for cid in candidates:
                try:
                    chat = await client.get_chat(cid)
                    numeric_chat_id = cid
                    break
                except Exception:
                    continue
        except (ValueError, TypeError):
            pass

    return chat, numeric_chat_id


async def _extract_messages(
    client: Client,
    chat_id: str,
    limit: Optional[int] = None,
) -> tuple[list[dict], str]:
    """Извлечение текстовых сообщений из чата."""
    print(f"\n{'=' * 60}")
    print(f"Подключение к чату {chat_id}...")

    chat, numeric_chat_id = await _resolve_chat(client, chat_id)
    chat_title = str(chat_id)

    if not chat:
        print("Не удалось подключиться к чату.")
        print("Убедитесь, что:")
        print("  1. Вы участник этого чата (или общались с этим пользователем)")
        print("  2. Используете правильный username, ID или телефон")
        print("  3. Для списка ваших диалогов введите 'list' при запросе чата")
        return [], chat_title

    title = getattr(chat, "title", None)
    first_name = getattr(chat, "first_name", None)
    last_name = getattr(chat, "last_name", None)
    username = getattr(chat, "username", None)
    chat_obj_id = getattr(chat, "id", chat_id)

    if title:
        chat_title = title
    else:
        parts: list[str] = []
        if first_name:
            parts.append(first_name)
        if last_name:
            parts.append(last_name)
        chat_title = " ".join(parts) if parts else (username or str(chat_obj_id))

    numeric_chat_id = chat_obj_id
    chat_type_obj = getattr(chat, "type", None)
    chat_type = chat_type_obj.name if chat_type_obj is not None else "UNKNOWN"
    print(f"Чат: {chat_title} (тип: {chat_type})")

    messages_data: list[dict] = []
    message_count = 0

    print("Извлечение сообщений (только текст)...\n")

    async for message in client.get_chat_history(numeric_chat_id, limit=limit):
        message_count += 1

        if message.text and message.text.strip():
            sender_name = "Unknown"
            sender_id = 0

            if message.from_user:
                sender_id = message.from_user.id
                sender_name = message.from_user.first_name or ""
                if message.from_user.last_name:
                    sender_name += f" {message.from_user.last_name}"
                if message.from_user.username:
                    sender_name += f" (@{message.from_user.username})"
                sender_name = sender_name.strip()
            elif message.author_signature:
                sender_name = message.author_signature

            date = message.date
            messages_data.append({
                "message_id": message.id,
                "timestamp": date.isoformat() if date else "",
                "date": date.strftime("%Y-%m-%d") if date else "",
                "time": date.strftime("%H:%M:%S") if date else "",
                "sender_id": sender_id,
                "sender_name": sender_name,
                "text": message.text.strip(),
            })

        if message_count % 1000 == 0:
            print(f"  Обработано: {message_count} (текста: {len(messages_data)})")

    return messages_data, chat_title


def _safe_filename_part(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in (" ", "-", "_")).strip()


def _save_csv(messages: list[dict], chat_title: str, output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = _safe_filename_part(chat_title)
    filepath = output_dir / f"chat_export_{safe_title}_{timestamp}.csv"

    with filepath.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "message_id", "date", "time", "sender_name", "sender_id", "text",
        ])
        writer.writeheader()
        for msg in messages:
            row = {k: msg[k] for k in ["message_id", "date", "time", "sender_name", "sender_id", "text"]}
            writer.writerow(row)

    return filepath


async def run_export(cfg: Config) -> Optional[Path]:
    """Полный цикл экспорта. Возвращает путь к CSV или None при ошибке."""
    api_id, api_hash = cfg.require_telegram()
    cfg.ensure_dirs()

    print("=" * 60)
    print("  Извлечение текстовых сообщений из чата")
    print("=" * 60)

    async with Client(
        name=str(cfg.session_path),
        api_id=api_id,
        api_hash=api_hash,
    ) as client:
        chat_id = await _ask_chat_id(cfg, client)

        print("\n" + "=" * 60)
        print("Сколько сообщений извлечь?")
        print("  - Enter или 0: все сообщения")
        print("  - Число: конкретное количество")
        print("=" * 60)
        limit_input = input("Лимит: ").strip()
        limit = int(limit_input) if limit_input and limit_input != "0" else None

        messages, chat_title = await _extract_messages(client, chat_id, limit=limit)

        if not messages:
            _clear_last_chat(cfg)
            return None

        csv_path = _save_csv(messages, chat_title, cfg.exports_dir)

        print("\n" + "=" * 60)
        print("  ЭКСПОРТ ЗАВЕРШЁН")
        print("=" * 60)
        print(f"Извлечено текстовых сообщений: {len(messages)}")
        print(f"Сохранено: {csv_path}")
        print("=" * 60)

        _save_last_chat(cfg, chat_id)
        return csv_path
