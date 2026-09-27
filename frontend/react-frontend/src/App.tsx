import { useEffect, useRef, useState } from "react";

import "./App.css";

type MessageStatus = "streaming" | "completed" | "stopped" | "error";

type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: MessageStatus;
};
type StreamEvent =
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
type Conversation = {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
};
function App() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const queryRef = useRef<HTMLTextAreaElement>(null);
  async function loadConversation(id: string) {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/conversations/${id}`,
      );

      if (response.status === 404) {
        localStorage.removeItem("active_conversation_id");

        setConversationId(null);
        setMessages([]);

        return;
      }

      if (!response.ok) {
        throw new Error(`Failed to load conversation: ${response.status}`);
      }

      const data = await response.json();

      setConversationId(data.id);

      setMessages(
        data.messages.map(
          (message: any): Message => ({
            id: message.id,
            role: message.role,
            content: message.content,
            status: message.status,
          }),
        ),
      );
    } catch (error) {
      console.error("Failed loading conversation:", error);

      setError("Failed to restore conversation.");
    }
  }

  useEffect(() => {
    const storedConversationId = localStorage?.getItem(
      "active_conversation_id",
    );
    if (!storedConversationId) {
      return;
    }
    loadConversation(storedConversationId);
  }, []);

  async function createConversation(): Promise<string> {
    const response = await fetch("http://127.0.0.1:8000/api/conversations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: null,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create conversation: ${response.status}`);
    }

    const conversation: Conversation = await response.json();

    setConversationId(conversation.id);

    localStorage.setItem("active_conversation_id", conversation.id);

    return conversation.id;
  }

  async function askLLM(conversation_id: string, message: Message) {
    controllerRef.current?.abort();

    const controller = new AbortController();
    controllerRef.current = controller;

    setIsStreaming(true);
    const assistantPlaceHolder: Message = {
      role: "assistant",
      content: "",
      status: "streaming",
    };
    setMessages((prev) => [...prev, assistantPlaceHolder]);

    try {
      const rawResp = await fetch(
        `http://127.0.0.1:8000/api/conversations/${conversation_id}/ask`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            message: message,
            // previous_response_id: previousResponseIdRef.current,
          }),

          signal: controller.signal,
        },
      );

      if (!rawResp.ok) {
        throw new Error(`Request failed: ${rawResp.status}`);
      }

      if (!rawResp.body) {
        throw new Error("Response body is missing");
      }

      const reader = rawResp.body.getReader();
      const decoder = new TextDecoder();
      let buffer: string = "";
      let streamFailed = false;
      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, {
          stream: true,
        });
        console.log(messages, "pppp");
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) {
            continue;
          }
          const event = JSON.parse(line) as StreamEvent;

          switch (event.type) {
            case "delta":
              setMessages((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  content: updated[lastIndex].content + event.delta,
                };

                return updated;
              });

              break;

            case "done":
              setMessages((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  status: "completed",
                };

                return updated;
              });

              break;
            case "error":
              setMessages((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  status: "error",
                };

                return updated;
              });
              setError(event.message);
              streamFailed = true;
              break;
          }
        }
        if (streamFailed) {
          break;
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        console.log("Streaming cancelled by user");
        return;
      }

      throw error;
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setIsStreaming(false);
      }
    }
  }

  const submitHandler = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const inputVal = queryRef.current?.value.trim();

    if (!inputVal) {
      return;
    }

    setError("");

    try {
      let activeConversationId = conversationId;

      // Only create a conversation if we don't already have one
      if (!activeConversationId) {
        activeConversationId = await createConversation();
      }

      const userMessage: Message = {
        role: "user",
        content: inputVal,
        status: "completed",
      };

      // Optimistically show user message in UI
      setMessages((prev) => [...prev, userMessage]);

      // Use the SAME conversation
      await askLLM(activeConversationId, inputVal);

      // Optional: clear textarea after submit
      if (queryRef.current) {
        queryRef.current.value = "";
      }
    } catch (error) {
      console.error(error);

      setError("Something went wrong while generating the response.");
    }
  };
  const stopStreaming = (e: Event) => {
    e.preventDefault();
    e.stopPropagation();

    controllerRef.current?.abort();
  };

  return (
    <form onSubmit={submitHandler}>
      <div className="flex w-1/2 m-auto justify-center items-center gap-4 mt-8 flex-col">
        <label className="text-3xl" htmlFor="query">
          Ask anything...
        </label>

        <textarea
          className="border-2 text-2xl p-2 w-full border-[cadetblue] rounded-lg shadow-xl"
          name="query"
          id="query"
          ref={queryRef}
        />

        {isStreaming ? (
          <button
            type="button"
            className="bg-[crimson] p-4 rounded-xl shadow-xl text-white cursor-pointer"
            onClick={stopStreaming}
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            className="bg-[darkgreen] p-4 rounded-xl shadow-xl text-white cursor-pointer"
          >
            Rocket
          </button>
        )}

        {error && <p className="text-red-600">{error}</p>}

        <div className="w-full">
          {messages?.length > 0 &&
            messages.map((message, index) => (
              <div key={index}>
                <strong>{message.role === "user" ? "You" : "Assistant"}</strong>

                <p>{message.content}</p>
              </div>
            ))}
        </div>
      </div>
    </form>
  );
}

export default App;
