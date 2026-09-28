import { useRef } from "react";

type Props = {
  isStreaming: boolean;
  onSend: (message: string) => Promise<void>;
  onStop: () => void;
};

export function ChatComposer({ isStreaming, onSend, onStop }: Props) {
  const queryRef = useRef<HTMLTextAreaElement>(null);

  async function submitHandler(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const input = queryRef.current?.value.trim();

    if (!input) {
      return;
    }

    await onSend(input);

    if (queryRef.current) {
      queryRef.current.value = "";
    }
  }

  return (
    <form onSubmit={submitHandler}>
      <textarea ref={queryRef} id="query" name="query" />

      {isStreaming ? (
        <button type="button" onClick={onStop}>
          Stop
        </button>
      ) : (
        <button type="submit">Send</button>
      )}
    </form>
  );
}
