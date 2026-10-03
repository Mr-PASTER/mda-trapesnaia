"""Создание/обновление аккаунта оператора (главный администратор).

Использование:
    uv run python -m app.create_operator --login root --full-name "Главный оператор"
    uv run python -m app.create_operator --login root --password 'S3cret!'
    uv run python -m app.create_operator --login root --reset-password   # сменить пароль существующему

Без --password пароль запрашивается интерактивно (getpass).

Скрипт идемпотентен и безопасен:
  * если логин свободен — создаёт оператора;
  * если оператор уже есть и не передан --reset-password — сообщает об этом и выходит без изменений;
  * если логин занят пользователем с другой ролью — отказывает;
  * с --reset-password обновляет пароль/ФИО и активирует аккаунт.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User, UserRole

MIN_PASSWORD_LENGTH = 4


class InvalidInput(Exception):
    """Некорректные входные данные (логин/пароль)."""


class NotOperator(Exception):
    """Логин занят пользователем с ролью, отличной от оператора."""


class PasswordResetRequired(Exception):
    """Оператор с таким логином уже существует; нужен --reset-password."""


async def ensure_operator(
    db: AsyncSession,
    *,
    login: str,
    full_name: str,
    password: str,
    reset_password: bool = False,
) -> User:
    """Создаёт оператора или (с reset_password) обновляет существующего."""
    login = login.lower().strip()
    full_name = full_name.strip() or "Оператор"

    if not login:
        raise InvalidInput("Логин не может быть пустым.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise InvalidInput(
            f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов."
        )

    existing = (
        await db.execute(select(User).where(User.login == login))
    ).scalar_one_or_none()

    if existing is not None:
        if existing.role != UserRole.operator:
            raise NotOperator(login)
        if not reset_password:
            raise PasswordResetRequired(login)
        existing.password_hash = hash_password(password)
        existing.full_name = full_name
        existing.is_active = True
        await db.flush()
        return existing

    user = User(
        login=login,
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.operator,
    )
    db.add(user)
    await db.flush()
    return user


async def run(
    *, login: str, full_name: str, password: str, reset_password: bool = False
) -> User:
    """Обёртка над ensure_operator со своей сессией и коммитом (для CLI)."""
    async with SessionLocal() as db:
        user = await ensure_operator(
            db,
            login=login,
            full_name=full_name,
            password=password,
            reset_password=reset_password,
        )
        await db.commit()
        return user


def _read_password(cli_password: str | None) -> str:
    if cli_password:
        return cli_password
    password = getpass.getpass("Пароль оператора: ")
    confirm = getpass.getpass("Повторите пароль: ")
    if password != confirm:
        raise InvalidInput("Пароли не совпадают.")
    return password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.create_operator",
        description="Создать или обновить аккаунт оператора (главного администратора).",
    )
    parser.add_argument("--login", help="Логин оператора (если не задан — запросится).")
    parser.add_argument(
        "--full-name",
        dest="full_name",
        default="",
        help="ФИО оператора (по умолчанию «Оператор»).",
    )
    parser.add_argument(
        "--password",
        help="Пароль (если не задан — запросится интерактивно).",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Сменить пароль/ФИО существующему оператору.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        login = (args.login or input("Логин оператора: ")).strip()
        full_name = args.full_name or input("ФИО (Enter — «Оператор»): ").strip()
        password = _read_password(args.password)
    except InvalidInput as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    try:
        user = asyncio.run(
            run(
                login=login,
                full_name=full_name,
                password=password,
                reset_password=args.reset_password,
            )
        )
    except InvalidInput as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    except PasswordResetRequired as exc:
        print(
            f"Оператор '{exc}' уже существует. "
            f"Добавьте --reset-password, чтобы сменить пароль.",
            file=sys.stderr,
        )
        return 3
    except NotOperator as exc:
        print(
            f"Логин '{exc}' уже занят пользователем с другой ролью.",
            file=sys.stderr,
        )
        return 4

    print(f"Готово: оператор '{user.login}' ({user.full_name}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
