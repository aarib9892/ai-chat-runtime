export async function* readNdjsonStream<T>(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<T> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();

  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, {
        stream: true,
      });

      const lines = buffer.split("\n");

      // The last item may be an incomplete JSON line.
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmedLine = line.trim();

        if (!trimmedLine) {
          continue;
        }

        yield JSON.parse(trimmedLine) as T;
      }
    }

    // Flush any remaining bytes held by TextDecoder.
    buffer += decoder.decode();

    // Defensive handling in case the final JSON object
    // didn't end with "\n".
    const finalLine = buffer.trim();

    if (finalLine) {
      yield JSON.parse(finalLine) as T;
    }
  } finally {
    reader.releaseLock();
  }
}
