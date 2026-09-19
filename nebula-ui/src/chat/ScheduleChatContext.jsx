import React, { createContext, useContext, useState, useCallback } from 'react';
import { sendChatMessage } from '../services/chatApi';

const ScheduleChatContext = createContext(null);

const DEFAULT_SCHEDULE_CONTEXT = {
  instanceId: null,
  instanceRevisionId: null,
  runId: null,
  baselineRunId: null,
  scenario: 'A',
  mode: 'requirements',
  selectedActivityId: null,
  selectedLocationId: null,
  selectedWeek: null,
  source: 'schedule',
};

export function ScheduleChatProvider({ children, initialContext = {} }) {
  const [scheduleContext, setScheduleContextState] = useState({
    ...DEFAULT_SCHEDULE_CONTEXT,
    ...initialContext,
  });

  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);

  const setScheduleChatContext = useCallback((newContext) => {
    setScheduleContextState((prev) => ({
      ...prev,
      ...newContext,
    }));
  }, []);

  const closeScheduleChat = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggleScheduleChat = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setError(null);
  }, []);

  const handleSendMessage = useCallback(async (questionText, overrideContext = {}) => {
    if (!questionText || !questionText.trim() || isLoading) return;

    const trimmedQuestion = questionText.trim();
    const userMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: trimmedQuestion,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    const activeCtx = {
      ...scheduleContext,
      ...overrideContext,
    };

    try {
      const data = await sendChatMessage({
        sessionId,
        instanceId: activeCtx.instanceId,
        instanceRevisionId: activeCtx.instanceRevisionId,
        runId: activeCtx.runId,
        scenario: activeCtx.scenario,
        mode: activeCtx.mode,
        baselineRunId: activeCtx.baselineRunId,
        question: trimmedQuestion,
        selectedActivityId: activeCtx.selectedActivityId,
        selectedLocationId: activeCtx.selectedLocationId,
        selectedWeek: activeCtx.selectedWeek,
      });

      if (data.session_id) {
        setSessionId(data.session_id);
      }

      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: data.answer,
        responseMode: data.response_mode,
        citations: data.citations || [],
        uncertainty: data.uncertainty || [],
        provenance: data.provenance,
        toolsUsed: data.tools_used || [],
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err.message || 'Failed to receive explanation');
      const errorMessage = {
        id: `error-${Date.now()}`,
        sender: 'assistant',
        text: `Error: ${err.message || 'Unable to connect to the scheduling explanation service.'}`,
        responseMode: 'deterministic_fallback',
        citations: [],
        uncertainty: ['request_error'],
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, scheduleContext, sessionId]);

  const openScheduleChat = useCallback(({ runId, baselineRunId, activityId, autoPrompt } = {}) => {
    if (runId || activityId || baselineRunId) {
      setScheduleContextState((prev) => ({
        ...prev,
        ...(runId ? { runId } : {}),
        ...(baselineRunId !== undefined ? { baselineRunId } : {}),
        ...(activityId ? { selectedActivityId: activityId } : {}),
      }));
    }

    setIsOpen(true);

    if (autoPrompt) {
      setTimeout(() => {
        handleSendMessage(autoPrompt, {
          runId: runId || scheduleContext.runId,
          baselineRunId: baselineRunId !== undefined ? baselineRunId : scheduleContext.baselineRunId,
          selectedActivityId: activityId || scheduleContext.selectedActivityId,
        });
      }, 50);
    }
  }, [handleSendMessage, scheduleContext]);

  const value = {
    scheduleContext,
    setScheduleChatContext,
    isOpen,
    openScheduleChat,
    closeScheduleChat,
    toggleScheduleChat,
    messages,
    sendMessage: handleSendMessage,
    clearMessages,
    isLoading,
    error,
    sessionId,
  };

  return (
    <ScheduleChatContext.Provider value={value}>
      {children}
    </ScheduleChatContext.Provider>
  );
}

export function useScheduleChat() {
  const context = useContext(ScheduleChatContext);
  if (!context) {
    return {
      scheduleContext: {},
      setScheduleChatContext: () => {},
      isOpen: false,
      openScheduleChat: () => {},
      closeScheduleChat: () => {},
      toggleScheduleChat: () => {},
      messages: [],
      sendMessage: () => {},
      clearMessages: () => {},
      isLoading: false,
      error: null,
      sessionId: null,
    };
  }
  return context;
}
