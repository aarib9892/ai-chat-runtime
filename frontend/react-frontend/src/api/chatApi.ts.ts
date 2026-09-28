const API_BASE_URL = "http://127.0.0.1:8000/api";
export async function loadConversationByIdApi(id: string) {
  const response = await fetch(`${API_BASE_URL}/conversations/${id}`);
  return response;
}

export async function createConversationApi() {
  const response = await fetch(`${API_BASE_URL}/conversations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: null,
    }),
  });
  return response;
}

export async function askMessageApi(
  conversation_id: string,
  message: string,
  signal: AbortSignal,
) {
  const response = await fetch(
    `${API_BASE_URL}/conversations/${conversation_id}/ask`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        message: message,
      }),

      signal: signal,
    },
  );
  return response;
}

export async function loadConversationsApi() {
  return fetch(`${API_BASE_URL}/conversations`);
}
