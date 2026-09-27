import { useRef, useState } from "react";

import "./App.css";
type Message = {
  role: "user" | "assistant";
  content: string;
};
type StreamEvent =
  | {
      type: "response_id";
      response_id: string;
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

function App() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);

  const controllerRef = useRef<AbortController | null>(null);
  const queryRef = useRef<HTMLTextAreaElement>(null);
  const previousResponseIdRef = useRef<string | null>(null);

  async function askLLM(inputVal: string) {
    controllerRef.current?.abort();

    const controller = new AbortController();
    controllerRef.current = controller;

    setIsStreaming(true);
    const assistantPlaceHolder: Message = {
      role: "assistant",
      content: "",
    };
    setMessages((prev) => [...prev, assistantPlaceHolder]);

    try {
      const rawResp = await fetch("http://127.0.0.1:8000/api/ask", {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          message: inputVal,
          previous_response_id: previousResponseIdRef.current,
        }),

        signal: controller.signal,
      });

      if (!rawResp.ok) {
        throw new Error(`Request failed: ${rawResp.status}`);
      }

      if (!rawResp.body) {
        throw new Error("Response body is missing");
      }

      const reader = rawResp.body.getReader();
      const decoder = new TextDecoder();
      let buffer: string = "";
      let pendingResponseId: string | null = null;
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
            case "response_id":
              pendingResponseId = event.response_id;
              break;

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
              if (pendingResponseId) {
                console.log("ikk", pendingResponseId);
                previousResponseIdRef.current = pendingResponseId;
              }

              break;
            case "error":
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

    const usrMssg: Message = {
      role: "user",
      content: inputVal,
    };
    const conversation = [...messages, usrMssg];
    setMessages(conversation);

    try {
      await askLLM(inputVal);
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
