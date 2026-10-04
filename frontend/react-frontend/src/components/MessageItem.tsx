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
    </div>
  );
}
