"""add_output_rule_to_prompt_template

Revision ID: 31b876598103
Revises: 2affbf5bb484
Create Date: 2026-03-05 22:57:27.810075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31b876598103'
down_revision: Union[str, Sequence[str], None] = '2affbf5bb484'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
