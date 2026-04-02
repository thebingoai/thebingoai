import { useChatStreaming } from './useChatStreaming'
import { useChatConversations } from './useChatConversations'
import { useChatWsHandlers } from './useChatWsHandlers'

export const useChat = () => {
  const { sendMessage, newChat } = useChatStreaming()
  const { loadConversations, loadMessages, generateSummary, loadConversationSummary, renameConversation, archiveConversation, unarchiveConversation, loadArchivedConversations } = useChatConversations()
  const { registerTitleHandler, registerSummaryHandler, registerHeartbeatHandler, resetContext } = useChatWsHandlers()

  return {
    sendMessage,
    newChat,
    loadConversations,
    loadMessages,
    renameConversation,
    registerTitleHandler,
    registerSummaryHandler,
    registerHeartbeatHandler,
    resetContext,
    archiveConversation,
    unarchiveConversation,
    loadArchivedConversations,
    generateSummary,
  }
}
