type MessageStatus = "streaming" | "completed" | "stopped" | "error";

export type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: MessageStatus;
};
export type StreamEvent =
  | {
      type: "message_ids";
      user_message_id: string;
      assistant_message_id: string;
    }
  | {
      type: "delta";
      delta: string;
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
