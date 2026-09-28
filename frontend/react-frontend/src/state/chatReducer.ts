import type {
  Conversation,
  ConversationWithMessages,
  Message,
} from "../types/chat";

export type ChatState = {
  activeConversationId: string | null;

  conversations: Conversation[];

  messages: Message[];

  streamStatus: "idle" | "streaming";

  error: string | null;
};

export const initialChatState: ChatState = {
  activeConversationId: null,

  conversations: [],

  messages: [],

  streamStatus: "idle",

  error: null,
};

export type ChatAction =
  | {
      type: "conversations/loaded";
      conversations: Conversation[];
    }
  | {
      type: "conversation/created";
      conversation: Conversation;
    }
  | {
      type: "conversation/loaded";
      conversation: ConversationWithMessages;
    }
  | {
      type: "message/userAdded";
      message: Message;
    }
  | {
      type: "stream/started";
    }
  | {
      type: "stream/delta";
      delta: string;
    }
  | {
      type: "stream/completed";
    }
  | {
      type: "stream/stopped";
    }
  | {
      type: "stream/error";
      message: string;
    }
  | {
      type: "error/cleared";
    }
  | {
      type: "chat/reset";
    };

function updateLastAssistant(
  messages: Message[],
  updater: (message: Message) => Message,
): Message[] {
  if (messages.length === 0) {
    return messages;
  }

  const updated = [...messages];

  const lastIndex = updated.length - 1;

  const lastMessage = updated[lastIndex];

  if (lastMessage.role !== "assistant") {
    return messages;
  }

  updated[lastIndex] = updater(lastMessage);

  return updated;
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "conversations/loaded":
      return {
        ...state,
        conversations: action.conversations,
      };

    case "conversation/created":
      return {
        ...state,
        activeConversationId: action.conversation.id,
        messages: [],
        error: null,
      };

    case "conversation/loaded":
      return {
        ...state,

        activeConversationId: action.conversation.id,

        messages: action.conversation.messages,

        error: null,
      };

    case "message/userAdded":
      return {
        ...state,

        messages: [...state.messages, action.message],
      };

    case "stream/started":
      return {
        ...state,

        streamStatus: "streaming",

        error: null,

        messages: [
          ...state.messages,
          {
            role: "assistant",
            content: "",
            status: "streaming",
          },
        ],
      };

    case "stream/delta":
      return {
        ...state,

        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,

          content: message.content + action.delta,
        })),
      };

    case "stream/completed":
      return {
        ...state,

        streamStatus: "idle",

        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,
          status: "completed",
        })),
      };

    case "stream/stopped":
      return {
        ...state,

        streamStatus: "idle",

        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,
          status: "stopped",
        })),
      };

    case "stream/error":
      return {
        ...state,

        streamStatus: "idle",

        error: action.message,

        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,
          status: "error",
        })),
      };

    case "error/cleared":
      return {
        ...state,
        error: null,
      };

    case "chat/reset":
      return {
        ...state,

        activeConversationId: null,

        messages: [],

        streamStatus: "idle",

        error: null,
      };

    default:
      return state;
  }
}
