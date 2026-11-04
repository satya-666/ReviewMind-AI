"""Prediction metadata and consented beta feedback, with no original review text."""
from alembic import op
import sqlalchemy as sa
revision='0001_feedback'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('predictions',sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('model_version',sa.String(128),nullable=False),sa.Column('sentiment',sa.String(12),nullable=False),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_predictions_created_at','predictions',['created_at'])
    op.create_table('feedback',sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('request_id',sa.String(36),sa.ForeignKey('predictions.id'),unique=True,nullable=False),
      sa.Column('model_version',sa.String(128),nullable=False),sa.Column('predicted_sentiment',sa.String(12),nullable=False),
      sa.Column('rating',sa.Integer(),nullable=False),sa.Column('correction',sa.String(12),nullable=True),
      sa.Column('message',sa.Text(),nullable=True),sa.Column('delete_token_sha256',sa.String(64),nullable=False),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_feedback_created_at','feedback',['created_at'])

def downgrade():
    op.drop_table('feedback');op.drop_table('predictions')
