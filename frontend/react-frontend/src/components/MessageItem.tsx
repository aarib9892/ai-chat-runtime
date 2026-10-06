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

      {message.status === "incomplete" && (
        <small>Response ended before completion.</small>
      )}

      {message.role === "assistant" &&
        message.sources &&
        message.sources.length > 0 && (
          <div>
            <strong>Sources</strong>

            <ul>
              {message.sources.map((source) => (
                <li key={`${source.documentId}-${source.chunkIndex}`}>
                  {source.filename}
                  {" — "}
                  chunk {source.chunkIndex}
                  {" — "}
                  similarity {source.similarity.toFixed(3)}
                </li>
              ))}
            </ul>
          </div>
        )}

      {message.role === "assistant" &&
        message.toolCalls &&
        message.toolCalls.length > 0 && (
          <div>
            <strong>Tools</strong>

            {message.toolCalls.map((toolCall) => (
              <div key={toolCall.callId}>
                <div>
                  <strong>{toolCall.name}</strong>
                </div>

                <div>
                  <small>
                    {toolCall.status === "running" && "Running..."}
                    {toolCall.status === "completed" && "Completed"}
                    {toolCall.status === "error" && "Failed"}
                  </small>
                </div>

                <pre>{JSON.stringify(toolCall.arguments, null, 2)}</pre>

                {toolCall.status === "completed" && (
                  <pre>{JSON.stringify(toolCall.result, null, 2)}</pre>
                )}

                {toolCall.status === "error" && <small>{toolCall.error}</small>}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
