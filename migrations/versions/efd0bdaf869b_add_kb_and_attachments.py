"""add kb and attachments

Revision ID: efd0bdaf869b
Revises: cade080f4545
Create Date: 2026-09-20 21:33:56.406646

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'efd0bdaf869b'
down_revision = 'cade080f4545'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'knowledge_articles' not in existing_tables:
        op.create_table('knowledge_articles',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=255), nullable=False),
            sa.Column('category', sa.Enum('Network', 'Hardware', 'Software', 'Access and Accounts', 'Email and Communication', 'Server and Infrastructure', name='ticketcategory'), nullable=False),
            sa.Column('summary', sa.String(length=500), nullable=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('tags', sa.String(length=255), nullable=True),
            sa.Column('is_published', sa.Boolean(), nullable=False),
            sa.Column('view_count', sa.Integer(), nullable=False),
            sa.Column('helpful_count', sa.Integer(), nullable=False),
            sa.Column('not_helpful_count', sa.Integer(), nullable=False),
            sa.Column('author_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('knowledge_articles', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_knowledge_articles_category'), ['category'], unique=False)
            batch_op.create_index(batch_op.f('ix_knowledge_articles_created_at'), ['created_at'], unique=False)
            batch_op.create_index(batch_op.f('ix_knowledge_articles_is_published'), ['is_published'], unique=False)
            batch_op.create_index(batch_op.f('ix_knowledge_articles_slug'), ['slug'], unique=True)
            batch_op.create_index(batch_op.f('ix_knowledge_articles_tags'), ['tags'], unique=False)
            batch_op.create_index(batch_op.f('ix_knowledge_articles_title'), ['title'], unique=False)

    if 'deflection_logs' not in existing_tables:
        op.create_table('deflection_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('article_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('search_query', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['article_id'], ['knowledge_articles.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('deflection_logs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_deflection_logs_article_id'), ['article_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_deflection_logs_created_at'), ['created_at'], unique=False)
            batch_op.create_index(batch_op.f('ix_deflection_logs_user_id'), ['user_id'], unique=False)

    if 'ticket_attachments' not in existing_tables:
        op.create_table('ticket_attachments',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('ticket_id', sa.Integer(), nullable=False),
            sa.Column('uploader_id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['uploader_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('ticket_attachments', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_ticket_attachments_created_at'), ['created_at'], unique=False)
            batch_op.create_index(batch_op.f('ix_ticket_attachments_ticket_id'), ['ticket_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_ticket_attachments_uploader_id'), ['uploader_id'], unique=False)

    if 'notifications' in existing_tables:
        existing_cols = [c['name'] for c in inspector.get_columns('notifications')]
        existing_indexes = [i['name'] for i in inspector.get_indexes('notifications')]
        with op.batch_alter_table('notifications', schema=None) as batch_op:
            if 'message' not in existing_cols:
                batch_op.add_column(sa.Column('message', sa.Text(), nullable=False, server_default=''))
            if 'icon' not in existing_cols:
                batch_op.add_column(sa.Column('icon', sa.String(length=32), nullable=False, server_default='bell'))
            if 'is_read' not in existing_cols:
                batch_op.add_column(sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('0')))
            if 'read_at' not in existing_cols:
                batch_op.add_column(sa.Column('read_at', sa.DateTime(), nullable=True))
            if 'ix_notifications_is_read' not in existing_indexes:
                batch_op.create_index('ix_notifications_is_read', ['is_read'], unique=False)

            for col in ['error_message', 'status', 'sent_at', 'attempts', 'last_attempt_at', 'max_attempts']:
                if col in existing_cols:
                    batch_op.drop_column(col)


def downgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_attempts', sa.INTEGER(), nullable=False))
        batch_op.add_column(sa.Column('last_attempt_at', sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('attempts', sa.INTEGER(), nullable=False))
        batch_op.add_column(sa.Column('sent_at', sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.VARCHAR(length=7), nullable=False))
        batch_op.add_column(sa.Column('error_message', sa.VARCHAR(length=500), nullable=True))
        batch_op.drop_index(batch_op.f('ix_notifications_is_read'))

    with op.batch_alter_table('ticket_attachments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ticket_attachments_uploader_id'))
        batch_op.drop_index(batch_op.f('ix_ticket_attachments_ticket_id'))
        batch_op.drop_index(batch_op.f('ix_ticket_attachments_created_at'))

    op.drop_table('ticket_attachments')
    with op.batch_alter_table('deflection_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deflection_logs_user_id'))
        batch_op.drop_index(batch_op.f('ix_deflection_logs_created_at'))
        batch_op.drop_index(batch_op.f('ix_deflection_logs_article_id'))

    op.drop_table('deflection_logs')
    with op.batch_alter_table('knowledge_articles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_title'))
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_tags'))
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_slug'))
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_is_published'))
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_created_at'))
        batch_op.drop_index(batch_op.f('ix_knowledge_articles_category'))

    op.drop_table('knowledge_articles')
