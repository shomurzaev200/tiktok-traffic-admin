"""Optional Telegram polling; events are committed before offset is acknowledged."""
import asyncio
import os
from aiogram import Bot
from redis import Redis
from .telegram_service import ingest

async def main():
    token=os.environ['TELEGRAM_BOT_TOKEN']
    bot=Bot(token)
    redis=Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'))
    offset=int(redis.get('telegram_offset') or 0)
    try:
        while True:
            redis.set('heartbeat:telegram_bot','POLLING',ex=90)
            updates=await bot.get_updates(offset=offset,timeout=30,allowed_updates=['chat_member'])
            for item in updates:
                ingest(item.model_dump(mode='json',exclude_none=True))
                offset=item.update_id+1
                redis.set('telegram_offset',offset)
    finally:
        await bot.session.close()

if __name__=='__main__': asyncio.run(main())
