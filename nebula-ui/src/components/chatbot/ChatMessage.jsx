import React from 'react';
import EvidenceList from './EvidenceList';
import GroundingBadge from './GroundingBadge';
import MarkdownContent from './MarkdownContent';
import { AlertCircle } from 'lucide-react';

export default function ChatMessage({ message }) {
  const isUser = message.sender === 'user';

  if (isUser) {
    return (
      <div className="flex flex-col items-end mb-3">
        <div className="chat-bubble-user font-normal">{message.text}</div>
        <span className="text-[10px] text-slate-500 mt-1 mr-1">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    );
  }

  const isFallback = message.responseMode === 'deterministic_fallback';

  return (
    <div className="flex flex-col items-start mb-4">
      <div className="chat-bubble-assistant">
        <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-slate-800/60 text-[11px]">
          <GroundingBadge responseMode={message.responseMode} />
          {message.toolsUsed && message.toolsUsed.length > 0 && (
            <span className="text-[10px] text-slate-400 font-mono">
              tools: {message.toolsUsed.join(', ')}
            </span>
          )}
        </div>

        {isFallback && (
          <div className="mb-2 p-2 rounded bg-slate-900/80 border border-slate-800 text-[11px] text-slate-300 flex items-start gap-1.5">
            <AlertCircle size={13} className="text-amber-400 shrink-0 mt-0.5" />
            <span>AI model unavailable or offline — showing verified deterministic schedule facts.</span>
          </div>
        )}

        <MarkdownContent content={message.text} />

        {/* Uncertainty indicators */}
        {message.uncertainty && message.uncertainty.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1">
            {message.uncertainty
              .filter((u) => u !== 'provider_unavailable')
              .map((flag, idx) => (
                <span
                  key={idx}
                  className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 font-mono"
                >
                  ⓘ {flag.replace(/_/g, ' ')}
                </span>
              ))}
          </div>
        )}

        {/* Structured Evidence list */}
        {message.citations && message.citations.length > 0 && (
          <EvidenceList citations={message.citations} />
        )}
      </div>

      <span className="text-[10px] text-slate-500 mt-1 ml-1">
        {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  );
}
