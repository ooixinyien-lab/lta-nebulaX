"""create PS1 persistence schema"""
from alembic import op
from backend.app.db.models import Base

revision = "0001_ps1_database"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    Base.metadata.drop_all(op.get_bind())
