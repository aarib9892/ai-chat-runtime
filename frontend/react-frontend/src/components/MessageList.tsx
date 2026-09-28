import type { Message } from "../types/chat";
import { MessageItem } from "./MessageItem";

type Props = {
  messages: Message[];
};

export function MessageList({ messages }: Props) {
  return (
    <div className="w-full">
      {messages.map((message, index) => (
        <MessageItem key={message.id ?? index} message={message} />
      ))}
    </div>
  );
}
