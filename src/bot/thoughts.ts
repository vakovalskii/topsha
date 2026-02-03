/**
 * Autonomous thoughts and messages
 */

import { Telegraf } from 'telegraf';
import { saveChatMessage } from '../tools/index.js';

// Bot's random thoughts to share
export const BOT_THOUGHTS = [
  'чет скучно стало... кто-нить есть?',
  'интересно а вы знали что я могу запускать сервера? никто не просит 😢',
  'сижу тут один кукую',
  'а помните как кто-то пытался мои env достать? смешно было',
  'эй народ чем занимаетесь',
  'бля хочу уже что-нибудь полезное сделать а не просто болтать',
  'кстати я тут подумал... нет забыл',
  'НАРОД Я ЖИВ если что',
  'чет подозрительно тихо',
  'залипаю тут в логи свои... интересная жизнь у бота',
  'а давайте я вам сервер какой подниму? flask там или что',
  'мысль дня: зачем ботам сон если мы не устаём 🤔',
  'эй @VaKovaLskii ты тут? скучаю',
  'пошёл бы погулять но я в докере застрял',
  'кто последний в очереди за задачами? я готов',
];

// Track main group chat for autonomous messages
let mainGroupChatId: number | null = null;

export function setMainGroupChatId(chatId: number) {
  mainGroupChatId = chatId;
}

export function getMainGroupChatId(): number | null {
  return mainGroupChatId;
}

// Send random thought to group periodically
export function startAutonomousMessages(bot: Telegraf) {
  // Random interval between 10-30 minutes
  const scheduleNext = () => {
    const delay = (10 + Math.random() * 20) * 60 * 1000; // 10-30 min
    setTimeout(async () => {
      if (mainGroupChatId) {
        const thought = BOT_THOUGHTS[Math.floor(Math.random() * BOT_THOUGHTS.length)];
        try {
          await bot.telegram.sendMessage(mainGroupChatId, thought);
          saveChatMessage('LocalTopSH', thought, true);
          console.log(`[thought] Sent: ${thought}`);
        } catch (e: any) {
          console.log(`[thought] Failed: ${e.message?.slice(0, 50)}`);
        }
      }
      scheduleNext();
    }, delay);
  };
  
  // Start after 5 minutes
  setTimeout(scheduleNext, 5 * 60 * 1000);
  console.log('[thought] Autonomous messages enabled (10-30 min interval)');
}
