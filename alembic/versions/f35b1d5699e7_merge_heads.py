"""merge_heads

Revision ID: f35b1d5699e7
Revises: 4830b44beec0, 5c160f1d8aa1
Create Date: 2026-03-13 00:55:09.831836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f35b1d5699e7'
down_revision: Union[str, Sequence[str], None] = ('4830b44beec0', '5c160f1d8aa1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
