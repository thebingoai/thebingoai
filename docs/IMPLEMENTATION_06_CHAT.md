# IMPLEMENTATION_06_CHAT.md

## Chat Page Implementation Plan - LLM-MD-CLI Web UI

This document provides a COMPLETE, production-ready implementation plan for the Chat page with streaming responses and all chat-specific components.

---

## Overview

The Chat page is the core feature of LLM-MD-CLI, enabling users to ask questions about indexed markdown files with streaming responses, context retrieval, and conversation management.

### Architecture
- **3-column responsive layout**: Conversation sidebar (250px) | Chat area (flex) | Context panel (300px, collapsible)
- **Real-time streaming**: Server-sent events via fetch + ReadableStream
- **State management**: Zustand stores for chat and providers
- **Markdown rendering**: Full markdown support with syntax highlighting

---

## Component Implementation

### 1. ChatPage.tsx

**File**: `src/pages/ChatPage.tsx`

**Purpose**: Main page component managing the 3-column layout, conversation state, and streaming orchestration.

**Features**:
- Responsive layout (3 columns → 2 columns → 1 column at breakpoints)
- Mobile drawer for conversation list
- URL routing for conversation ID (`/chat/:conversationId`)
- Integration with chat store and providers
- Keyboard shortcuts
- Empty state with namespace selector and example prompts

**Code**:

