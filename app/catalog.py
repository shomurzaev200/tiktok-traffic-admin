"""Editable fields are an explicit allow-list; integration state is never user-editable."""
FIELDS={
 'accounts':{'username':'Имя аккаунта без @','profile_url':'Ссылка на профиль TikTok','owner':'Владелец','account_type':['OWN','PARTNER'],'campaign_id':'Кампания #','note':'Заметка'},
 'creators':{'username':'Имя автора без @','profile_url':'Профиль TikTok','category':'Категория','language':'Язык','country':'Страна (если известна)','priority':'Приоритет','status':['MANUAL','PAUSED'],'campaign_id':'Кампания #'},
 'videos':{'url':'Ссылка на видео TikTok','external_id':'ID видео','creator_id':'Автор #','account_id':'Свой аккаунт # (для собственного видео)','campaign_id':'Кампания #','description':'Описание','note':'Заметка','status':['NEW','IN_REVIEW','APPROVED','SKIPPED'],'operator_id':'Оператор #'},
 'comments':{'external_comment_id':'ID исходного комментария (для ручного учёта можно свой уникальный ID)','campaign_id':'Кампания #','video_id':'Видео #','text':'Текст исходного комментария','author':'Автор комментария'},
 'campaigns':{'name':'Название','description':'Описание','goal':['telegram_subscribers','channel_visits','engagement','brand_awareness'],'channel_id':'Telegram-канал #','status':['DRAFT','ACTIVE','PAUSED','COMPLETED','ARCHIVED'],'budget':'Бюджет','spend':'Фактические расходы','kpi':'Целевые подписки'},
 'channels':{'name':'Название','chat_id':'Telegram chat_id: -100…'},
 'schedules':{'name':'Название','kind':['TELEGRAM_SYNC','SYSTEM_CHECK'],'interval_minutes':'Интервал, минут','enabled':'Включён'},
 'settings':{'name':['disable_animations','report_note'],'value':'Значение'},
}
LABELS={'accounts':'TikTok-аккаунты','creators':'Каталог авторов','videos':'Мониторинг видео','comments':'Исходные комментарии','drafts':'Черновики и модерация',
 'campaigns':'Кампании','channels':'Telegram-каналы','links':'Пригласительные ссылки','events':'События Telegram','tasks':'Очередь задач',
 'notifications':'Уведомления','errors':'Центр ошибок','audit':'Системные журналы','backups':'Резервные копии','users':'Пользователи и роли',
 'schedules':'Планировщик','settings':'Настройки','ai-requests':'История AI'}
HIDDEN={'password_hash','token_encrypted','token_hash','csrf','open_id'}
INTS={'campaign_id','channel_id','creator_id','account_id','operator_id','video_id','source_comment_id','priority','kpi','interval_minutes'}
