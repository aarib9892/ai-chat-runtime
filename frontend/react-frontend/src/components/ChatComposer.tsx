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
    <form
      onSubmit={submitHandler}
      className="flex w-full gap-4 justify-center items-center mt-10 sticky bottom-0 border-t bg-[#16171d]"
    >
      <textarea
        className="bg-[#3b3939] my-4 text-white rounded-xl p-4 w-1/2 shadow-xl"
        ref={queryRef}
        id="query"
        name="query"
      />

      {isStreaming ? (
        <button
          type="button"
          className="bg-[crimson] text-white rounded-md p-2"
          onClick={(event) => {
            event.preventDefault();
            onStop();
          }}
        >
          Stop
        </button>
      ) : (
        <button
          className="bg-[cadetblue] text-white rounded-md p-2"
          type="submit"
        >
          Send
        </button>
      )}
    </form>
  );
}
