/**
 * send_dm - Send a direct message to the user's private chat
 * Works only if user has previously started a conversation with the bot
 */

// Callback for sending DM (set from bot)
let sendDmCallback: ((
  userId: number,
  message: string
) => Promise<boolean>) | null = null;

/**
 * Set the send DM callback (called from bot)
 */
export function setSendDmCallback(
  callback: (userId: number, message: string) => Promise<boolean>
) {
  sendDmCallback = callback;
}

export const definition = {
  type: "function" as const,
  function: {
    name: "send_dm",
    description: "Send a direct/private message. By default sends to the user who asked. Can specify user_id to send to someone else (if they have started DM with bot).",
    parameters: {
      type: "object",
      properties: {
        message: {
          type: "string",
          description: "Message text to send (supports markdown)"
        },
        user_id: {
          type: "number",
          description: "Optional: specific user ID to send to. Default: the user who wrote the request."
        },
      },
      required: ["message"],
    },
  },
};

// Max message length
const MAX_MESSAGE_LENGTH = 4000;

export async function execute(
  args: { message: string; user_id?: number },
  defaultUserId: number
): Promise<{ success: boolean; output?: string; error?: string }> {
  if (!sendDmCallback) {
    return {
      success: false,
      error: 'Send DM callback not configured',
    };
  }
  
  // Use provided user_id or fall back to the requesting user
  const targetUserId = args.user_id || defaultUserId;
  
  if (!targetUserId || targetUserId === 0) {
    return {
      success: false,
      error: 'No user ID available. Make sure you are replying to a user message.',
    };
  }
  
  if (!args.message || args.message.trim().length === 0) {
    return {
      success: false,
      error: 'Message cannot be empty',
    };
  }
  
  if (args.message.length > MAX_MESSAGE_LENGTH) {
    return {
      success: false,
      error: `Message too long (${args.message.length} chars). Max: ${MAX_MESSAGE_LENGTH}`,
    };
  }
  
  try {
    const sent = await sendDmCallback(targetUserId, args.message);
    if (sent) {
      return {
        success: true,
        output: `Sent DM to user ${targetUserId}`,
      };
    } else {
      return {
        success: false,
        error: 'User has not started a conversation with me yet. Ask them to write /start in my DM first.',
      };
    }
  } catch (e: any) {
    // Check common errors
    if (e.message?.includes('bot was blocked') || e.message?.includes('user is deactivated')) {
      return {
        success: false,
        error: 'User has blocked the bot or account is deactivated',
      };
    }
    if (e.message?.includes('chat not found') || e.message?.includes("can't initiate")) {
      return {
        success: false,
        error: 'User has not started a conversation with me yet. Ask them to write /start in my DM first.',
      };
    }
    return {
      success: false,
      error: `Failed to send DM: ${e.message}`,
    };
  }
}
