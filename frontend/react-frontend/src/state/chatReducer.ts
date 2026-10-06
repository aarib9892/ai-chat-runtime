import type {
  Conversation,
  ConversationWithMessages,
  Message,
  MessageSource,
  MessageToolCall,
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
      type: "stream/sourcesReceived";
      sources: MessageSource[];
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
    }
  | {
      type: "messages/persisted";
      userMessageId: string;
      assistantMessageId: string;
    }
  | {
      type: "stream/toolCallStarted";
      toolCall: MessageToolCall;
    }
  | {
      type: "stream/toolCallCompleted";
      callId: string;
      result?: unknown;
      status: Exclude<MessageToolCall["status"], "running">;
      error?: string;
    }
  | {
      type: "stream/incomplete";
      reason: string;
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

function attachPersistedMessageIds(
  messages: Message[],
  userMessageId: string,
  assistantMessageId: string,
): Message[] {
  const updated = [...messages];

  const assistantIndex = updated.findLastIndex(
    (message) => message.role === "assistant" && message.status === "streaming",
  );

  if (assistantIndex === -1) {
    return messages;
  }

  let userIndex = -1;

  for (let index = assistantIndex - 1; index >= 0; index--) {
    if (updated[index].role === "user") {
      userIndex = index;
      break;
    }
  }

  if (userIndex !== -1) {
    updated[userIndex] = {
      ...updated[userIndex],
      id: userMessageId,
    };
  }

  updated[assistantIndex] = {
    ...updated[assistantIndex],
    id: assistantMessageId,
  };

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

    case "messages/persisted":
      return {
        ...state,

        messages: attachPersistedMessageIds(
          state.messages,
          action.userMessageId,
          action.assistantMessageId,
        ),
      };
    case "stream/incomplete":
      return {
        ...state,

        streamStatus: "idle",

        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,
          status: "incomplete",
        })),

        error:
          action.reason === "max_tokens"
            ? "The response reached the maximum output length."
            : "The response ended before completion.",
      };
    case "stream/sourcesReceived":
      return {
        ...state,
        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,
          sources: action.sources,
        })),
      };
    case "stream/toolCallStarted":
      return {
        ...state,

        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,
          toolCalls: [...(message.toolCalls ?? []), action.toolCall],
        })),
      };
    case "stream/toolCallCompleted":
      return {
        ...state,

        messages: updateLastAssistant(state.messages, (message) => ({
          ...message,
          toolCalls: message.toolCalls?.map((toolCall) => {
            if (toolCall.callId !== action.callId) {
              return toolCall;
            }

            return {
              ...toolCall,
              status: action.status,
              result: action.result,
              error: action.error,
            };
          }),
        })),
      };

    default:
      return state;
  }
}
