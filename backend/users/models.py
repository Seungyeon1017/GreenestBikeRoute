"""Database tables (SQLAlchemy). After changing one, create a migration (see migrations/README)."""
from datetime import datetime

from sqlalchemy import DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from backend.users.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    # Stored in lower case (see router.py), so "Anna@x.de" and "anna@x.de" are the same account.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Never the password itself: an Argon2 hash from security.hash_password().
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    # False blocks login without deleting the account.
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r})"