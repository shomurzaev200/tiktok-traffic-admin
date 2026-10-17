export type Row=Record<string,unknown>;
export type Field=string|string[];
export type Catalog={fields:Record<string,Record<string,Field>>;labels:Record<string,string>;role:string};
let csrf='';
export function setCsrf(value:string){csrf=value;}
export async function api<T=Row>(path:string,method='GET',body?:unknown):Promise<T>{
 const response=await fetch(path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await response.json().catch(()=>({detail:'Ответ сервера не распознан'}));
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:`Ошибка ${response.status}`);
 return data as T;
}
export const labels:Record<string,string>={id:'ID',username:'Аккаунт',owner:'Владелец',profile_url:'Профиль',name:'Название',note:'Заметка',status:'Статус',
 created_at:'Создано',updated_at:'Изменено',account_id:'Аккаунт #',campaign_id:'Кампания #',video_id:'Видео #',claimed_by:'Оператор #',source_comment_id:'Комментарий #',
 text:'Текст',author:'Автор',description:'Описание',url:'Видео',kind:'Тип',attempts:'Попытки',last_error:'Ошибка',message:'Сообщение',role:'Роль',active:'Активен',
 channel_id:'Канал #',chat_id:'Telegram ID',members:'Подписчиков (последняя проверка)',invite_url:'Приглашение',slug:'Код перехода',result_url:'Результат',
 clicks:'Переходы',joins:'Вступления',leaves:'Выходы',conversion:'Конверсия, %',cost_per_subscriber:'Цена подписчика',spend:'Расходы',budget:'Бюджет',
 actor_id:'Оператор #',action:'Действие',entity:'Раздел',entity_id:'Запись #',external_comment_id:'Внешний ID',platform:'Платформа',source_text:'Исходный комментарий',
 account_type:'Тип аккаунта',last_sync:'Последняя синхронизация',token_expires_at:'Срок авторизации',published_at:'Подтверждено оператором',
 external_id:'ID видео',creator_id:'Автор #',operator_id:'Оператор #',category:'Категория',language:'Язык',country:'Страна',priority:'Приоритет',goal:'Цель',kpi:'KPI',
 payload:'Параметры',result:'Результат',due_at:'Запланировано',lease_until:'Резерв до',idempotency_key:'Ключ идемпотентности',
 correlation_id:'ID диагностики',service:'Сервис',code:'Код',filename:'Файл',sha256:'SHA256',bytes:'Размер',interval_minutes:'Интервал, минут',enabled:'Включён',next_run:'Следующий запуск',
 value:'Значение',user_hash:'Анонимный ID участника',update_id:'ID Telegram update',input_tokens:'Входные токены',output_tokens:'Выходные токены',provider:'Провайдер',model:'Модель',error:'Ошибка'};
export const states:Record<string,string>={AUTH_REQUIRED:'Ручной учёт · вход не выполнен',NOT_SUPPORTED:'Недоступно',CONNECTED:'Подключён',DISCONNECTED:'Отключён',PAUSED:'Приостановлен',OWN:'Свой',PARTNER:'Партнёрский',
 NEW:'Новое',DRAFTED:'Черновик',REVIEW:'На проверке',APPROVED:'Одобрен',PUBLISHED:'Опубликовано вручную',SKIPPED:'Отклонён',DRAFT:'Черновик',ACTIVE:'Активна',COMPLETED:'Завершена',ARCHIVED:'Архив',
 PENDING:'Ожидает',RUNNING:'Выполняется',SUCCESS:'Успешно',FAILED:'Ошибка',RETRY:'Повтор',CANCELLED:'Отменено',MANUAL:'Ручной импорт',NOT_CHECKED:'Не проверено',VERIFIED:'Права подтверждены',
 UNREAD:'Не прочитано',READ:'Прочитано',OPEN:'Открыта',RESOLVED:'Решена',JOIN:'Вступление',LEAVE:'Выход',IN_REVIEW:'На проверке',
 SYSTEM_CHECK:'Проверка системы',TELEGRAM_SYNC:'Синхронизация Telegram',AI_GENERATION:'Подготовка AI',telegram_subscribers:'Подписчики Telegram',channel_visits:'Переходы в канал',engagement:'Вовлечённость',brand_awareness:'Узнаваемость'};
export function show(value:unknown):string{if(value===null||value===undefined||value==='')return 'Нет данных';if(typeof value==='boolean')return value?'Да':'Нет';if(typeof value==='object')return JSON.stringify(value);return states[String(value)]??String(value);}
