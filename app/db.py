import os
from datetime import datetime, timezone
from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, BigInteger, String,
    Text, DateTime, Boolean, ForeignKey, UniqueConstraint, JSON, Float)
from sqlalchemy.engine import URL

def now(): return datetime.now(timezone.utc)
url = os.getenv('DATABASE_URL') or URL.create('postgresql+psycopg', username=os.getenv('DB_USER','traffic'),
    password=os.getenv('DB_PASSWORD',''), host=os.getenv('DB_HOST','db'), database=os.getenv('DB_NAME','traffic'))
engine = create_engine(url, pool_pre_ping=True, pool_size=5) if not str(url).startswith('sqlite') else create_engine(url)
meta = MetaData()

def table(name, *columns, constraints=()):
    return Table(name, meta, Column('id',Integer,primary_key=True), *columns,
        Column('created_at',DateTime(timezone=True),default=now,nullable=False),
        Column('updated_at',DateTime(timezone=True),default=now,onupdate=now,nullable=False), *constraints)

users=table('users',Column('username',String(80),unique=True,nullable=False),Column('password_hash',Text,nullable=False),
    Column('role',String(30),nullable=False),Column('active',Boolean,default=True,nullable=False))
sessions=table('sessions',Column('token_hash',String(64),unique=True,nullable=False),Column('user_id',ForeignKey('users.id'),nullable=False),
    Column('csrf',String(64),nullable=False),Column('expires_at',DateTime(timezone=True),nullable=False))
channels=table('telegram_channels',Column('name',String(120),nullable=False),Column('chat_id',String(80),unique=True,nullable=False),
    Column('status',String(30),default='NOT_CHECKED'),Column('members',Integer))
campaigns=table('campaigns',Column('name',String(120),nullable=False),Column('description',Text,default=''),
    Column('goal',String(40),default='telegram_subscribers'),Column('channel_id',ForeignKey('telegram_channels.id')),
    Column('status',String(30),default='DRAFT'),Column('budget',Float,default=0),Column('spend',Float,default=0),Column('kpi',Integer,default=0))
accounts=table('tiktok_accounts',Column('username',String(80),unique=True,nullable=False),Column('profile_url',Text,nullable=False),
    Column('owner',String(120),default=''),Column('account_type',String(30),default='OWN'),Column('status',String(30),default='AUTH_REQUIRED'),
    Column('campaign_id',ForeignKey('campaigns.id')),Column('note',Text,default=''),Column('open_id',String(150),unique=True),
    Column('token_encrypted',Text),Column('token_expires_at',DateTime(timezone=True)),Column('last_sync',DateTime(timezone=True)))
creators=table('creators',Column('username',String(80),unique=True,nullable=False),Column('profile_url',Text,nullable=False),
    Column('category',String(80),default=''),Column('language',String(20),default='ru'),Column('country',String(60),default=''),
    Column('priority',Integer,default=0),Column('status',String(30),default='MANUAL'),Column('campaign_id',ForeignKey('campaigns.id')))
videos=table('videos',Column('url',Text,unique=True,nullable=False),Column('external_id',String(100)),Column('creator_id',ForeignKey('creators.id')),
    Column('account_id',ForeignKey('tiktok_accounts.id')),Column('campaign_id',ForeignKey('campaigns.id')),Column('description',Text,default=''),
    Column('status',String(30),default='NEW'),Column('operator_id',ForeignKey('users.id')),Column('note',Text,default=''))
comments=table('source_comments',Column('platform',String(20),default='tiktok',nullable=False),Column('external_comment_id',String(150),nullable=False),
    Column('campaign_id',ForeignKey('campaigns.id'),nullable=False),Column('video_id',ForeignKey('videos.id'),nullable=False),
    Column('text',Text,default=''),Column('author',String(120),default=''),
    constraints=(UniqueConstraint('platform','external_comment_id','campaign_id'),))
