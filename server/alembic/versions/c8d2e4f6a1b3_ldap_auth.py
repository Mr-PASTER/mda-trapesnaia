"""ldap auth

Revision ID: c8d2e4f6a1b3
Revises: b7f1c2d3e4a5
Create Date: 2026-10-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d2e4f6a1b3"
down_revision: Union[str, Sequence[str], None] = "b7f1c2d3e4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    auth_source = sa.Enum("local", "ldap", name="auth_source")
    auth_source.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("auth_source", auth_source, nullable=False, server_default="local"),
    )
    op.add_column("users", sa.Column("ldap_uid", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("ldap_dn", sa.String(length=512), nullable=True))
    op.alter_column(
        "users", "password_hash", existing_type=sa.String(length=255), nullable=True
    )
    op.create_index(
        "ux_users_ldap_uid",
        "users",
        ["ldap_uid"],
        unique=True,
        postgresql_where=sa.text("ldap_uid IS NOT NULL"),
    )


def downgrade() -> None:
    # NULL-пароли у LDAP-записей нужно заполнить заглушкой до отката столбца.
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.drop_index("ux_users_ldap_uid", table_name="users")
    op.alter_column(
        "users", "password_hash", existing_type=sa.String(length=255), nullable=False
    )
    op.drop_column("users", "ldap_dn")
    op.drop_column("users", "ldap_uid")
    op.drop_column("users", "auth_source")
    sa.Enum(name="auth_source").drop(op.get_bind(), checkfirst=True)
