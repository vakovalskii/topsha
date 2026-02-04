/**
 * Message formatting utilities
 */

import { CONFIG } from '../config.js';

// Escape HTML
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// Convert Markdown table to readable list format
export function convertTable(tableText: string): string {
  const lines = tableText.trim().split('\n');
  if (lines.length < 2) return tableText;
  
  const headerCells = lines[0].split('|').map(c => c.trim()).filter(c => c);
  const dataLines = lines.slice(2);
  
  const result: string[] = [];
  for (const line of dataLines) {
    const cells = line.split('|').map(c => c.trim()).filter(c => c);
    if (cells.length === 0) continue;
    
    const parts = cells.map((cell, i) => {
      const header = headerCells[i] || '';
      return header ? `${header}: ${cell}` : cell;
    });
    result.push(`• ${parts.join(' | ')}`);
  }
  
  return result.join('\n');
}

// Markdown → Telegram HTML
export function mdToHtml(text: string): string {
  const codeBlocks: string[] = [];
  let result = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre>${escapeHtml(code.trim())}</pre>`);
    return `__CODE_BLOCK_${idx}__`;
  });
  
  result = result.replace(/(?:^\|.+\|$\n?)+/gm, (table) => {
    return convertTable(table);
  });
  
  const inlineCode: string[] = [];
  result = result.replace(/`([^`]+)`/g, (_, code) => {
    const idx = inlineCode.length;
    inlineCode.push(`<code>${escapeHtml(code)}</code>`);
    return `__INLINE_CODE_${idx}__`;
  });
  
  // Protect @mentions from formatting (before escapeHtml)
  const mentions: string[] = [];
  result = result.replace(/@[\w_]+/g, (mention) => {
    const idx = mentions.length;
    mentions.push(mention);
    return `\x00MENTION${idx}\x00`;  // Use null bytes as delimiters (won't match markdown patterns)
  });
  
  result = escapeHtml(result);
  
  codeBlocks.forEach((block, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, block);
  });
  inlineCode.forEach((code, i) => {
    result = result.replace(`__INLINE_CODE_${i}__`, code);
  });
  
  result = result
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.+?)\*/g, '<i>$1</i>')
    .replace(/__(.+?)__/g, '<b>$1</b>')
    .replace(/_(.+?)_/g, '<i>$1</i>')
    .replace(/~~(.+?)~~/g, '<s>$1</s>');
  
  // Restore @mentions after formatting
  mentions.forEach((mention, i) => {
    result = result.replace(`\x00MENTION${i}\x00`, mention);
  });
  
  return result;
}

// Split long messages
export function splitMessage(text: string, maxLen = CONFIG.messages.maxLength): string[] {
  if (text.length <= maxLen) return [text];
  
  const parts: string[] = [];
  let current = '';
  
  for (const line of text.split('\n')) {
    if (current.length + line.length + 1 > maxLen) {
      if (current) parts.push(current);
      current = line;
    } else {
      current += (current ? '\n' : '') + line;
    }
  }
  if (current) parts.push(current);
  
  return parts;
}
