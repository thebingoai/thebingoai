import { useChatStreaming } from './useChatStreaming'
import { useChatConversations } from './useChatConversations'
import { useChatWsHandlers } from './useChatWsHandlers'

export const useChat = () => {
  const { sendMessage, newChat } = useChatStreaming()
  const { loadConversations, loadMoreConversations, loadMessages, generateSummary, loadConversationSummary, renameConversation, archiveConversation, unarchiveConversation, loadArchivedConversations } = useChatConversations()
  const { registerTitleHandler, registerSummaryHandler, registerHeartbeatHandler, registerSkillSuggestionsHandler, resetContext } = useChatWsHandlers()

  return {
    sendMessage,
    newChat,
    loadConversations,
    loadMoreConversations,
    loadMessages,
    renameConversation,
    registerTitleHandler,
    registerSummaryHandler,
    registerHeartbeatHandler,
    registerSkillSuggestionsHandler,
    resetContext,
    archiveConversation,
    unarchiveConversation,
    loadArchivedConversations,
    generateSummary,
  }
}
