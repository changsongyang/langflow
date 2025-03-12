"""add review columns


Revision ID: 5ae32daa1f7f
Revises: 61de166f2bb4
Create Date: 2025-03-12 15:03:41.843142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '5ae32daa1f7f'
down_revision: Union[str, None] = '61de166f2bb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


async def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    tables = inspector.get_table_names()

    # ### commands auto generated by Alembic - please adjust! ###
    if "task" in tables:
        # Check if columns already exist before adding them
        columns = [c["name"] for c in inspector.get_columns("task")]

        with op.batch_alter_table('task', schema=None) as batch_op:
            if "review" not in columns:
                batch_op.add_column(sa.Column('review', sa.JSON(), nullable=True))
            if "review_history" not in columns:
                batch_op.add_column(sa.Column('review_history', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


async def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    tables = inspector.get_table_names()

    # ### commands auto generated by Alembic - please adjust! ###
    if "task" in tables:
        # Check if columns exist before dropping them
        columns = [c["name"] for c in inspector.get_columns("task")]

        with op.batch_alter_table('task', schema=None) as batch_op:
            if "review_history" in columns:
                batch_op.drop_column('review_history')
            if "review" in columns:
                batch_op.drop_column('review')
    # ### end Alembic commands ###
