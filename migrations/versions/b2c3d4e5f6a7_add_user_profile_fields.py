"""add user profile fields

Revision ID: b2c3d4e5f6a7
Revises: efd0bdaf869b
Create Date: 2026-09-24 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'efd0bdaf869b'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('users')]

    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'phone_number' not in existing_columns:
            batch_op.add_column(sa.Column('phone_number', sa.String(length=50), nullable=True))
        if 'department' not in existing_columns:
            batch_op.add_column(sa.Column('department', sa.String(length=100), nullable=True))
        if 'company_name' not in existing_columns:
            batch_op.add_column(sa.Column('company_name', sa.String(length=150), nullable=True))
        if 'job_title' not in existing_columns:
            batch_op.add_column(sa.Column('job_title', sa.String(length=100), nullable=True))
        if 'address' not in existing_columns:
            batch_op.add_column(sa.Column('address', sa.String(length=255), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('users')]

    with op.batch_alter_table('users', schema=None) as batch_op:
        for col_name in ['address', 'job_title', 'company_name', 'department', 'phone_number']:
            if col_name in existing_columns:
                batch_op.drop_column(col_name)
