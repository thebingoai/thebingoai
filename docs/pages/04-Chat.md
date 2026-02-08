# Chat Page

**Route:** `/chat` or `/chat/:conversationId`  
**Purpose:** RAG-powered conversational interface  
**Priority:** P0

---

## Wireframe - Empty State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]    [🌙]           │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │  💬 Chat                                                         │
│  📊      │                                                                  │
│  📄 Docs │  ┌───────────────────────────────────────────────────────────┐  │
│  🔍 Search│  │                                                             │  │
│  💬 Chat │  │                  🤖 LLM-MD-CLI                              │  │
│  ⚙️ Jobs │  │                                                             │  │
│  ⚙️ Settings│  │  Ask questions about your documents                        │  │
│          │  │                                                             │  │
│          │  │  Examples:                                                  │  │
│          │  │  • "Summarize my meeting notes"                            │  │
│          │  │  • "What did we decide about the API?"                     │  │
│          │  │  • "Find all TODO items in my notes"                       │  │
│          │  │                                                             │  │
│          │  │  ┌─────────────────────────────────────────────────────┐   │  │
│          │  │  │  Select a namespace to get started...              │   │  │
│          │  │  │                                                     │   │  │
│          │  │  │  [📁 personal ▼]  [🚀 Start Chat]                  │   │  │
│          │  │  └─────────────────────────────────────────────────────┘   │  │
│          │  │                                                             │  │
│          │  └───────────────────────────────────────────────────────────┘  │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