drafts=table('comment_drafts',Column('source_comment_id',ForeignKey('source_comments.id'),unique=True,nullable=False),
    Column('account_id',ForeignKey('tiktok_accounts.id'),nullable=False),Column('text',Text,default=''),Column('status',String(30),default='DRAFTED'),
    Column('claimed_by',ForeignKey('users.id')),Column('result_url',Text,default=''),Column('published_at',DateTime(timezone=True)))
publications=table('publication_records',Column('draft_id',ForeignKey('comment_drafts.id'),unique=True,nullable=False),
    Column('idempotency_key',String(64),unique=True,nullable=False),Column('operator_id',ForeignKey('users.id'),nullable=False),
    Column('result_url',Text,nullable=False),Column('method',String(30),default='MANUAL_CONFIRMED'))
tasks=table('tasks',Column('kind',String(40),nullable=False),Column('payload',JSON,nullable=False,default=dict),Column('status',String(30),default='PENDING'),
    Column('attempts',Integer,default=0),Column('due_at',DateTime(timezone=True),default=now),Column('lease_until',DateTime(timezone=True)),
    Column('last_error',String(200),default=''),Column('result',JSON),Column('idempotency_key',String(100),unique=True,nullable=False))
links=table('telegram_invite_links',Column('campaign_id',ForeignKey('campaigns.id'),nullable=False),Column('channel_id',ForeignKey('telegram_channels.id'),nullable=False),
    Column('invite_url',Text,unique=True,nullable=False),Column('slug',String(40),unique=True,nullable=False))
events=table('telegram_membership_events',Column('update_id',BigInteger,unique=True,nullable=False),Column('channel_id',ForeignKey('telegram_channels.id'),nullable=False),
    Column('user_hash',String(64),nullable=False),Column('kind',String(10),nullable=False),Column('campaign_id',ForeignKey('campaigns.id')))
clicks=table('tracking_clicks',Column('link_id',ForeignKey('telegram_invite_links.id'),nullable=False))
ai_requests=table('ai_requests',Column('draft_id',ForeignKey('comment_drafts.id')),Column('provider',String(30)),Column('model',String(100)),
    Column('status',String(30)),Column('input_tokens',Integer,default=0),Column('output_tokens',Integer,default=0),Column('error',String(100),default=''))
notifications=table('notifications',Column('message',Text,nullable=False),Column('key',String(160),unique=True,nullable=False),Column('status',String(20),default='UNREAD'))
errors=table('system_errors',Column('service',String(40)),Column('code',String(80)),Column('message',String(200)),Column('correlation_id',String(64)),
    Column('severity',String(20),default='ERROR'),Column('task_id',ForeignKey('tasks.id')),Column('account_id',ForeignKey('tiktok_accounts.id')),
    Column('retry_count',Integer,default=0),Column('status',String(20),default='OPEN'))
audit=table('audit_logs',Column('actor_id',ForeignKey('users.id')),Column('action',String(80)),Column('entity',String(60)),Column('entity_id',Integer))
backups=table('backup_records',Column('filename',String(120),unique=True),Column('sha256',String(64)),Column('bytes',BigInteger),Column('status',String(30)))
schedules=table('schedules',Column('name',String(120),nullable=False),Column('kind',String(40),nullable=False),Column('interval_minutes',Integer,default=1440),
    Column('enabled',Boolean,default=True),Column('next_run',DateTime(timezone=True),default=now))
settings=table('settings',Column('name',String(100),unique=True,nullable=False),Column('value',Text,default=''))
oauth_states=table('oauth_states',Column('state',String(64),unique=True),Column('user_id',ForeignKey('users.id')),Column('expires_at',DateTime(timezone=True)))

TABLES = {'accounts':accounts,'creators':creators,'videos':videos,'comments':comments,'drafts':drafts,'campaigns':campaigns,
    'channels':channels,'links':links,'events':events,'tasks':tasks,'notifications':notifications,'errors':errors,'audit':audit,
    'backups':backups,'users':users,'schedules':schedules,'settings':settings,'ai-requests':ai_requests}
for t in (drafts,tasks,videos,events,audit,clicks):
    from sqlalchemy import Index
    Index(f'ix_{t.name}_created_id',t.c.created_at,t.c.id)
