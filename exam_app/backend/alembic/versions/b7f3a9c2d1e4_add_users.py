"""add users and exam owner index

Revision ID: b7f3a9c2d1e4
Revises: 2692c533f049
Create Date: 2026-11-14 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f3a9c2d1e4"
down_revision: Union[str, Sequence[str], None] = "2692c533f049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the users table and index exams.owner_id.

    The checks make this safe on databases where ``create_all`` already made
    the table, and on fresh databases.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    if "exams" in tables:
        indexes = {ix["name"] for ix in inspector.get_indexes("exams")}
        if "ix_exams_owner_id" not in indexes:
            op.create_index(op.f("ix_exams_owner_id"), "exams", ["owner_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "exams" in tables:
        indexes = {ix["name"] for ix in inspector.get_indexes("exams")}
        if "ix_exams_owner_id" in indexes:
            op.drop_index(op.f("ix_exams_owner_id"), table_name="exams")

    if "users" in tables:
        op.drop_index(op.f("ix_users_username"), table_name="users")
        op.drop_table("users")
