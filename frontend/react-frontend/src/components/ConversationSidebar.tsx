import type { Conversation } from "../types/chat";

type Props = {
  conversations: Conversation[];
  activeConversationId: string | null;

  onSelect: (conversationId: string) => void;

  onNewChat: () => void;
};

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onNewChat,
}: Props) {
  return (
    <aside className="w-64 border-r min-h-screen p-4">
      <button
        type="button"
        onClick={onNewChat}
        className="w-full p-2 mb-4 border rounded-lg cursor-pointer"
      >
        + New Chat
      </button>

      <div className="flex flex-col gap-2">
        {conversations.map((conversation) => {
          const isActive = conversation.id === activeConversationId;

          return (
            <button
              key={conversation.id}
              type="button"
              onClick={() => onSelect(conversation.id)}
              className={`text-left p-2 rounded-lg cursor-pointer ${
                isActive ? "bg-gray-300" : "hover:bg-gray-100"
              }`}
            >
              {conversation.title ?? "Untitled Chat"}
            </button>
          );
        })}
      </div>
    </aside>
  );
}
