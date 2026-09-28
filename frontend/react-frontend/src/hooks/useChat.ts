import { useEffect, useReducer, useRef } from "react";

import type { Conversation, Message, StreamEvent } from "../types/chat";

import {
  askMessageApi,
  createConversationApi,
  loadConversationByIdApi,
  loadConversationsApi,
} from "../api/chatApi.ts";

import { readNdjsonStream } from "../stream/ndjsonstream.ts";

import { chatReducer, initialChatState } from "../state/chatReducer";

const ACTIVE_CONVERSATION_KEY = "active_conversation_id";

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);

  const controllerRef = useRef<AbortController | null>(null);

  // -------------------------
  // LOAD CONVERSATION
  // -------------------------

  async function loadConversation(id: string) {
    try {
      const response = await loadConversationByIdApi(id);

      if (response.status === 404) {
        localStorage.removeItem(ACTIVE_CONVERSATION_KEY);

        dispatch({
          type: "chat/reset",
        });

        return;
      }

      if (!response.ok) {
        throw new Error(`Failed to load conversation: ${response.status}`);
      }

      const conversation = await response.json();

      dispatch({
        type: "conversation/loaded",
        conversation,
      });
    } catch (error) {
      console.error("Failed loading conversation:", error);

      dispatch({
        type: "stream/error",
        message: "Failed to restore conversation.",
      });
    }
  }

  async function loadConversations() {
    try {
      const response = await loadConversationsApi();

      if (!response.ok) {
        throw new Error(`Failed to load conversations: ${response.status}`);
      }

      const data = await response.json();

      dispatch({
        type: "conversations/loaded",
        conversations: data.conversations,
      });
    } catch (error) {
      console.error("Failed loading conversations:", error);

      dispatch({
        type: "stream/error",
        message: "Failed to load conversation history.",
      });
    }
  }

  // -------------------------
  // RESTORE ACTIVE CHAT
  // -------------------------

  useEffect(() => {
    loadConversations();

    const storedConversationId = localStorage.getItem(ACTIVE_CONVERSATION_KEY);

    if (storedConversationId) {
      loadConversation(storedConversationId);
    }
  }, []);
  // -------------------------
  // CREATE CONVERSATION
  // -------------------------
  async function selectConversation(id: string) {
    if (id === state.activeConversationId) {
      return;
    }

    controllerRef.current?.abort();

    dispatch({
      type: "error/cleared",
    });

    localStorage.setItem(ACTIVE_CONVERSATION_KEY, id);

    await loadConversation(id);
  }
  async function createConversation(): Promise<string> {
    const response = await createConversationApi();

    if (!response.ok) {
      throw new Error(`Failed to create conversation: ${response.status}`);
    }

    const conversation: Conversation = await response.json();

    dispatch({
      type: "conversation/created",
      conversation,
    });

    localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversation.id);

    return conversation.id;
  }

  // -------------------------
  // STREAM RESPONSE
  // -------------------------

  async function askLLM(
    conversationId: string,
    message: string,
    isNewConversation = false,
  ) {
    controllerRef.current?.abort();

    const controller = new AbortController();

    controllerRef.current = controller;

    dispatch({
      type: "stream/started",
    });

    try {
      const response = await askMessageApi(
        conversationId,
        message,
        controller.signal,
      );

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Response body is missing");
      }
      if (isNewConversation) {
        await loadConversations();
      }

      for await (const event of readNdjsonStream<StreamEvent>(response.body)) {
        switch (event.type) {
          case "delta":
            dispatch({
              type: "stream/delta",
              delta: event.delta,
            });

            break;

          case "done":
            dispatch({
              type: "stream/completed",
            });

            break;

          case "error":
            dispatch({
              type: "stream/error",
              message: event.message,
            });

            return;
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        dispatch({
          type: "stream/stopped",
        });

        return;
      }

      console.error(error);

      dispatch({
        type: "stream/error",
        message: "Something went wrong while generating the response.",
      });
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
      }
    }
  }

  // -------------------------
  // SEND USER MESSAGE
  // -------------------------

  async function sendMessage(input: string) {
    const message = input.trim();

    if (!message) {
      return;
    }

    dispatch({
      type: "error/cleared",
    });

    try {
      let conversationId = state.activeConversationId;
      const isNewConversation = !conversationId;

      if (!conversationId) {
        conversationId = await createConversation();
      }

      const userMessage: Message = {
        role: "user",
        content: message,
        status: "completed",
      };

      dispatch({
        type: "message/userAdded",
        message: userMessage,
      });

      await askLLM(conversationId, message, isNewConversation);
    } catch (error) {
      console.error(error);

      dispatch({
        type: "stream/error",
        message: "Something went wrong while sending the message.",
      });
    }
  }

  // -------------------------
  // STOP STREAM
  // -------------------------

  function stopStreaming() {
    controllerRef.current?.abort();
  }

  // -------------------------
  // NEW CHAT
  // -------------------------

  function newChat() {
    controllerRef.current?.abort();

    localStorage.removeItem(ACTIVE_CONVERSATION_KEY);

    dispatch({
      type: "chat/reset",
    });
  }

  return {
    state,
    selectConversation,
    sendMessage,
    stopStreaming,
    loadConversation,
    newChat,
  };
}
