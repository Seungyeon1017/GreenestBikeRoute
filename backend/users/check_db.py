"""Shows which users settings were read and whether the database answers. From the repo root:

    uv run python -m backend.users.check_db
    docker compose -f compose.yml -f compose.users.yml exec backend python -m backend.users.check_db
"""
import sys

from sqlalchemy import create_engine, make_url, text

from backend.users.config import UserSettings


def main() -> None:
    # UserSettings() directly, not get_settings(): that one would invent a random secret if none is set.
    settings = UserSettings()

    print("Settings read from USERS_* environment variables / .env:")
    for name in ("database_hostname", "database_port", "database_username", "database_name",
                 "access_token_expire_minutes"):
        print(f"  {name:<28} {getattr(settings, name)}")
    # Never print secrets, only whether they're set.
    print(f"  {'database_password':<28} {'set' if settings.database_password else 'EMPTY'}")
    print(f"  {'jwt_secret_key':<28} {'set' if settings.jwt_secret_key else 'NOT SET (tokens reset on restart)'}")
    print(f"  {'URL':<28} {make_url(settings.database_url).render_as_string(hide_password=True)}")

    print("\nConnecting...")
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            print("  OK:", conn.scalar(text("select version()")))
            has_users = conn.scalar(text("select to_regclass('public.users')")) is not None
            print("  users table:", "exists" if has_users else "missing (run: alembic -c backend/users/alembic.ini upgrade head)")
            if has_users:
                print("  migration:", conn.scalar(text("select version_num from alembic_version")))
                print("  users:", conn.scalar(text("select count(*) from users")))
    except Exception as error:  # show the reason, not a long traceback
        print(f"  FAILED: {type(error).__name__}: {str(error).splitlines()[0]}")
        print("  Check: is the database running, and do hostname/port/username/password match it?")
        sys.exit(1)


if __name__ == "__main__":
    main()