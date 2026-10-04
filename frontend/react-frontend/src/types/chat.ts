type MessageStatus =
  | "streaming"
  | "completed"
  | "stopped"
  | "error"
  | "incomplete";
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
