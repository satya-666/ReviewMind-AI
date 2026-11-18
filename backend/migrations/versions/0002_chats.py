"""Account-owned saved conversations."""
from alembic import op
import sqlalchemy as sa
revision='0002_chats'
down_revision='0001_feedback'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('chats',sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('owner',sa.String(255),nullable=False),sa.Column('title',sa.String(100),nullable=False),
      sa.Column('messages',sa.JSON(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_chats_owner','chats',['owner'])
    op.create_index('ix_chats_updated_at','chats',['updated_at'])

def downgrade():
    op.drop_table('chats')
