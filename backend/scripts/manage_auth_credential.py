"""Admin CLI to initialize or update the single authorized login credential in MongoDB."""

from __future__ import annotations

import argparse
import asyncio
import getpass
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.mongodb import MongoAuthDatabase  # noqa: E402
from app.repositories.auth_repository import AuthRepository  # noqa: E402


async def _run_command(args: argparse.Namespace) -> int:
    settings = get_settings()
    mongo = MongoAuthDatabase(
        url=settings.MONGODB_URL,
        database_name=settings.MONGODB_DATABASE,
        collection_name=settings.MONGODB_COLLECTION,
        connect_timeout_ms=settings.MONGODB_CONNECT_TIMEOUT_MS,
    )
    await mongo.connect()
    repo = AuthRepository(mongo)
    await repo.ensure_indexes()

    try:
        if args.action == "status":
            existing = await repo.get_authorized_account()
            if existing is None:
                print("Status: NO_CREDENTIAL (authorized_account not initialized)")
                return 1
            print(
                f"Status: INITIALIZED id={existing.id} username={existing.username} "
                f"is_active={existing.is_active} updated_at={existing.updated_at}"
            )
            return 0

        if args.action in {"init", "update"}:
            existing = await repo.get_authorized_account()
            if args.action == "init" and existing is not None:
                print(
                    f"Authorized account already exists (username={existing.username}). "
                    "Use 'update' to intentionally rotate credentials."
                )
                return 1

            username = (args.username or "").strip()
            if not username:
                username = input("Authorized username: ").strip()
            if not username:
                print("Error: username must not be empty.", file=sys.stderr)
                return 2

            password = args.password
            if not password:
                password = getpass.getpass("Authorized password: ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    print("Error: passwords do not match.", file=sys.stderr)
                    return 2
            if len(password) < 8:
                print("Error: password must be at least 8 characters.", file=sys.stderr)
                return 2

            password_hash = hash_password(password)
            if args.action == "init":
                record, created = await repo.create_initial_authorized_account(
                    username=username,
                    password_hash=password_hash,
                    is_active=True,
                )
                print(
                    f"Created authorized account: id={record.id} username={record.username} created={created}"
                )
            else:
                record = await repo.upsert_authorized_account(
                    username=username,
                    password_hash=password_hash,
                    is_active=True,
                )
                print(
                    f"Updated authorized account: id={record.id} username={record.username} updated_at={record.updated_at}"
                )
            return 0

        if args.action in {"activate", "deactivate"}:
            is_active = args.action == "activate"
            record = await repo.set_account_active(is_active)
            if record is None:
                print("Error: authorized account does not exist yet.", file=sys.stderr)
                return 1
            print(f"Account '{record.username}' is_active={record.is_active}")
            return 0

        return 2
    finally:
        await mongo.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage the single authorized credential stored in MongoDB."
    )
    parser.add_argument(
        "action",
        choices=["status", "init", "update", "activate", "deactivate"],
        help="Administrative credential operation.",
    )
    parser.add_argument("--username", help="Username for init/update.")
    parser.add_argument(
        "--password",
        help="Optional password for non-interactive automation (prompted securely if omitted).",
    )
    parsed = parser.parse_args()
    return asyncio.run(_run_command(parsed))


if __name__ == "__main__":
    raise SystemExit(main())
