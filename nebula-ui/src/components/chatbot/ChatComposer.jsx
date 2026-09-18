import React, { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';

export default function ChatComposer({ onSend, isLoading = false }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (!isLoading) {
      textareaRef.current?.focus();
    }
  }, [isLoading]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!text.trim() || isLoading) return;
    onSend(text);
    setText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-3 bg-slate-950 border-t border-slate-800">
      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about the schedule..."
          rows={2}
          maxLength={2000}
          disabled={isLoading}
          className="flex-1 bg-slate-900 border border-slate-700/80 focus:border-cyan-400 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none resize-none transition disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          className="bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-800 disabled:text-slate-600 text-slate-950 p-2.5 rounded-xl font-bold transition flex items-center justify-center shrink-0 cursor-pointer disabled:cursor-not-allowed"
          title="Send Question"
          aria-label="Send Question"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
