import React from 'react';
import { useScheduleChat } from '../../chat/ScheduleChatContext';
import ChatLauncher from './ChatLauncher';
import ChatPanel from './ChatPanel';

export default function ScheduleChatDock() {
  const {
    isOpen,
    toggleScheduleChat,
    closeScheduleChat,
    clearMessages,
    scheduleContext,
    messages,
    isLoading,
    sendMessage,
  } = useScheduleChat();

  return (
    <>
      <ChatLauncher onClick={toggleScheduleChat} isOpen={isOpen} />
      <ChatPanel
        isOpen={isOpen}
        onClose={closeScheduleChat}
        onClear={clearMessages}
        context={scheduleContext}
        messages={messages}
        isLoading={isLoading}
        onSend={sendMessage}
      />
    </>
  );
}
