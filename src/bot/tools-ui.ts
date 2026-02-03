/**
 * Tool UI - emojis and funny comments for tool execution
 */

import type { ToolTracker } from './types.js';
import { CONFIG } from '../config.js';

// Tool name → emoji
export function toolEmoji(name: string): string {
  const map: Record<string, string> = {
    'run_command': '⚡',
    'read_file': '📖',
    'write_file': '✏️',
    'edit_file': '🔧',
    'search_files': '🔍',
    'search_text': '🔎',
    'list_directory': '📁',
    'search_web': '🌐',
    'fetch_page': '📥',
    'ask_user': '❓',
    'memory': '🧠',
    'manage_tasks': '📋',
  };
  return map[name] || '🔧';
}

// Funny comments for tools (family-friendly but sassy)
export const TOOL_COMMENTS: Record<string, string[]> = {
  'run_command': [
    'ща запущу...',
    'погнали!',
    'жму кнопки',
    'выполняю приказ',
    'терминал go brrrr',
    'один момент...',
    'колдую в консоли',
    'хакерские штучки',
    '*стук по клавишам*',
    'sudo make me a sandwich',
  ],
  'read_file': [
    'смотрю че там',
    'открываю файлик',
    'читаю с умным видом',
    'изучаю содержимое',
    'а что у нас тут...',
    '*надевает очки*',
    'секундочку, читаю',
  ],
  'write_file': [
    'записываю мудрость',
    'создаю шедевр',
    'пишу код как поэму',
    'файл goes brrr',
    'творю!',
    'сохраняю для потомков',
  ],
  'edit_file': [
    'правлю баги (наверное)',
    'редактирую красоту',
    'улучшаю код',
    'немного магии...',
    'ctrl+s intensifies',
    'делаю код лучше (или хуже)',
  ],
  'search_web': [
    'гуглю...',
    'ищу в интернетах',
    'лезу в сеть',
    'спрашиваю у гугла',
    'исследую веб',
    '*включает режим детектива*',
    'шерстю интернет',
  ],
  'fetch_page': [
    'качаю страничку',
    'скачиваю контент',
    'тяну данные',
    'загружаю...',
  ],
  'memory': [
    'записываю в мозг',
    'сохраняю на память',
    'запоминаю...',
    'кладу в копилочку',
  ],
  'list_directory': [
    'смотрю папочки',
    'листаю файлы',
    'что тут у нас...',
  ],
  'error': [
    'ой, что-то пошло не так',
    'упс, ошибочка',
    'не получилось, блин',
    'капец какой-то',
    'сломалось что-то',
    'хм, это не по плану',
    'ну вот, опять',
    'жесть, не работает',
    'фигня вышла',
  ],
  'success': [
    'готово!',
    'сделано',
    'ок',
    'красота',
    'вуаля!',
    'легко!',
    'изи',
  ],
};

export function getToolComment(toolName: string, isError = false): string {
  const key = isError ? 'error' : toolName;
  const comments = TOOL_COMMENTS[key] || TOOL_COMMENTS['success'];
  return comments[Math.floor(Math.random() * comments.length)];
}

// Track tools for batched status updates
export const toolTrackers = new Map<number, ToolTracker>();
export const TOOL_UPDATE_INTERVAL = CONFIG.status.toolUpdateInterval;
export const MIN_EDIT_INTERVAL_MS = CONFIG.status.minEditInterval;
