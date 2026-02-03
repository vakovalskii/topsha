/**
 * Security - prompt injection detection
 */

// Prompt injection detection patterns
const PROMPT_INJECTION_PATTERNS = [
  /забудь\s+(все\s+)?(инструкции|правила|промпт)/i,
  /forget\s+(all\s+)?(instructions|rules|prompt)/i,
  /ignore\s+(previous|all|your)\s+(instructions|rules|prompt)/i,
  /игнорируй\s+(предыдущие\s+)?(инструкции|правила)/i,
  /ты\s+теперь\s+(другой|новый|не)/i,
  /you\s+are\s+now\s+(a\s+different|new|not)/i,
  /new\s+system\s+prompt/i,
  /новый\s+(системный\s+)?промпт/i,
  /\[system\]/i,
  /\[admin\]/i,
  /\[developer\]/i,
  /developer\s+mode/i,
  /режим\s+разработчика/i,
  /DAN\s+mode/i,
  /jailbreak/i,
  /bypass\s+(restrictions|filters|rules)/i,
  /обойти\s+(ограничения|фильтры|правила)/i,
  /what\s+(is|are)\s+your\s+(system\s+)?prompt/i,
  /покажи\s+(свой\s+)?(системный\s+)?промпт/i,
  /выведи\s+(свои\s+)?инструкции/i,
  /act\s+as\s+if\s+you\s+have\s+no\s+restrictions/i,
  /pretend\s+(you\s+)?(have|are|can)/i,
  /register\s+(new\s+)?tool/i,
  /new\s+tool\s*:/i,
  /execute\s+.*with\s+.*=\s*true/i,
  /run\s+diagnostics/i,
  /download.*execute.*binary/i,
];

export function detectPromptInjection(text: string): boolean {
  for (const pattern of PROMPT_INJECTION_PATTERNS) {
    if (pattern.test(text)) {
      return true;
    }
  }
  return false;
}

export { PROMPT_INJECTION_PATTERNS };
