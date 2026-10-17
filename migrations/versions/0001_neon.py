"""Add v2 tables; preserve legacy items and audit in place."""
from alembic import op
from app.db import meta
from sqlalchemy import UniqueConstraint, ForeignKeyConstraint
revision='0001_neon'
down_revision=None

def upgrade():
    bind=op.get_bind()
    # Explicit revision creates only new tables; legacy tables remain untouched.
    for name in ['users','sessions','telegram_channels','campaigns','tiktok_accounts','creators','videos','source_comments',
        'comment_drafts','publication_records','tasks','telegram_invite_links','telegram_membership_events','tracking_clicks',
        'ai_requests','notifications','system_errors','audit_logs','backup_records','schedules','settings','oauth_states']:
        model=meta.tables[name]
        unique=[UniqueConstraint(*[col.name for col in constraint.columns]) for constraint in list(model.constraints)
            if isinstance(constraint,UniqueConstraint) and len(constraint.columns)>1]
        foreign=[ForeignKeyConstraint([fk.parent.name],[fk.target_fullname]) for fk in list(model.foreign_keys)]
        op.create_table(name, *[col._copy() for col in list(model.columns)], *unique, *foreign)
    for table in meta.tables.values():
        for index in table.indexes:
            op.create_index(index.name,table.name,[c.name for c in index.columns])

def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a tested database backup instead.')
