type MessageStatus =
  | "streaming"
  | "completed"
  | "stopped"
  | "error"
  | "incomplete";
export type ToolCallStatus = "running" | "completed" | "error";
export type MessageToolCall = {
  callId: string;
  name: string;
  arguments: Record<string, unknown>;
  status: ToolCallStatus;
  step?: number;
  result?: unknown;
  error?: string;
};
export type MessageSource = {
  documentId: string;
  filename: string;
  chunkIndex: number;
  similarity: number;
};
export type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: MessageStatus;
  sources?: MessageSource[];
  toolCalls?: MessageToolCall[];
  agentSteps?: AgentStep[];
};

type RetrievalSource = {
  document_id: string;
  filename: string;
  chunk_index: number;
  similarity: number;
};
export type StreamEvent =
  | {
      type: "message_ids";
      user_message_id: string;
      assistant_message_id: string;
    }
  | {
      type: "sources";
      sources: RetrievalSource[];
    }
  | {
      type: "delta";
      delta: string;
    }
  | {
      type: "tool_call";
      call_id: string;
      name: string;
      step?: number;
      arguments: Record<string, unknown>;
    }
  | {
      type: "tool_result";
      call_id: string;
      name: string;
      status: Exclude<ToolCallStatus, "running">;
      result?: unknown;
      error?: string;
    }
  | {
      type: "tool_error";
      call_id: string;
      name: string;
      error: string;
    }
  | {
      type: "agent_step_started";
      step: number;
    }
  | {
      type: "agent_step_completed";
      step: number;
      outcome: "tool" | "final" | "continue";
    }
  | {
      type: "incomplete";
      reason: string;
    }
  | {
      type: "done";
    }
  | {
      type: "error";
      message: string;
    };
export type Conversation = {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
};
export type ConversationWithMessages = Conversation & {
  messages: Message[];
};

//API types

export type BackendToolCall = {
  call_id: string;
  name: string;
  arguments: Record<string, unknown>;
  step: number | null;
  status: ToolCallStatus;
  result: unknown | null;
  error: string | null;
};

export type BackendMessageSource = {
  document_id: string;
  filename: string;
  chunk_index: number;
  similarity: number;
};

export type BackendMessage = {
  id: string;
  conversation_id: string;

  role: "user" | "assistant";
  content: string;
  status: MessageStatus;

  provider_response_id: string | null;
  created_at: string;

  sources?: BackendMessageSource[];
  tool_calls?: BackendToolCall[];
  agent_steps?: BackendAgentStep[];
};

export type BackendConversationWithMessages = Conversation & {
  messages: BackendMessage[];
};
export type AgentStep = {
  step: number;
  responseId: string | null;
  status: "running" | "completed" | "incomplete" | "stopped" | "error";
  outcome: "tool" | "final" | "continue" | null;
  startedAt: string;
  completedAt: string | null;
};

export type BackendAgentStep = {
  step: number;
  response_id: string | null;
  status: AgentStep["status"];
  outcome: AgentStep["outcome"];
  started_at: string;
  completed_at: string | null;
};
