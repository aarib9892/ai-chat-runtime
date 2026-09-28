import "./App.css";
import { useChat } from "./hooks/useChat.ts";
import { MessageList } from "./components/MessageList.tsx";
import { ChatComposer } from "./components/ChatComposer.tsx";
import { ConversationSidebar } from "./components/ConversationSidebar.tsx";

function App() {
  const { state, sendMessage, stopStreaming, newChat, selectConversation } =
    useChat();

  return (
    <div className="flex min-h-screen w-full">
      <ConversationSidebar
        conversations={state.conversations}
        activeConversationId={state.activeConversationId}
        onSelect={selectConversation}
        onNewChat={newChat}
      />

      <main className="flex-1">
        {state.error && <p className="text-red-600">{state.error}</p>}

        <MessageList messages={state.messages} />

        <ChatComposer
          isStreaming={state.streamStatus === "streaming"}
          onSend={sendMessage}
          onStop={stopStreaming}
        />
      </main>
    </div>
  );
}

export default App;
