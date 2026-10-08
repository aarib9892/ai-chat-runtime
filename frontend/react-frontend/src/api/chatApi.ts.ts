import type { BackendMessage, Message } from "../types/chat";

const API_BASE_URL = "http://127.0.0.1:8000/api";

export function mapBackendMessage(message: BackendMessage): Message {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    status: message.status,

    sources:
      message.sources?.map((source) => ({
        documentId: source.document_id,
        filename: source.filename,
        chunkIndex: source.chunk_index,
        similarity: source.similarity,
      })) ?? [],

    toolCalls:
      message.tool_calls?.map((toolCall) => ({
        callId: toolCall.call_id,
        name: toolCall.name,
        arguments: toolCall.arguments,
        step: toolCall.step ?? undefined,
        status: toolCall.status,
        result: toolCall.result ?? undefined,
        error: toolCall.error ?? undefined,
      })) ?? [],

    agentSteps:
      message.agent_steps?.map((step) => ({
        step: step.step,
        responseId: step.response_id,
        status: step.status,
        outcome: step.outcome,
        startedAt: step.started_at,
        completedAt: step.completed_at,
      })) ?? [],
  };
}
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
  documentId?: string | null,
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
        document_id: documentId,
      }),

      signal: signal,
    },
  );
  return response;
}

export async function loadConversationsApi() {
  return fetch(`${API_BASE_URL}/conversations`);
}
