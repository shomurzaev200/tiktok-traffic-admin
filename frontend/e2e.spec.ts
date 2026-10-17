import {test,expect} from '@playwright/test';
test('вход, реестр аккаунтов и неоновая панель',async({page})=>{
 await page.goto('http://127.0.0.1:8000');
 await page.getByLabel('Логин',{exact:true}).fill(process.env.ADMIN_USER??'admin');
 await page.getByLabel('Пароль',{exact:true}).fill(process.env.ADMIN_PASSWORD??'');
 await page.getByRole('button',{name:'Войти',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Обзор',exact:true})).toBeVisible();
 await page.screenshot({path:'test-results/neon-dashboard.png',fullPage:true});
 await page.getByRole('button',{name:'TikTok-аккаунты',exact:true}).click();
 await page.getByRole('button',{name:'Добавить',exact:true}).click();
 const suffix=Date.now().toString();
 await page.getByLabel('Имя аккаунта без @').fill('e2e'+suffix);
 await page.getByLabel('Ссылка на профиль TikTok').fill('https://www.tiktok.com/@e2e'+suffix);
 await page.getByLabel('Владелец',{exact:true}).fill('E2E operator');
 await page.getByRole('button',{name:'Сохранить',exact:true}).click();
 await expect(page.getByText('e2e'+suffix,{exact:true})).toBeVisible();
 await page.screenshot({path:'test-results/neon-accounts.png',fullPage:true});
 for(const [name,heading] of [['Каталог авторов','Каталог авторов'],['Мониторинг видео','Мониторинг видео'],['Комментарии','Комментарии'],['Черновики и модерация','Черновики и модерация'],['AI-центр','AI-центр'],['Очередь задач','Очередь задач'],['Кампании','Кампании'],['Telegram-каналы','Telegram-каналы'],['Ссылки и переходы','Ссылки и переходы'],['Аналитика','Аналитика'],['Конверсии','Конверсии'],['Уведомления','Уведомления'],['Центр ошибок','Центр ошибок'],['Интеграции','Интеграции'],['Планировщик','Планировщик'],['Системные журналы','Системные журналы'],['Резервные копии','Резервные копии'],['Пользователи и роли','Пользователи и роли'],['Настройки','Настройки'],['Архив первой версии','Архив первой версии']]){
  await page.getByRole('button',{name,exact:true}).click();
  await expect(page.getByRole('heading',{name:heading,exact:true}).first()).toBeVisible();
 }
 await page.getByRole('button',{name:'Выйти',exact:true}).click();
 await expect(page.getByRole('heading',{name:'С возвращением'})).toBeVisible();
});
