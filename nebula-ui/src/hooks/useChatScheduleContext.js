import { useScheduleChat } from '../chat/ScheduleChatContext';

/**
 * Hook to access and update the schedule context bound to the floating chatbot.
 */
export function useChatScheduleContext() {
  const { scheduleContext, setScheduleChatContext, openScheduleChat } = useScheduleChat();
  return {
    scheduleContext,
    setScheduleChatContext,
    openScheduleChat,
  };
}

export default useChatScheduleContext;
