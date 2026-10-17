import hashlib
import hmac
import os
import secrets
import httpx
from fastapi import Body, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .db import engine, channels, links, campaigns, events, now
from .security import log

def telegram(method,payload=None):
    token=os.getenv('TELEGRAM_BOT_TOKEN','')
    if not token: raise HTTPException(409,'TELEGRAM_BOT_TOKEN не задан')
    try:
        response=httpx.post(f'https://api.telegram.org/bot{token}/{method}',json=payload or {},timeout=15)
        result=response.json()
    except Exception: raise HTTPException(502,'Telegram недоступен; токен не записывается в журнал')
    if not result.get('ok'): raise HTTPException(502,'Telegram отклонил запрос: проверьте токен, ID канала и права бота')
    return result['result']

def sync_channel(channel_id):
    with engine.connect() as c: row=c.execute(select(channels).where(channels.c.id==channel_id)).mappings().first()
    if not row: raise HTTPException(404,'Канал не найден')
    me=telegram('getMe'); member=telegram('getChatMember',{'chat_id':row['chat_id'],'user_id':me['id']})
    if member['status'] not in ('administrator','creator') or not member.get('can_invite_users',member['status']=='creator'):
        raise HTTPException(409,'Боту нужны права администратора и приглашения пользователей')
    count=telegram('getChatMemberCount',{'chat_id':row['chat_id']})
    with engine.begin() as c: c.execute(update(channels).where(channels.c.id==channel_id).values(status='VERIFIED',members=count))
    return {'status':'VERIFIED','members':count}

def register_routes(app,current,require):
    @app.post('/api/telegram/channels/{channel_id}/sync')
    def sync(channel_id:int,user=Depends(current)):
        require(user,'ADMIN'); result=sync_channel(channel_id)
        with engine.begin() as c: log(c,user,'telegram_sync','channels',channel_id)
        return result

    @app.post('/api/telegram/invite-links')
    def invite(data:dict=Body(...),user=Depends(current)):
        require(user,'ADMIN')
        try: campaign_id=int(data['campaign_id'])
        except (KeyError,TypeError,ValueError): raise HTTPException(422,'Нужен ID кампании')
        with engine.connect() as c: campaign=c.execute(select(campaigns).where(campaigns.c.id==campaign_id)).mappings().first()
        if not campaign or not campaign['channel_id']: raise HTTPException(422,'Назначьте канал кампании')
        sync_channel(campaign['channel_id'])
        with engine.connect() as c: channel=c.execute(select(channels).where(channels.c.id==campaign['channel_id'])).mappings().one()
        result=telegram('createChatInviteLink',{'chat_id':channel['chat_id'],'name':f'Campaign {campaign_id}'})
        with engine.begin() as c:
            row=c.execute(links.insert().values(campaign_id=campaign_id,channel_id=channel['id'],invite_url=result['invite_link'],slug=secrets.token_hex(12)).returning(links)).mappings().one()
            log(c,user,'create_invite','links',row['id'])
        return dict(row)

def ingest(update_data):
    item=update_data.get('chat_member')
    if not item: return False
    def member(value): return value.get('status') in ('creator','administrator','member') or (value.get('status')=='restricted' and value.get('is_member'))
    before=member(item['old_chat_member']); after=member(item['new_chat_member'])
    if before==after: return False
    user_id=str(item['new_chat_member']['user']['id'])
    hashed=hmac.new(os.environ['ADMIN_PASSWORD'].encode(),user_id.encode(),hashlib.sha256).hexdigest()
    try:
        with engine.begin() as c:
            channel=c.execute(select(channels).where(channels.c.chat_id==str(item['chat']['id']))).mappings().first()
            if not channel: return False
            link_url=(item.get('invite_link') or {}).get('invite_link')
            campaign_id=c.scalar(select(links.c.campaign_id).where(links.c.invite_url==link_url)) if link_url else None
            if before and not after:
                campaign_id=c.scalar(select(events.c.campaign_id).where(events.c.channel_id==channel['id'],events.c.user_hash==hashed,events.c.kind=='JOIN').order_by(events.c.id.desc()).limit(1))
            c.execute(events.insert().values(update_id=update_data['update_id'],channel_id=channel['id'],user_hash=hashed,kind='JOIN' if after else 'LEAVE',campaign_id=campaign_id))
        return True
    except IntegrityError: return False
