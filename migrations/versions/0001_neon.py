"""Add v2 tables; preserve legacy items and audit in place."""
from alembic import op
from app.db import meta
revision='0001_neon'
down_revision=None

def upgrade():
    bind=op.get_bind()
    # Explicit revision creates only new tables; legacy tables remain untouched.
    for name in ['users','sessions','telegram_channels','campaigns','tiktok_accounts','creators','videos','source_comments',
        'comment_drafts','publication_records','tasks','telegram_invite_links','telegram_membership_events','tracking_clicks',
        'ai_requests','notifications','system_errors','audit_logs','backup_records','schedules','settings','oauth_states']:
        op.create_table(name, *[c._copy() for c in meta.tables[name].columns],
            *[c._copy() for c in meta.tables[name].constraints if c.__class__.__name__=='UniqueConstraint'])
    for table in meta.tables.values():
        for index in table.indexes:
            op.create_index(index.name,table.name,[c.name for c in index.columns])

def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a tested database backup instead.')
