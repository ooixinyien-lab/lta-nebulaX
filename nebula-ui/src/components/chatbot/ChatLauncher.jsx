import React from 'react';
import { MessageSquareText, Sparkles } from 'lucide-react';
import '../../styles/chatbot.css';

export default function ChatLauncher({ onClick, isOpen }) {
  if (isOpen) return null;

  return (
    <button
      onClick={onClick}
      className="chat-launcher-btn"
      title="Explain this schedule"
      aria-label="Explain this schedule"
    >
      <div className="relative">
        <MessageSquareText size={24} />
        <span className="absolute -top-1 -right-1 text-cyan-200">
          <Sparkles size={11} />
        </span>
      </div>
    </button>
  );
}
