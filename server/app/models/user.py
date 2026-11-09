import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AuthSource, UserRole


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ux_users_ldap_uid",
            "ldap_uid",
            unique=True,
            postgresql_where=text("ldap_uid IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    default_meal_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meal_types.id"), nullable=True
    )
    auth_source: Mapped[AuthSource] = mapped_column(
        Enum(AuthSource, name="auth_source"),
        default=AuthSource.local,
        server_default=AuthSource.local.value,
    )
    ldap_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ldap_dn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
