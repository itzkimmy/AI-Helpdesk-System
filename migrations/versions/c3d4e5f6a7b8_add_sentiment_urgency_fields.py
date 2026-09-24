"""add sentiment and urgency fields to classification_predictions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-24 09:47:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('classification_predictions')]

    with op.batch_alter_table('classification_predictions', schema=None) as batch_op:
        if 'sentiment_label' not in existing_columns:
            batch_op.add_column(sa.Column('sentiment_label', sa.String(length=50), nullable=True))
        if 'sentiment_score' not in existing_columns:
            batch_op.add_column(sa.Column('sentiment_score', sa.Float(), nullable=True))
        if 'urgency_score' not in existing_columns:
            batch_op.add_column(sa.Column('urgency_score', sa.Integer(), nullable=True))
        if 'urgency_triggers' not in existing_columns:
            batch_op.add_column(sa.Column('urgency_triggers', sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('classification_predictions')]

    with op.batch_alter_table('classification_predictions', schema=None) as batch_op:
        for col_name in ['urgency_triggers', 'urgency_score', 'sentiment_score', 'sentiment_label']:
            if col_name in existing_columns:
                batch_op.drop_column(col_name)