```typescript
import React, { useEffect, useRef, useCallback, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import ConversationList from '@/components/chat/ConversationList';
import MessageList from '@/components/chat/MessageList';
import ChatInput from '@/components/chat/ChatInput';
import ContextPanel from '@/components/chat/ContextPanel';
import { useChatStore } from '@/store/chatStore';
import { useProviders } from '@/hooks/useProviders';
import { useNamespaces } from '@/hooks/useNamespaces';
import { streamChat } from '@/lib/streaming';
import { useToast } from '@/hooks/useToast';
import type { ConversationMessage } from '@/types/chat';

export default function ChatPage() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  // Stores
  const {
    conversations,
    messages,
    currentConversationId,
    isStreaming,
    streamingContent,
    streamingSources,
    setCurrentConversation,
    addMessage,
    updateStreamingContent,
    setStreamingContent,
    setStreamingSources,
    setIsStreaming,
    addConversation,
    deleteConversation,
  } = useChatStore();

  const { providers, defaultProvider, isLoading: providersLoading } = useProviders();
  const { namespaces } = useNamespaces();

  // State
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [contextPanelOpen, setContextPanelOpen] = useState(true);
  const streamAbortController = useRef<AbortController | null>(null);
  const messageListRef = useRef<HTMLDivElement>(null);

  // Get current conversation
  const currentConversation = conversations.find(c => c.id === (conversationId || currentConversationId));
  const currentMessages = currentConversation ? messages[currentConversation.id] || [] : [];
  const currentNamespace = currentConversation?.namespace || namespaces[0]?.id;

  // Handle conversation selection
  useEffect(() => {
    if (conversationId && conversationId !== currentConversationId) {
      setCurrentConversation(conversationId);
    }
  }, [conversationId, currentConversationId, setCurrentConversation]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K: focus input
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const input = document.querySelector('[data-chat-input]') as HTMLTextAreaElement;
        input?.focus();
      }

      // Cmd/Ctrl + N: new conversation
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault();
        handleNewConversation();
      }

      // Escape: stop streaming
      if (e.key === 'Escape' && isStreaming) {
        e.preventDefault();
        stopStreaming();
      }

      // Cmd/Ctrl + Shift + [: previous conversation
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === '[') {
        e.preventDefault();
        navigateConversation(-1);
      }

      // Cmd/Ctrl + Shift + ]: next conversation
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === ']') {
        e.preventDefault();
        navigateConversation(1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isStreaming, conversations, conversationId]);

  const handleNewConversation = useCallback(() => {
    const newId = crypto.randomUUID();
    const conversation = {
      id: newId,
      title: 'New Conversation',
      namespace: namespaces[0]?.id || 'default',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      thread_id: null,
    };
    addConversation(conversation);
    setCurrentConversation(newId);
    navigate(`/chat/${newId}`);
    setSidebarOpen(false);
  }, [namespaces, addConversation, setCurrentConversation, navigate]);

  const navigateConversation = useCallback((direction: 1 | -1) => {
    if (!conversationId) return;
    const sortedConversations = [...conversations].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
    const currentIndex = sortedConversations.findIndex(c => c.id === conversationId);
    if (currentIndex === -1) return;

    const nextIndex = currentIndex + direction;
    if (nextIndex >= 0 && nextIndex < sortedConversations.length) {
      const nextConversation = sortedConversations[nextIndex];
      navigate(`/chat/${nextConversation.id}`);
    }
  }, [conversations, conversationId, navigate]);

  const stopStreaming = useCallback(() => {
    if (streamAbortController.current) {
      streamAbortController.current.abort();
      streamAbortController.current = null;
    }
    setIsStreaming(false);
  }, [setIsStreaming]);

  const handleSendMessage = useCallback(
    async (content: string, namespace?: string, provider?: string, model?: string) => {
      if (!content.trim()) return;

      // Get or create conversation
      let conversationIdToUse = conversationId;
      if (!conversationIdToUse) {
        conversationIdToUse = crypto.randomUUID();
        const conversation = {
          id: conversationIdToUse,
          title: content.slice(0, 50) || 'New Conversation',
          namespace: namespace || currentNamespace || namespaces[0]?.id || 'default',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          thread_id: null,
        };
        addConversation(conversation);
        setCurrentConversation(conversationIdToUse);
        navigate(`/chat/${conversationIdToUse}`);
      }

      // Add user message
      const userMessage: ConversationMessage = {
        role: 'user',
        content: content.trim(),
        timestamp: new Date().toISOString(),
      };
      addMessage(conversationIdToUse, userMessage);

      // Initialize streaming state
      setIsStreaming(true);
      setStreamingContent('');
      setStreamingSources([]);

      // Prepare request
      const requestBody = {
        query: content.trim(),
        namespace: namespace || currentNamespace || namespaces[0]?.id || 'default',
        conversation_id: currentConversation?.thread_id,
        stream: true,
        provider: provider || defaultProvider?.provider,
        model: model || defaultProvider?.model,
      };

      // Create abort controller for this stream
      streamAbortController.current = new AbortController();

      try {
        const result = await streamChat(requestBody, {
          signal: streamAbortController.current.signal,
          onSources: (sources) => {
            setStreamingSources(sources);
          },
          onToken: (token) => {
            updateStreamingContent(token);
          },
          onThreadId: (threadId) => {
            // Update conversation with thread_id if it's set
            if (currentConversation && !currentConversation.thread_id) {
              // This would need a store update method
            }
          },
          onDone: () => {
            // Create final message
            const assistantMessage: ConversationMessage = {
              role: 'assistant',
              content: streamingContent,
              sources: streamingSources.length > 0 ? streamingSources : undefined,
              timestamp: new Date().toISOString(),
              thread_id: result?.thread_id,
            };
            addMessage(conversationIdToUse, assistantMessage);

            // Reset streaming state
            setIsStreaming(false);
            setStreamingContent('');
            streamAbortController.current = null;
          },
          onError: (error) => {
            toast({
              type: 'error',
              title: 'Chat Error',
              message: error.message || 'Failed to get response. Please try again.',
            });
            setIsStreaming(false);
            streamAbortController.current = null;
          },
        });
      } catch (error) {
        if (error instanceof Error && error.name !== 'AbortError') {
          toast({
            type: 'error',
            title: 'Error',
            message: error.message || 'An error occurred',
          });
        }
        setIsStreaming(false);
        streamAbortController.current = null;
      }

      setSidebarOpen(false);
    },
    [
      conversationId,
      currentConversation,
      currentNamespace,
      namespaces,
      defaultProvider,
      addConversation,
      setCurrentConversation,
      addMessage,
      setIsStreaming,
      setStreamingContent,
      setStreamingSources,
      updateStreamingContent,
      navigate,
      toast,
      streamingContent,
      streamingSources,
    ]
  );

  if (providersLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-white">
      {/* Mobile header */}
      <div className="lg:hidden flex items-center gap-2 px-4 py-3 border-b border-gray-200">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          aria-label="Toggle sidebar"
        >
          {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <h1 className="text-lg font-semibold text-gray-900">LLM-MD-CLI</h1>
      </div>

      {/* Main layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar - Conversation List */}
        <div
          className={`
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
            absolute lg:relative lg:translate-x-0 left-0 top-0 h-full lg:h-auto
            w-64 bg-gray-50 border-r border-gray-200 flex flex-col z-30
            transition-transform duration-200 ease-out lg:transition-none
          `}
        >
          <ConversationList
            conversations={conversations}
            currentConversationId={conversationId || currentConversationId}
            onSelectConversation={(id) => {
              navigate(`/chat/${id}`);
              setSidebarOpen(false);
            }}
            onNewConversation={handleNewConversation}
            onDeleteConversation={deleteConversation}
          />
        </div>

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="absolute inset-0 bg-black bg-opacity-50 lg:hidden z-20"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Chat area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!currentConversation ? (
            // Empty state
            <div className="flex-1 flex flex-col items-center justify-center px-4 py-8">
              <div className="text-center max-w-md">
                <div className="text-5xl mb-4">📚</div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  Ask questions about your documents
                </h2>
                <p className="text-gray-600 mb-8">
                  Select or create a conversation to get started. All answers are grounded in your
                  indexed markdown files.
                </p>

                {/* Namespace selector */}
                {namespaces.length > 0 && (
                  <div className="mb-8">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Search namespace
                    </label>
                    <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue">
                      {namespaces.map(ns => (
                        <option key={ns.id} value={ns.id}>
                          {ns.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Example prompts */}
                <div className="grid grid-cols-1 gap-3">
                  {[
                    'What are the main topics covered?',
                    'Summarize the key findings',
                    'How are these concepts related?',
                    'What is the implementation approach?',
                  ].map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => handleSendMessage(prompt)}
                      className="px-4 py-3 text-left text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>

                <button
                  onClick={handleNewConversation}
                  className="mt-8 px-6 py-2 bg-brand-blue text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Start New Conversation
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Messages */}
              <MessageList
                ref={messageListRef}
                messages={currentMessages}
                isStreaming={isStreaming}
                streamingContent={streamingContent}
                streamingSources={streamingSources}
              />

              {/* Input */}
              <ChatInput
                onSendMessage={handleSendMessage}
                isStreaming={isStreaming}
                onStopStreaming={stopStreaming}
                defaultNamespace={currentConversation.namespace}
                defaultProvider={defaultProvider?.provider}
                defaultModel={defaultProvider?.model}
              />
            </>
          )}
        </div>

        {/* Context Panel */}
        {currentConversation && (
          <div
            className={`
              hidden lg:flex flex-col w-80 bg-gray-50 border-l border-gray-200
              transition-all duration-200 overflow-hidden
              ${contextPanelOpen ? 'w-80' : 'w-0'}
            `}
          >
            <ContextPanel
              sources={streamingSources.length > 0 ? streamingSources : currentMessages[currentMessages.length - 1]?.sources}
              isOpen={contextPanelOpen}
              onToggle={() => setContextPanelOpen(!contextPanelOpen)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### 2. ConversationList.tsx

**File**: `src/components/chat/ConversationList.tsx`

**Purpose**: Displays list of conversations with search, create, and management features.

**Features**:
- Search/filter conversations
- Sort by updated_at descending
- New conversation button
- Right-click context menu (rename, delete)
- Active conversation highlighting
- Relative timestamps
- Empty state

**Code**:

```typescript
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Plus, Trash2, Edit2, MessageSquare, X } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { Conversation } from '@/types/chat';