## Wireframe - Active Chat

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]    [🌙]    [⚙️]   │
├──────────┬───────────┬──────────────────────────────────────────────────────┤
│          │ Conversations          │ Chat: General Questions               │
│  📊      │                        │                                       │
│  📄 Docs │ 🔍 Search chats...     │  ┌─────────────────────────────────┐  │
│  🔍 Search│                        │  │ 👤 What are embeddings?         │  │
│  💬 Chat │ 💬 General Questions   │  │     @personal                   │  │
│  ⚙️ Jobs │    2h ago             │  └─────────────────────────────────┘  │
│  ⚙️ Settings│ ➕ New Chat          │                                       │
│          │                        │  ┌─────────────────────────────────┐  │
│          │ 💬 API Design Decisions│  │ 🤖 Embeddings are dense vector  │  │
│          │    Yesterday          │  │    representations that capture │  │
│          │                        │  │    semantic meaning...          │  │
│          │ 💬 Project Roadmap     │  │                                 │  │
│          │    3 days ago         │  │    Based on your personal notes │  │
│          │                        │  │    (3 sources):                 │  │
│          │ ─────────────────     │  │    • notes.md                   │  │
│          │                        │  │    • meeting-notes.md           │  │
│          │ Context: @personal    │  │    • todo.md                    │  │
│          │ Provider: openai      │  │                                 │  │
│          │ Model: gpt-4o         │  │ [👍] [👎] [🔄 Regenerate]      │  │
│          │                        │  └─────────────────────────────────┘  │
│          │                        │                                       │
│          │                        │  ┌─────────────────────────────────┐  │
│          │                        │  │ 👤 How do they work?           │  │
│          │                        │  └─────────────────────────────────┘  │
│          │                        │                                       │
│          │                        │  ┌─────────────────────────────────┐  │
│          │                        │  │ 🤖 ▌Generating response...      │  │
│          │                        │  └─────────────────────────────────┘  │
│          │                        │                                       │
│          │                        │                                       │
│          │                        │  ┌───────────────────────────────────┐  │
│          │                        │  │ 📁 personal ▼  │  📝 Message...  │  │
│          │                        │  │                │                 │  │
│          │                        │  │ openai ▼       │ [➤]            │  │
│          │                        │  └───────────────────────────────────┘  │
│          │                        │                                       │
└──────────┴───────────┴──────────────────────────────────────────────────────┘
```

## Wireframe - Context Panel (Expanded)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌──────────────────┬──────────────────────┬─────────────────────────────┐  │
│  │ Conversations    │ Chat                 │ Retrieved Context           │  │
│  │                  │                      │                             │  │
│  │  ...             │  ...                 │ 📚 Sources (3 chunks)       │  │
│  │                  │                      │                             │  │
│  │                  │                      │ 1. notes.md #chunk-2        │  │
│  │                  │                      │    Score: 0.92              │  │
│  │                  │                      │    ...word embeddings...    │  │
│  │                  │                      │                             │  │
│  │                  │                      │ 2. meeting.md #chunk-5      │  │
│  │                  │                      │    Score: 0.87              │  │
│  │                  │                      │    ...embeddings for...     │  │
│  │                  │                      │                             │  │
│  │                  │                      │ 3. todo.md #chunk-1         │  │
│  │                  │                      │    Score: 0.81              │  │
│  │                  │                      │    ...embedding model...    │  │
│  │                  │                      │                             │  │
│  │                  │                      │ [📄 View All in Search]     │  │
│  │                  │                      │                             │  │
│  │                  │                      │ ─────────────────────────   │  │
│  │                  │                      │                             │  │
│  │                  │                      │ 🎛️ Settings                │  │
│  │                  │                      │ Temperature: [━━●──] 0.7   │  │
│  │                  │                      │ Top-K: [5 ▼]               │  │
│  │                  │                      │                             │  │
│  └──────────────────┴──────────────────────┴─────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layout

**3-Column Layout (Desktop):**
- **Left (250px):** Conversation list
- **Center (flex):** Chat messages
- **Right (300px, collapsible):** Context panel

**2-Column Layout (Tablet):**
- Left: Conversations (collapsible)
- Center: Chat

**Single Column (Mobile):**
- Full-screen chat
- Drawer for conversations

---

## Sections

### 1. Conversation Sidebar

**Header:**
- Title: "Conversations"
- Search input (filter conversations)
- "New Chat" button

**Conversation List:**
- Sorted by: last message time (desc)
- Each item shows:
  - 💬 Icon
  - Title (first message or "New Chat")
  - Timestamp (relative)
  - Unread indicator

**Interactions:**
- Click → Switch to conversation
- Right-click → Rename, Delete
- Swipe left (mobile) → Delete

**Empty State:**
```
No conversations yet
Start by asking a question
```

### 2. Chat Header

**Elements:**
- Conversation title (editable inline)
- Context indicator: "📁 @personal"
- Model indicator: "🤖 openai/gpt-4o"
- Actions: [Clear] [Settings] [Export]

### 3. Message Area

**User Message:**
```
┌─────────────────────────────────────────────────────────────┐
│                                         ┌─────────────────┐ │
│                                         │ 👤 Message text │ │
│                                         │ @personal       │ │
│                                         └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Assistant Message:**
```
┌─────────────────────────────────────────────────────────────┐
│ 🤖                                                          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Response text with **markdown** support                 │ │
│ │                                                         │ │
│ │ ```python                                               │ │
│ │ # Code blocks highlighted                               │ │
│ │ ```                                                     │ │
│ │                                                         │ │
│ │ 📚 Sources: notes.md, meeting.md                      │ │
│ │                                                         │ │
│ │ [👍] [👎] [🔄] [📋 Copy]                              │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Message Actions:**
- 👍 / 👎 - Feedback
- 🔄 - Regenerate response
- 📋 - Copy to clipboard
- 👁️ - View sources (if not shown)

### 4. Input Area

**Components:**
```
┌─────────────────────────────────────────────────────────────┐
│ 📁 [personal ▼]  │  [📝 Type your message...    ]  [➤]    │
│ 🤖 [openai ▼]    │  @mention for context                    │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Multi-line text input (auto-expand)
- @mention autocomplete for namespaces
- Namespace selector dropdown
- Provider/model selector
- Send button (or Enter to send, Shift+Enter for newline)

