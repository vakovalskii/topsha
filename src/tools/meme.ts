/**
 * get_meme - Fetch random memes and funny images
 * Sources: Imgflip memes, random dogs, random cats
 */

import { CONFIG } from '../config.js';

export const definition = {
  type: "function" as const,
  function: {
    name: "get_meme",
    description: "Get random meme or funny image. Sources: 'meme' (classic meme templates), 'dog' (random dog pics), 'cat' (random cat pics), 'catmeme' (cat with funny caption). Use when user wants memes, fun content, animals, or is bored.",
    parameters: {
      type: "object",
      properties: {
        source: {
          type: "string",
          description: "Image source: 'meme' (default), 'dog', 'cat', 'catmeme'",
          enum: ["meme", "dog", "cat", "catmeme"],
        },
        count: {
          type: "number",
          description: "Number of images (1-5, default 1)",
        },
      },
      required: [],
    },
  },
};

interface ImageResult {
  title: string;
  url: string;
  source: string;
}

// Imgflip memes cache
let memesCache: any[] = [];
let cacheTime = 0;
const CACHE_TTL = 60 * 60 * 1000;

async function getImgflipMeme(): Promise<ImageResult | null> {
  try {
    // Use cache
    const now = Date.now();
    if (memesCache.length === 0 || now - cacheTime > CACHE_TTL) {
      const res = await fetch('https://api.imgflip.com/get_memes', { 
        signal: AbortSignal.timeout(CONFIG.timeouts.memeApi) 
      });
      if (res.ok) {
        const data = await res.json() as { success: boolean; data?: { memes: any[] } };
        if (data.success && data.data?.memes) {
          memesCache = data.data.memes;
          cacheTime = now;
        }
      }
    }
    
    if (memesCache.length === 0) return null;
    
    const meme = memesCache[Math.floor(Math.random() * memesCache.length)];
    return {
      title: meme.name,
      url: meme.url,
      source: 'Imgflip',
    };
  } catch {
    return null;
  }
}

async function getRandomDog(): Promise<ImageResult | null> {
  try {
    const res = await fetch('https://dog.ceo/api/breeds/image/random', {
      signal: AbortSignal.timeout(CONFIG.timeouts.memeApi),
    });
    if (!res.ok) return null;
    
    const data = await res.json() as { status: string; message: string };
    if (data.status === 'success' && data.message) {
      // Extract breed from URL
      const match = data.message.match(/breeds\/([^/]+)/);
      const breed = match ? match[1].replace('-', ' ') : 'dog';
      return {
        title: `🐕 ${breed}`,
        url: data.message,
        source: 'Dog CEO',
      };
    }
    return null;
  } catch {
    return null;
  }
}

async function getRandomCat(): Promise<ImageResult | null> {
  try {
    const res = await fetch('https://api.thecatapi.com/v1/images/search', {
      signal: AbortSignal.timeout(CONFIG.timeouts.memeApi),
    });
    if (!res.ok) return null;
    
    const data = await res.json() as { url: string }[];
    if (data[0]?.url) {
      return {
        title: '🐱 Random cat',
        url: data[0].url,
        source: 'The Cat API',
      };
    }
    return null;
  } catch {
    return null;
  }
}

async function getCatMeme(): Promise<ImageResult | null> {
  try {
    const res = await fetch('https://cataas.com/cat?json=true', {
      signal: AbortSignal.timeout(CONFIG.timeouts.memeApi),
    });
    if (!res.ok) return null;
    
    const data = await res.json() as { url: string; tags?: string[] };
    if (data.url) {
      const tags = data.tags?.slice(0, 3).join(', ') || 'funny cat';
      return {
        title: `🐱 ${tags}`,
        url: data.url.startsWith('http') ? data.url : `https://cataas.com${data.url}`,
        source: 'Cataas',
      };
    }
    return null;
  } catch {
    return null;
  }
}

export async function execute(
  args: { source?: string; count?: number }
): Promise<{ success: boolean; output?: string; error?: string }> {
  const source = args.source || 'meme';
  const count = Math.min(Math.max(args.count || 1, 1), 5);
  
  const results: ImageResult[] = [];
  
  for (let i = 0; i < count; i++) {
    let result: ImageResult | null = null;
    
    switch (source) {
      case 'dog':
        result = await getRandomDog();
        break;
      case 'cat':
        result = await getRandomCat();
        break;
      case 'catmeme':
        result = await getCatMeme();
        break;
      case 'meme':
      default:
        result = await getImgflipMeme();
        break;
    }
    
    if (result) {
      results.push(result);
    }
  }
  
  if (results.length === 0) {
    return {
      success: false,
      error: 'Could not fetch images. Try again or different source.',
    };
  }
  
  const output = results.map((r, i) => {
    const prefix = results.length > 1 ? `#${i + 1}: ` : '';
    return `${prefix}${r.title}\n🔗 ${r.url}`;
  }).join('\n\n');
  
  return {
    success: true,
    output: `#meme\n\n${output}`,
  };
}
