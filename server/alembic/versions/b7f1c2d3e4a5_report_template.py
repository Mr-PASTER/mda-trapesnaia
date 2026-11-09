"""report template

Revision ID: b7f1c2d3e4a5
Revises: 01fe93c155e1
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f1c2d3e4a5"
down_revision: Union[str, Sequence[str], None] = "01fe93c155e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("show_subtotal", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "report_group_halls",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["group_id"], ["report_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "hall_id"),
    )
    op.create_table(
        "report_totals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("all_halls", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "report_total_halls",
        sa.Column("total_id", sa.Uuid(), nullable=False),
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["total_id"], ["report_totals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("total_id", "hall_id"),
    )


def downgrade() -> None:
    op.drop_table("report_total_halls")
    op.drop_table("report_totals")
    op.drop_table("report_group_halls")
    op.drop_table("report_groups")