**Mentions:**
- Type "@" → Show namespace dropdown
- Select → Adds namespace tag to message
- Multiple namespaces allowed

### 5. Context Panel (Right Sidebar)

**Sections:**

**Retrieved Chunks:**
- List of chunks used for current response
- Each shows:
  - Source document
  - Chunk number
  - Similarity score
  - Content preview
- Click → Open document at chunk

**Settings:**
- Temperature slider (0.0 - 1.0)
- Top-K selector
- Max tokens input
- System prompt (advanced)

**Token Usage:**
- Input tokens
- Output tokens
- Total for conversation

---

## Streaming Response

**Behavior:**
1. User sends message
2. Show "🤖 Thinking..." indicator
3. Start receiving SSE stream
4. Render tokens as they arrive (typewriter effect)
5. Show sources when received
6. Enable actions when complete

**Loading States:**
```
┌─────────────────────────────────────────────────────────┐
│ 🤖                                                      │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ▌Generating response...                             │ │
│ │ ⏳ Retrieving context...                            │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Components Needed

| Component | File |
|-----------|------|
| ConversationList | `components/chat/ConversationList.tsx` |
| ConversationItem | `components/chat/ConversationItem.tsx` |
| MessageList | `components/chat/MessageList.tsx` |
| UserMessage | `components/chat/UserMessage.tsx` |
| AssistantMessage | `components/chat/AssistantMessage.tsx` |
| ChatInput | `components/chat/ChatInput.tsx` |
| MentionAutocomplete | `components/chat/MentionAutocomplete.tsx` |
| ContextPanel | `components/chat/ContextPanel.tsx` |
| StreamingText | `components/chat/StreamingText.tsx` |
| SourcesList | `components/chat/SourcesList.tsx` |

---

## API Endpoints

```typescript
// Send message (streaming)
POST /api/ask
  Body: {
    question: string;
    namespace: string;
    provider: string;
    model?: string;
    temperature: number;
    thread_id?: string;
    stream: true;
  }
  Response: SSE stream

// Get conversation history
GET /api/conversation/{thread_id}
  Response: {
    thread_id: string;
    messages: Array<{
      role: 'user' | 'assistant';
      content: string;
      sources?: Source[];
    }>
  }

// Delete conversation
DELETE /api/conversation/{thread_id}

// Get providers
GET /api/providers
```

---

## State Management

```typescript
interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Message[];
  isStreaming: boolean;
  streamContent: string;
  
  // Input state
  inputText: string;
  selectedNamespace: string;
  selectedProvider: string;
  
  // Settings
  temperature: number;
  topK: number;
  
  // Actions
  sendMessage: (text: string) => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  createConversation: () => string;
  deleteConversation: (id: string) => Promise<void>;
  regenerateMessage: (messageId: string) => Promise<void>;
}
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift + Enter` | New line in input |
| `Cmd/Ctrl + K` | Focus chat input |
| `Cmd/Ctrl + N` | New conversation |
| `Cmd/Ctrl + Shift + [` | Previous conversation |
| `Cmd/Ctrl + Shift + ]` | Next conversation |
| `Escape` | Stop streaming |
| `@` | Trigger namespace mention |

---

## Empty States

**No Conversations:**
```
┌─────────────────────────────────────┐
│           💬                        │
│     No conversations yet            │
│                                     │
│  Start chatting with your           │
│  documents to see them here         │
│                                     │
│     [Start New Chat]                │
└─────────────────────────────────────┘
```

**No Namespace Selected:**
```
Select a namespace to start chatting
[Select Namespace ▼]
```

---

## Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| Desktop (≥1280px) | 3-column (conv, chat, context) |
| Tablet (≥768px) | 2-column (conv, chat), context drawer |
| Mobile (<768px) | 1-column, conv drawer, no context |

**Mobile:**
- Conversations in drawer (slide from left)
- Input fixed to bottom
- Swipe gestures for navigation
