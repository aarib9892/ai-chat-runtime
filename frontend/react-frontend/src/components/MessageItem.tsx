import type { Message } from "../types/chat";

type Props = {
  message: Message;
};

export function MessageItem({ message }: Props) {
  return (
    <div>
      <strong>{message.role === "user" ? "You" : "Assistant"}</strong>

      <p>{message.content}</p>

      {message.status === "streaming" && <small>Generating...</small>}

      {message.status === "stopped" && <small>Stopped</small>}

      {message.status === "error" && <small>Generation failed</small>}
    </div>
  );
}
