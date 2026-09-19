import React, { useEffect, useRef } from 'react';
import ChatMessage from './ChatMessage';
import ChatEmptyState from './ChatEmptyState';
import { Loader2 } from 'lucide-react';

export default function ChatMessageList({ messages = [], isLoading = false, context = {}, onSelectPrompt }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    if (typeof bottomRef.current?.scrollIntoView === 'function') {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto chat-scroll-container">
        <ChatEmptyState context={context} onSelectPrompt={onSelectPrompt} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 chat-scroll-container">
      {messages.map((msg) => (
        <ChatMessage key={msg.id} message={msg} />
      ))}

      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-cyan-400 p-3 bg-slate-900/60 rounded-xl border border-slate-800 w-fit">
          <Loader2 size={14} className="animate-spin" />
          <span>Generating grounded schedule explanation...</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
