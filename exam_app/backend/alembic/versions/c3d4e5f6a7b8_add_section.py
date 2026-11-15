"""add section column to questions

Revision ID: c3d4e5f6a7b8
Revises: b7f3a9c2d1e4
Create Date: 2026-11-14 06:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b7f3a9c2d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "questions" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("questions")}
    if "section" not in cols:
        op.add_column("questions", sa.Column("section", sa.String(length=128), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "questions" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("questions")}
        if "section" in cols:
            op.drop_column("questions", "section")