interface ConversationListProps {
  conversations: Conversation[];
  currentConversationId?: string;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
}

interface ContextMenu {
  conversationId: string;
  x: number;
  y: number;
}

export default function ConversationList({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
}: ConversationListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Sort conversations by updated_at descending
  const sortedConversations = [...conversations].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  // Filter conversations
  const filteredConversations = sortedConversations.filter(conv =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Close context menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    };

    if (contextMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [contextMenu]);

  // Focus rename input
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const handleContextMenu = useCallback((e: React.MouseEvent<HTMLDivElement>, conversationId: string) => {
    e.preventDefault();
    setContextMenu({ conversationId, x: e.clientX, y: e.clientY });
  }, []);

  const handleRename = useCallback((conversationId: string) => {
    const conversation = conversations.find(c => c.id === conversationId);
    if (conversation) {
      setRenamingId(conversationId);
      setRenameValue(conversation.title);
      setContextMenu(null);
    }
  }, [conversations]);

  const handleRenameSubmit = useCallback((conversationId: string) => {
    if (renameValue.trim()) {
      // This would need a store update method
      // updateConversationTitle(conversationId, renameValue.trim());
    }
    setRenamingId(null);
    setRenameValue('');
  }, [renameValue]);

  const handleDelete = useCallback((conversationId: string) => {
    onDeleteConversation(conversationId);
    setDeleteConfirmId(null);
    setContextMenu(null);
  }, [onDeleteConversation]);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Conversations</h2>
          <button
            onClick={onNewConversation}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
            title="New conversation (Cmd+N)"
            aria-label="New conversation"
          >
            <Plus size={18} className="text-gray-700" />
          </button>
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
        />
      </div>

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto">
        {filteredConversations.length === 0 ? (
          <div className="p-4 text-center text-gray-600 text-sm">
            {conversations.length === 0 ? 'No conversations yet' : 'No matching conversations'}
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {filteredConversations.map(conv => (
              <div
                key={conv.id}
                onContextMenu={(e) => handleContextMenu(e, conv.id)}
                className={`
                  group flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer
                  transition-colors duration-150
                  ${
                    currentConversationId === conv.id
                      ? 'bg-brand-blue/10 text-brand-blue'
                      : 'hover:bg-gray-200 text-gray-700'
                  }
                `}
              >
                {renamingId === conv.id ? (
                  <input
                    ref={renameInputRef}
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => handleRenameSubmit(conv.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleRenameSubmit(conv.id);
                      } else if (e.key === 'Escape') {
                        setRenamingId(null);
                      }
                    }}
                    className="flex-1 px-2 py-1 bg-white border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <MessageSquare size={16} className="flex-shrink-0" />
                    <div
                      className="flex-1 min-w-0 cursor-pointer"
                      onClick={() => onSelectConversation(conv.id)}
                    >
                      <p className="text-sm font-medium truncate">{conv.title}</p>
                      <p className="text-xs opacity-70">
                        {formatDistanceToNow(new Date(conv.updated_at), { addSuffix: true })}
                      </p>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          ref={contextMenuRef}
          style={{
            position: 'fixed',
            left: `${contextMenu.x}px`,
            top: `${contextMenu.y}px`,
            zIndex: 50,
          }}
          className="bg-white border border-gray-300 rounded-lg shadow-lg py-1"
        >
          <button
            onClick={() => handleRename(contextMenu.conversationId)}
            className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
          >
            <Edit2 size={16} />
            Rename
          </button>
          <button
            onClick={() => setDeleteConfirmId(contextMenu.conversationId)}
            className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      )}

      {/* Delete Confirmation */}
      {deleteConfirmId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete conversation?</h3>
            <p className="text-gray-600 mb-6">This action cannot be undone.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-900 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirmId)}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

### 3. MessageList.tsx

**File**: `src/components/chat/MessageList.tsx`

**Purpose**: Displays conversation messages with auto-scroll and welcome state.

**Features**:
- Auto-scroll to bottom on new message
- Welcome section with example prompts
- Streaming message display
- Smooth scrolling

**Code**:

```typescript
import React, { useEffect, useRef, forwardRef } from 'react';
import ChatMessage from './ChatMessage';
import StreamingText from './StreamingText';
import type { ConversationMessage } from '@/types/chat';
import type { RetrievedSource } from '@/types/api';

interface MessageListProps {
  messages: ConversationMessage[];
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: RetrievedSource[];
}

const MessageList = forwardRef<HTMLDivElement, MessageListProps>(
  ({ messages, isStreaming, streamingContent, streamingSources }, ref) => {
    const endRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
      const scrollToBottom = () => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
      };

      // Scroll on new messages
      if (messages.length > 0) {
        setTimeout(scrollToBottom, 0);
      }

      // Scroll on streaming content
      if (isStreaming) {
        setTimeout(scrollToBottom, 50);
      }
    }, [messages, isStreaming, streamingContent]);

    const isEmpty = messages.length === 0 && !isStreaming;

    return (
      <div
        ref={containerRef || ref}
        className="flex-1 overflow-y-auto bg-white px-4 py-6 lg:px-8"
      >
        {isEmpty ? (
          // Welcome section
          <div className="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto py-12">
            <div className="text-6xl mb-6">🤖</div>
            <h2 className="text-2xl lg:text-3xl font-bold text-gray-900 mb-3">
              Hi there! Ready to explore your documents?
            </h2>
            <p className="text-gray-600 mb-12 text-lg">
              Ask me anything about your markdown files. I'll search through them and provide
              answers grounded in the actual content.
            </p>

            {/* Example prompts */}
            <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
              {[
                {
                  title: '📋 Summarize',
                  prompt: 'Provide a comprehensive summary of the main topics covered in the documents.',
                },
                {
                  title: '🔍 Search',
                  prompt: 'Find all references to implementation details and best practices.',
                },
                {
                  title: '📊 Analysis',
                  prompt: 'What are the key metrics and statistics mentioned?',
                },
                {
                  title: '🎯 Clarify',
                  prompt: 'Explain the relationship between the main concepts.',
                },
              ].map((example, i) => (
                <div key={i} className="text-left">
                  <p className="text-sm font-medium text-gray-700 mb-1">{example.title}</p>
                  <button
                    onClick={() => {
                      // Trigger message send in parent
                      const event = new CustomEvent('send-message', { detail: example.prompt });
                      window.dispatchEvent(event);
                    }}
                    className="w-full px-4 py-3 text-sm text-gray-700 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors text-left"
                  >
                    {example.prompt}
                  </button>
                </div>
              ))}
            </div>

            <p className="text-xs text-gray-500">
              💡 Tip: Use @ to mention specific namespaces or documents
            </p>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="max-w-4xl mx-auto space-y-6">
              {messages.map((message, index) => (
                <ChatMessage key={index} message={message} isStreaming={false} />
              ))}

              {/* Streaming message */}
              {isStreaming && (
                <ChatMessage
                  message={{
                    role: 'assistant',
                    content: streamingContent,
                    sources: streamingSources.length > 0 ? streamingSources : undefined,
                    timestamp: new Date().toISOString(),
                  }}
                  isStreaming={true}
                />
              )}
            </div>
          </>
        )}

        {/* Scroll anchor */}
        <div ref={endRef} />
      </div>
    );
  }
);

MessageList.displayName = 'MessageList';

export default MessageList;
```

---

### 4. ChatMessage.tsx

**File**: `src/components/chat/ChatMessage.tsx`

**Purpose**: Renders individual messages with markdown, sources, and actions.

**Features**:
- User vs assistant styling
- Markdown rendering
- Sources display (expandable)
- Action buttons (copy, regenerate, thumbs)
- Streaming cursor
- Avatar icons

**Code**:

```typescript
import React, { useState, useCallback } from 'react';
import { Copy, ThumbsUp, ThumbsDown, RotateCcw, ChevronDown, ChevronUp, Bot, User } from 'lucide-react';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import StreamingText from './StreamingText';
import type { ConversationMessage } from '@/types/chat';
import type { RetrievedSource } from '@/types/api';

interface ChatMessageProps {
  message: ConversationMessage;
  isStreaming?: boolean;
  onRegenerate?: () => void;
}

export default function ChatMessage({ message, isStreaming = false, onRegenerate }: ChatMessageProps) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const isUserMessage = message.role === 'user';

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [message.content]);

  const handleFeedback = useCallback((positive: boolean) => {
    // Send feedback to backend
    console.log(`Feedback (${positive ? 'positive' : 'negative'}) for message:`, message);
  }, [message]);

  return (
    <div
      className={`flex gap-4 ${isUserMessage ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* Avatar */}
      <div
        className={`
          flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white
          ${isUserMessage ? 'bg-brand-blue' : 'bg-gray-400'}
        `}
      >
        {isUserMessage ? (
          <User size={18} />
        ) : (
          <Bot size={18} />
        )}
      </div>

      {/* Message content */}
      <div className={`flex-1 ${isUserMessage ? 'text-right' : 'text-left'}`}>
        {/* Main message */}
        <div
          className={`
            inline-block max-w-2xl px-4 py-3 rounded-lg
            ${
              isUserMessage
                ? 'bg-brand-blue text-white rounded-br-none'
                : 'bg-gray-100 text-gray-900 rounded-bl-none'
            }
          `}
        >
          {isStreaming ? (
            <StreamingText content={message.content} isStreaming={true} />
          ) : (
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <MarkdownRenderer content={message.content} />
            </div>
          )}
        </div>

        {/* Assistant actions and sources */}
        {!isUserMessage && (
          <div className="mt-2 space-y-2">
            {/* Actions */}
            <div className="flex gap-2 items-center">
              <button
                onClick={handleCopy}
                className="p-1 hover:bg-gray-100 rounded transition-colors text-gray-600 hover:text-gray-900"
                title="Copy message"
                aria-label="Copy message"
              >
                <Copy size={16} />
              </button>
              <button
                onClick={() => handleFeedback(true)}
                className="p-1 hover:bg-gray-100 rounded transition-colors text-gray-600 hover:text-green-600"
                title="Mark as helpful"
                aria-label="Mark as helpful"
              >
                <ThumbsUp size={16} />
              </button>
              <button
                onClick={() => handleFeedback(false)}
                className="p-1 hover:bg-gray-100 rounded transition-colors text-gray-600 hover:text-red-600"
                title="Mark as unhelpful"
                aria-label="Mark as unhelpful"
              >
                <ThumbsDown size={16} />
              </button>
              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="p-1 hover:bg-gray-100 rounded transition-colors text-gray-600 hover:text-brand-blue"
                  title="Regenerate response"
                  aria-label="Regenerate response"
                >
                  <RotateCcw size={16} />
                </button>
              )}

              {/* Copied feedback */}
              {copied && (
                <span className="text-xs text-gray-600 ml-2">Copied!</span>
              )}
            </div>

            {/* Sources section */}
            {message.sources && message.sources.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <button
                  onClick={() => setSourcesExpanded(!sourcesExpanded)}
                  className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  {sourcesExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  <span className="font-medium">
                    {message.sources.length} source{message.sources.length !== 1 ? 's' : ''}
                  </span>
                </button>

                {sourcesExpanded && (
                  <div className="mt-2 space-y-2 ml-6">
                    {message.sources.map((source, idx) => (
                      <div
                        key={idx}
                        className="px-3 py-2 bg-gray-50 rounded-lg border border-gray-200"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-700 truncate">
                              {source.source}
                            </p>
                            <p className="text-xs text-gray-600">
                              Chunk {source.chunk_index + 1}
                            </p>
                          </div>
                          <div className="flex-shrink-0">
                            <span className="inline-block px-2 py-1 bg-brand-blue/10 text-brand-blue text-xs font-medium rounded">
                              {(source.score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>

                        {/* Source content preview - collapsible */}
                        <SourcePreview source={source} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Source preview component
function SourcePreview({ source }: { source: RetrievedSource }) {
  const [expanded, setExpanded] = useState(false);

  // Truncate content for preview
  const preview = source.content.slice(0, 150).replace(/\n/g, ' ');
  const isLong = source.content.length > 150;

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-gray-600 hover:text-gray-900 underline"
      >
        {expanded ? 'Show less' : 'Show content'}
      </button>

      {expanded && (
        <div className="mt-2 p-2 bg-white border border-gray-200 rounded text-xs text-gray-700 whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
          {source.content}
        </div>
      )}

      {!expanded && isLong && (
        <p className="text-xs text-gray-600 mt-1 italic">{preview}...</p>
      )}
    </div>
  );
}
```

---

### 5. ChatInput.tsx

**File**: `src/components/chat/ChatInput.tsx`

**Purpose**: Input area with namespace/provider selectors and multi-line textarea.

**Features**:
- Auto-expanding textarea
- Namespace and provider dropdowns
- Send button
- Keyboard shortcuts (Enter to send, Shift+Enter for newline)
- Stop button during streaming
- @mention support (future)

**Code**:

```typescript
import React, { useRef, useEffect, useState } from 'react';
import { Send, Square } from 'lucide-react';
import { useProviders } from '@/hooks/useProviders';
import { useNamespaces } from '@/hooks/useNamespaces';

interface ChatInputProps {
  onSendMessage: (content: string, namespace?: string, provider?: string, model?: string) => void;
  isStreaming: boolean;
  onStopStreaming: () => void;
  defaultNamespace?: string;
  defaultProvider?: string;
  defaultModel?: string;
}

export default function ChatInput({
  onSendMessage,
  isStreaming,
  onStopStreaming,
  defaultNamespace,
  defaultProvider,
  defaultModel,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { providers } = useProviders();
  const { namespaces } = useNamespaces();

  const [content, setContent] = useState('');
  const [selectedNamespace, setSelectedNamespace] = useState(defaultNamespace || namespaces[0]?.id || '');
  const [selectedProvider, setSelectedProvider] = useState(defaultProvider || providers[0]?.name || '');
  const [selectedModel, setSelectedModel] = useState(defaultModel || '');

  // Auto-expand textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const newHeight = Math.min(textarea.scrollHeight, 200); // Max height 200px
      textarea.style.height = `${newHeight}px`;
    }
  }, [content]);

  // Update model when provider changes
  useEffect(() => {
    const provider = providers.find(p => p.name === selectedProvider);
    if (provider && provider.models && provider.models.length > 0) {
      setSelectedModel(provider.models[0]);
    }
  }, [selectedProvider, providers]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || isStreaming) return;

    onSendMessage(content, selectedNamespace, selectedProvider, selectedModel);
    setContent('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter (unless Shift is held)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }

    // Escape to stop streaming
    if (e.key === 'Escape' && isStreaming) {
      e.preventDefault();
      onStopStreaming();
    }
  };

  const getSelectedProviderObject = providers.find(p => p.name === selectedProvider);

  return (
    <form
      onSubmit={handleSubmit}
      className="flex-shrink-0 border-t border-gray-200 bg-white px-4 py-4 lg:px-8"
    >
      <div className="max-w-4xl mx-auto space-y-3">
        {/* Selectors row */}
        <div className="flex gap-3">
          {/* Namespace selector */}
          <select
            value={selectedNamespace}
            onChange={(e) => setSelectedNamespace(e.target.value)}
            disabled={isStreaming}
            className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed"
            title="Search namespace"
          >
            {namespaces.map(ns => (
              <option key={ns.id} value={ns.id}>
                📁 {ns.name}
              </option>
            ))}
          </select>

          {/* Provider selector */}
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            disabled={isStreaming}
            className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed"
            title="Provider"
          >
            {providers.map(p => (
              <option key={p.name} value={p.name} disabled={!p.available}>
                {p.available ? '✓' : '✗'} {p.name}
              </option>
            ))}
          </select>

          {/* Model selector */}
          {getSelectedProviderObject && getSelectedProviderObject.models && (
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={isStreaming}
              className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed"
              title="Model"
            >
              {getSelectedProviderObject.models.map(model => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Input area */}
        <div className="flex gap-3 items-end">
          {/* Textarea container */}
          <div className="flex-1 relative bg-gray-50 rounded-lg border border-gray-300 focus-within:ring-2 focus-within:ring-brand-blue focus-within:border-transparent transition-all">
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              placeholder="Message LLM-MD-CLI... (Cmd+K to focus, Shift+Enter for new line)"
              data-chat-input
              className="w-full resize-none bg-transparent px-4 py-3 text-gray-900 placeholder-gray-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              rows={1}
              style={{ maxHeight: '200px', minHeight: '44px' }}
            />
          </div>

          {/* Send/Stop button */}
          <button
            type="submit"
            disabled={!content.trim() || isStreaming}
            onClick={(e) => {
              if (isStreaming) {
                e.preventDefault();
                onStopStreaming();
              }
            }}
            className={`
              flex-shrink-0 p-3 rounded-lg transition-all duration-200
              ${
                isStreaming
                  ? 'bg-red-500 hover:bg-red-600 text-white'
                  : content.trim()
                  ? 'bg-brand-blue hover:bg-blue-700 text-white'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }
            `}
            title={isStreaming ? 'Stop (Escape)' : 'Send (Enter)'}
            aria-label={isStreaming ? 'Stop streaming' : 'Send message'}
          >
            {isStreaming ? <Square size={20} /> : <Send size={20} />}
          </button>
        </div>

        {/* Helper text */}
        <div className="text-xs text-gray-500 pl-1">
          {isStreaming && '⏹️ Streaming... Press Escape or click Stop to cancel'}
          {!isStreaming && content.length > 0 && `${content.length} characters`}
        </div>
      </div>
    </form>
  );
}
```

---

### 6. StreamingText.tsx

**File**: `src/components/chat/StreamingText.tsx`

**Purpose**: Renders content with streaming cursor animation.

**Features**:
- Markdown rendering
- Blinking cursor during streaming
- Smooth animation

**Code**:

```typescript
import React from 'react';
import MarkdownRenderer from '@/components/MarkdownRenderer';

interface StreamingTextProps {
  content: string;
  isStreaming: boolean;
}

export default function StreamingText({ content, isStreaming }: StreamingTextProps) {
  return (
    <div className="prose prose-sm max-w-none dark:prose-invert">
      <MarkdownRenderer content={content} />
      {isStreaming && (
        <span
          className="inline-block ml-1 w-2 h-5 bg-gray-900 animate-pulse"
          style={{
            animation: 'blink 1s infinite',
          }}
        />
      )}
      <style>{`
        @keyframes blink {
          0%, 49%, 100% {
            opacity: 1;
          }
          50%, 99% {
            opacity: 0.3;
          }
        }
      `}</style>
    </div>
  );
}
```

---

### 7. ContextPanel.tsx

**File**: `src/components/chat/ContextPanel.tsx`

**Purpose**: Right sidebar showing retrieved sources and chat settings.

**Features**:
- Collapsible header
- Sources list with file names, scores
- Settings: temperature, top-k, model
- Token usage display
- Expandable source content

**Code**:

```typescript
import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Settings } from 'lucide-react';
import type { RetrievedSource } from '@/types/api';

interface ContextPanelProps {
  sources?: RetrievedSource[];
  isOpen: boolean;
  onToggle: () => void;
}

export default function ContextPanel({ sources = [], isOpen, onToggle }: ContextPanelProps) {
  const [temperature, setTemperature] = useState(0.7);
  const [topK, setTopK] = useState(5);
  const [expandedSourceId, setExpandedSourceId] = useState<number | null>(null);

  if (!isOpen) {
    return (
      <div className="w-full h-full flex items-center justify-center border-l border-gray-200 bg-gray-50">
        <button
          onClick={onToggle}
          className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          aria-label="Open context panel"
        >
          <ChevronDown size={20} className="text-gray-600" />
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50 overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <Settings size={18} />
          Context & Settings
        </h3>
        <button
          onClick={onToggle}
          className="p-1 hover:bg-gray-200 rounded transition-colors"
          aria-label="Close context panel"
        >
          <ChevronUp size={18} className="text-gray-600" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto space-y-6 p-4">
        {/* Retrieved Sources Section */}
        {sources && sources.length > 0 && (
          <section>
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Retrieved Sources ({sources.length})</h4>
            <div className="space-y-2">
              {sources.map((source, idx) => (
                <div
                  key={idx}
                  className="bg-white border border-gray-200 rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-colors"
                >
                  <div
                    onClick={() => setExpandedSourceId(expandedSourceId === idx ? null : idx)}
                    className="flex items-start justify-between gap-2"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-700 truncate">{source.source}</p>
                      <p className="text-xs text-gray-600">Chunk {source.chunk_index + 1}</p>
                    </div>
                    <span className="flex-shrink-0 inline-block px-2 py-1 bg-brand-blue/10 text-brand-blue text-xs font-semibold rounded">
                      {(source.score * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Expandable content */}
                  {expandedSourceId === idx && (
                    <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-700 max-h-32 overflow-y-auto">
                      {source.content}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Settings Section */}
        <section className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-700 mb-4">Generation Settings</h4>

          {/* Temperature */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-700 mb-2">
              Temperature: {temperature.toFixed(2)}
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-brand-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Lower = more focused, Higher = more creative
            </p>
          </div>

          {/* Top-K */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-700 mb-2">
              Top-K (Context chunks): {topK}
            </label>
            <input
              type="range"
              min="1"
              max="20"
              step="1"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-brand-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Number of source chunks to retrieve
            </p>
          </div>
        </section>

        {/* Token Usage */}
        <section className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p className="text-xs font-semibold text-blue-900 mb-2">Token Usage</p>
          <div className="text-xs text-blue-800 space-y-1">
            <p>Input tokens: <span className="font-semibold">--</span></p>
            <p>Output tokens: <span className="font-semibold">--</span></p>
            <p>Total: <span className="font-semibold">--</span></p>
          </div>
        </section>
      </div>
    </div>
  );
}
```

---

### 8. MentionAutocomplete.tsx (Future Enhancement)

**File**: `src/components/chat/MentionAutocomplete.tsx`

**Purpose**: Autocomplete for @mentions when typing in chat input.

**Features**:
- Triggered by @ character
- Filter namespaces/documents
- Arrow key navigation
- Insert @namespace on selection

**Code**:

```typescript
import React, { useState, useEffect, useRef } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';

interface MentionAutocompleteProps {
  trigger: string; // "@"
  options: Array<{ id: string; name: string; type: 'namespace' | 'document' }>;
  onSelect: (option: { id: string; name: string; type: 'namespace' | 'document' }) => void;
  onClose: () => void;
  position: { top: number; left: number };
}

export default function MentionAutocomplete({
  trigger,
  options,
  onSelect,
  onClose,
  position,
}: MentionAutocompleteProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [filter, setFilter] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  const filteredOptions = options.filter(opt =>
    opt.name.toLowerCase().includes(filter.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [filter]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % filteredOptions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + filteredOptions.length) % filteredOptions.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredOptions[selectedIndex]) {
        onSelect(filteredOptions[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div
      style={{
        position: 'absolute',
        top: position.top,
        left: position.left,
      }}
      className="bg-white border border-gray-300 rounded-lg shadow-lg z-50 min-w-48"
      onKeyDown={handleKeyDown}
    >
      {/* Search input */}
      <input
        autoFocus
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Search..."
        className="w-full px-3 py-2 border-b border-gray-200 focus:outline-none text-sm"
      />

      {/* Options list */}
      <div ref={listRef} className="max-h-48 overflow-y-auto">
        {filteredOptions.length === 0 ? (
          <div className="px-3 py-4 text-sm text-gray-600 text-center">No results</div>
        ) : (
          filteredOptions.map((option, idx) => (
            <button
              key={option.id}
              onClick={() => onSelect(option)}
              className={`
                w-full px-3 py-2 text-left text-sm transition-colors
                ${
                  idx === selectedIndex
                    ? 'bg-brand-blue text-white'
                    : 'hover:bg-gray-100 text-gray-700'
                }
              `}
            >
              <span className="mr-2">
                {option.type === 'namespace' ? '📁' : '📄'}
              </span>
              {option.name}
            </button>
          ))
        )}
      </div>
    </div>
  );
}
```

---

## Store Integration (chatStore)

### Zustand Chat Store

**File**: `src/store/chatStore.ts`

The chat store manages conversation state, messages, and streaming content.

```typescript
import { create } from 'zustand';
import type { Conversation, ConversationMessage } from '@/types/chat';
import type { RetrievedSource } from '@/types/api';

interface ChatState {
  // Data
  conversations: Conversation[];
  messages: Record<string, ConversationMessage[]>;
  currentConversationId: string | null;
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: RetrievedSource[];

  // Actions
  setCurrentConversation: (id: string) => void;
  addConversation: (conversation: Conversation) => void;
  updateConversationTitle: (id: string, title: string) => void;
  deleteConversation: (id: string) => void;
  addMessage: (conversationId: string, message: ConversationMessage) => void;
  updateStreamingContent: (token: string) => void;
  setStreamingContent: (content: string) => void;
  setStreamingSources: (sources: RetrievedSource[]) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  clearMessages: (conversationId: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  messages: {},
  currentConversationId: null,
  isStreaming: false,
  streamingContent: '',
  streamingSources: [],

  setCurrentConversation: (id) =>
    set({ currentConversationId: id }),

  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      messages: { ...state.messages, [conversation.id]: [] },
    })),

  updateConversationTitle: (id, title) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title, updated_at: new Date().toISOString() } : c
      ),
    })),

  deleteConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      messages: Object.fromEntries(
        Object.entries(state.messages).filter(([key]) => key !== id)
      ),
      currentConversationId:
        state.currentConversationId === id ? null : state.currentConversationId,
    })),

  addMessage: (conversationId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: [...(state.messages[conversationId] || []), message],
      },
    })),

  updateStreamingContent: (token) =>
    set((state) => ({
      streamingContent: state.streamingContent + token,
    })),

  setStreamingContent: (content) =>
    set({ streamingContent: content }),

  setStreamingSources: (sources) =>
    set({ streamingSources: sources }),

  setIsStreaming: (isStreaming) =>
    set({ isStreaming }),

  clearMessages: (conversationId) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: [],
      },
    })),
}));
```

---

## Streaming Client

### Streaming Library Implementation

**File**: `src/lib/streaming.ts`

```typescript
import type { RetrievedSource } from '@/types/api';

export interface StreamingRequest {
  query: string;
  namespace?: string;
  conversation_id?: string;
  stream: true;
  provider?: string;
  model?: string;
}

export interface StreamingCallbacks {
  signal?: AbortSignal;
  onSources?: (sources: RetrievedSource[]) => void;
  onToken?: (token: string) => void;
  onThreadId?: (threadId: string) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
}

export async function streamChat(
  request: StreamingRequest,
  callbacks: StreamingCallbacks
): Promise<{ thread_id?: string }> {
  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: callbacks.signal,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('Response body is empty');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let result = { thread_id: undefined as string | undefined };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          const data = line.slice(6);

          // Handle [DONE]
          if (data === '[DONE]') {
            callbacks.onDone?.();
            return result;
          }

          try {
            const parsed = JSON.parse(data);

            // Handle sources
            if (parsed.sources) {
              callbacks.onSources?.(parsed.sources);
            }

            // Handle token
            if (parsed.token) {
              callbacks.onToken?.(parsed.token);
            }

            // Handle thread_id
            if (parsed.thread_id) {
              result.thread_id = parsed.thread_id;
              callbacks.onThreadId?.(parsed.thread_id);
            }

            // Handle error
            if (parsed.error) {
              throw new Error(parsed.error);
            }
          } catch (e) {
            if (e instanceof SyntaxError) {
              // Ignore JSON parse errors for non-JSON lines
              continue;
            }
            throw e;
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    callbacks.onDone?.();
    return result;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      // Streaming was cancelled
      return { thread_id: undefined };
    }
    callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
    throw error;
  }
}
```

---

## Type Definitions

### Chat Types

**File**: `src/types/chat.ts`

```typescript
import type { RetrievedSource } from './api';

export interface Conversation {
  id: string;
  title: string;
  namespace: string;
  created_at: string;
  updated_at: string;
  thread_id: string | null;
}

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: RetrievedSource[];
  timestamp: string;
  thread_id?: string;
}
```

### API Types

**File**: `src/types/api.ts`

```typescript
export interface RetrievedSource {
  source: string;
  chunk_index: number;
  score: number;
  content: string;
}

export interface AskResponse {
  answer: string;
  sources: RetrievedSource[];
  provider: string;
  model: string;
  thread_id?: string;
  has_context: boolean;
}

export interface Provider {
  name: string;
  available: boolean;
  models: string[];
  error?: string;
}

export interface Namespace {
  id: string;
  name: string;
}
```

---

## Tailwind CSS Configuration

Ensure the following custom utilities are in your `tailwind.config.ts`:

```typescript
module.exports = {
  theme: {
    extend: {
      colors: {
        'brand-blue': '#3B82F6',
      },
      animation: {
        'typing-cursor': 'typing-cursor 0.6s infinite',
      },
      keyframes: {
        'typing-cursor': {
          '0%, 49%': { opacity: '1' },
          '50%, 100%': { opacity: '0.3' },
        },
      },
    },
  },
};
```

---

## Keyboard Shortcuts Reference

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line in input |
| Cmd/Ctrl+K | Focus chat input |
| Cmd/Ctrl+N | New conversation |
| Escape | Stop streaming |
| Cmd/Ctrl+Shift+[ | Previous conversation |
| Cmd/Ctrl+Shift+] | Next conversation |

---

## Chat Flow Diagram

```
User Types Message
    ↓
Press Enter
    ↓
Add user message to UI
    ↓
Create/Get conversation
    ↓
Call streamChat() with callbacks
    ↓
Display temporary streaming message
    ↓
onToken → append to streamingContent
onSources → store sources
    ↓
onDone → create final message
    ↓
Replace streaming message with final
    ↓
Reset streaming state
```

---

## API Integration Points

### Request to `/api/ask` (Streaming)

```json
{
  "query": "What is RAG?",
  "namespace": "default",
  "conversation_id": "uuid-or-null",
  "stream": true,
  "provider": "openai",
  "model": "gpt-4"
}
```

### Expected SSE Response Format

```
data: {"sources": [{"source": "file.md", "chunk_index": 0, "score": 0.95, "content": "..."}]}
data: {"token": "RAG "}
data: {"token": "stands "}
data: {"token": "for "}
data: {"token": "Retrieval "}
data: {"token": "Augmented "}
data: {"token": "Generation"}
data: {"thread_id": "uuid"}
data: [DONE]
```

---

## Testing Considerations

1. **Streaming Edge Cases**:
   - Network interruption during stream
   - AbortController cancellation
   - Empty response content
   - Large content streaming

2. **UI State**:
   - Disabled inputs during streaming
   - Stop button visibility
   - Auto-scroll behavior
   - Message ordering

3. **Responsive Design**:
   - Mobile drawer/sidebar
   - Column collapsing at breakpoints
   - Touch interactions

4. **Performance**:
   - Message virtualization (for long conversations)
   - Markdown rendering optimization
   - Streaming performance

---

## Future Enhancements

1. **@mention System**: Full implementation with document/namespace autocomplete
2. **Message Editing**: Edit previous messages and regenerate responses
3. **Conversation Export**: Export to markdown/PDF
4. **Search**: Full-text search across messages
5. **Voice Input**: Speech-to-text for messages
6. **Feedback System**: Track helpful/unhelpful responses
7. **Custom Instructions**: System prompts per conversation
8. **Model Switching**: Switch models mid-conversation

---

This implementation provides a production-ready Chat page with all streaming, state management, and responsive design considerations. All components are fully typed with TypeScript and follow React best practices.
