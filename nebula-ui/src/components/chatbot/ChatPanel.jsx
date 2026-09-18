import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import ChatHeader from './ChatHeader';
import ChatContextBar from './ChatContextBar';
import ChatMessageList from './ChatMessageList';
import ChatComposer from './ChatComposer';
import '../../styles/chatbot.css';

export default function ChatPanel({
  isOpen,
  onClose,
  onClear,
  context,
  messages,
  isLoading,
  onSend,
}) {
  // Listen for Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isMock = !context.runId || context.runId.startsWith('mock') || context.runId.includes('sample');

  const content = (
    <div
      className="chat-panel-container"
      role="dialog"
      aria-label="Schedule Explainer"
      aria-modal="true"
    >
      <ChatHeader onClose={onClose} onClear={onClear} isMock={isMock} />
      <ChatContextBar context={context} />
      <ChatMessageList
        messages={messages}
        isLoading={isLoading}
        context={context}
        onSelectPrompt={onSend}
      />
      <ChatComposer onSend={onSend} isLoading={isLoading} />
    </div>
  );

  // Render via portal into document.body to prevent stacking context or layout clipping
  if (typeof document !== 'undefined') {
    return createPortal(content, document.body);
  }

  return content;
}
