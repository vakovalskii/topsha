/**
 * Web tools - Pattern: Action + Object
 * search_web (via Proxy or direct Z.AI), fetch_page
 */

import { CONFIG } from '../config.js';

interface SearchResult {
  title: string;
  url: string;
  content: string;
  date?: string;
}

// Store proxy URL (set at startup)
let proxyUrl: string | undefined;

export function setProxyUrl(url: string | undefined) {
  proxyUrl = url;
  if (url) {
    console.log('[web] Using proxy for API requests');
  }
}

// Z.AI Web Search via Proxy
async function searchViaProxy(query: string): Promise<SearchResult[]> {
  if (!proxyUrl) throw new Error('Proxy URL not configured');
  
  const response = await fetch(`${proxyUrl}/zai/search?q=${encodeURIComponent(query)}`);
  
  if (!response.ok) {
    throw new Error(`Proxy error: ${response.status}`);
  }
  
  const data = await response.json() as { search_result?: any[] };
  return (data.search_result || []).map((r: any) => ({
    title: r.title,
    url: r.link,
    content: r.content,
    date: r.publish_date,
  }));
}

// Z.AI Web Search API (direct, for local dev)
async function searchZai(query: string, apiKey: string): Promise<SearchResult[]> {
  const response = await fetch('https://api.z.ai/api/paas/v4/web_search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      search_engine: 'search-prime',
      search_query: query,
      count: 10,
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Z.AI error: ${response.status}`);
  }
  
  const data = await response.json() as { search_result?: any[] };
  return (data.search_result || []).map((r: any) => ({
    title: r.title,
    url: r.link,
    content: r.content,
    date: r.publish_date,
  }));
}

// Tavily Search API (fallback)
async function searchTavily(query: string, apiKey: string): Promise<SearchResult[]> {
  const { tavily } = await import('@tavily/core');
  const client = tavily({ apiKey });
  const response = await client.search(query, { maxResults: 5 });
  
  return response.results.map((r: any) => ({
    title: r.title,
    url: r.url,
    content: r.content,
  }));
}

// ============ search_web ============
export const searchWebDefinition = {
  type: "function" as const,
  function: {
    name: "search_web",
    description: "Search the internet. USE IMMEDIATELY for: news, current events, external info, 'what is X?', prices, weather.",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
      },
      required: ["query"],
    },
  },
};

export async function executeSearchWeb(
  args: { query: string },
  zaiApiKey?: string,
  tavilyApiKey?: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  try {
    let results: SearchResult[];
    
    // Try Proxy first (most secure)
    if (proxyUrl) {
      try {
        results = await searchViaProxy(args.query);
      } catch (e: any) {
        console.log(`[search] Proxy failed: ${e.message}`);
        // Fall through to direct API
        if (zaiApiKey) {
          results = await searchZai(args.query, zaiApiKey);
        } else if (tavilyApiKey) {
          results = await searchTavily(args.query, tavilyApiKey);
        } else {
          throw e;
        }
      }
    } else if (zaiApiKey) {
      // Direct Z.AI (local dev)
      try {
        results = await searchZai(args.query, zaiApiKey);
      } catch (e) {
        console.log('[search] Z.AI failed, trying Tavily...');
        if (tavilyApiKey) {
          results = await searchTavily(args.query, tavilyApiKey);
        } else {
          throw e;
        }
      }
    } else if (tavilyApiKey) {
      results = await searchTavily(args.query, tavilyApiKey);
    } else {
      return { success: false, error: "No search API configured (PROXY_URL or ZAI_API_KEY)" };
    }
    
    if (!results.length) {
      return { success: true, output: "(no results)" };
    }
    
    const output = results.map((r, i) => {
      const date = r.date ? ` (${r.date})` : '';
      return `[${i + 1}] ${r.title}${date}\n${r.url}\n${r.content.slice(0, 400)}`;
    }).join('\n\n');
    
    return { success: true, output };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

// Z.AI Web Reader via Proxy
async function readPageViaProxy(url: string): Promise<string> {
  if (!proxyUrl) throw new Error('Proxy URL not configured');
  
  const response = await fetch(`${proxyUrl}/zai/read?url=${encodeURIComponent(url)}`);
  
  if (!response.ok) {
    throw new Error(`Proxy error: ${response.status}`);
  }
  
  const data = await response.json() as { reader_result?: { content?: string; title?: string; description?: string } };
  const result = data.reader_result;
  
  if (!result?.content) {
    throw new Error('No content returned');
  }
  
  let output = '';
  if (result.title) output += `# ${result.title}\n\n`;
  if (result.description) output += `> ${result.description}\n\n`;
  output += result.content;
  
  return output;
}

// Z.AI Web Reader API (direct, for local dev)
async function readPageZai(url: string, apiKey: string): Promise<string> {
  const response = await fetch('https://api.z.ai/api/paas/v4/reader', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      url,
      return_format: 'markdown',
      retain_images: false,
      timeout: Math.floor(CONFIG.timeouts.webFetch / 1000),
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Z.AI Reader error: ${response.status}`);
  }
  
  const data = await response.json() as { reader_result?: { content?: string; title?: string; description?: string } };
  const result = data.reader_result;
  
  if (!result?.content) {
    throw new Error('No content returned');
  }
  
  let output = '';
  if (result.title) output += `# ${result.title}\n\n`;
  if (result.description) output += `> ${result.description}\n\n`;
  output += result.content;
  
  return output;
}

// ============ fetch_page ============
export const fetchPageDefinition = {
  type: "function" as const,
  function: {
    name: "fetch_page",
    description: "Fetch and parse content from a URL. Returns clean markdown text.",
    parameters: {
      type: "object",
      properties: {
        url: { type: "string", description: "URL to fetch" },
      },
      required: ["url"],
    },
  },
};

// Blocked URL patterns for security
const BLOCKED_URL_PATTERNS = [
  // Cloud metadata endpoints
  /^https?:\/\/169\.254\.169\.254/i,
  /^https?:\/\/metadata\.google\.internal/i,
  /^https?:\/\/metadata\.azure\.internal/i,
  /^https?:\/\/100\.100\.100\.200/i,
  
  // Internal/private networks
  /^https?:\/\/localhost/i,
  /^https?:\/\/127\./i,
  /^https?:\/\/10\./i,
  /^https?:\/\/172\.(1[6-9]|2[0-9]|3[0-1])\./i,
  /^https?:\/\/192\.168\./i,
  /^https?:\/\/0\.0\.0\.0/i,
  /^https?:\/\/\[::1\]/i,
  
  // File protocol
  /^file:/i,
  
  // Internal Docker networks
  /^https?:\/\/host\.docker\.internal/i,
  /^https?:\/\/docker\.internal/i,
  /^https?:\/\/proxy:/i,  // Block access to our proxy directly
  
  // Kubernetes internal
  /^https?:\/\/kubernetes\.default/i,
  /^https?:\/\/.*\.cluster\.local/i,
];

function isUrlSafe(url: string): { safe: boolean; reason?: string } {
  if (!url.match(/^https?:\/\//i)) {
    return { safe: false, reason: 'Only http/https URLs allowed' };
  }
  
  for (const pattern of BLOCKED_URL_PATTERNS) {
    if (pattern.test(url)) {
      return { safe: false, reason: 'URL blocked for security (internal/metadata endpoint)' };
    }
  }
  
  return { safe: true };
}

export async function executeFetchPage(
  args: { url: string },
  zaiApiKey?: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  const urlCheck = isUrlSafe(args.url);
  if (!urlCheck.safe) {
    console.log(`[SECURITY] Blocked fetch: ${args.url} - ${urlCheck.reason}`);
    return { success: false, error: `🚫 BLOCKED: ${urlCheck.reason}` };
  }
  
  // Try Proxy first
  if (proxyUrl) {
    try {
      console.log('[fetch] Using Proxy reader...');
      const content = await readPageViaProxy(args.url);
      return { success: true, output: content.slice(0, 50000) };
    } catch (e: any) {
      console.log(`[fetch] Proxy reader failed: ${e.message}, falling back`);
    }
  }
  
  // Try Z.AI Reader (local dev)
  if (zaiApiKey) {
    try {
      console.log('[fetch] Using Z.AI Reader...');
      const content = await readPageZai(args.url, zaiApiKey);
      return { success: true, output: content.slice(0, 50000) };
    } catch (e: any) {
      console.log(`[fetch] Z.AI Reader failed: ${e.message}, falling back to direct fetch`);
    }
  }
  
  // Fallback to direct fetch
  try {
    const response = await fetch(args.url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; Agent/1.0)' },
      redirect: 'follow',
    });
    
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get('location');
      if (location) {
        const redirectCheck = isUrlSafe(location);
        if (!redirectCheck.safe) {
          return { success: false, error: `🚫 BLOCKED: Redirect to internal URL blocked` };
        }
      }
    }
    
    if (!response.ok) {
      return { success: false, error: `HTTP ${response.status}` };
    }
    
    const text = await response.text();
    return { success: true, output: text.slice(0, 50000) };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}
