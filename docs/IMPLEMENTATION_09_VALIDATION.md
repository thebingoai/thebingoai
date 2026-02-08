# Implementation 09 — Validation & Browser Testing with MCP

**Purpose:** Systematic validation checklist for verifying the frontend using Claude's MCP browser tools after each implementation phase.
**Method:** Use `mcp__Claude_in_Chrome` tools to navigate, inspect, screenshot, and verify each page.

---

## Table of Contents

1. [Pre-Validation Setup](#1-pre-validation-setup)
2. [Phase 1: Foundation Validation](#2-phase-1-foundation-validation)
3. [Phase 2: Component Library Validation](#3-phase-2-component-library-validation)
4. [Phase 3: Dashboard Validation](#4-phase-3-dashboard-validation)
5. [Phase 4: Documents Validation](#5-phase-4-documents-validation)
6. [Phase 5: Search Validation](#6-phase-5-search-validation)
7. [Phase 6: Chat Validation](#7-phase-6-chat-validation)
8. [Phase 7: Jobs Validation](#8-phase-7-jobs-validation)
9. [Phase 8: Settings Validation](#9-phase-8-settings-validation)
10. [Cross-Cutting Validations](#10-cross-cutting-validations)
11. [MCP Tool Reference](#11-mcp-tool-reference)

---

## 1. Pre-Validation Setup

### 1.1 Start Development Server

```bash
cd frontend
npm install
npm run dev
# Verify: Server starts on http://localhost:3000
```

### 1.2 Start Backend Server

```bash
cd backend
uvicorn backend.main:app --reload --port 8000
# Verify: http://localhost:8000/health returns { "status": "healthy" }
```

### 1.3 MCP Browser Initialization

```
Step 1: Call mcp__Claude_in_Chrome__tabs_context_mcp to get tab context
Step 2: Call mcp__Claude_in_Chrome__tabs_create_mcp to create a new tab
Step 3: Call mcp__Claude_in_Chrome__navigate with url: "http://localhost:3000"
Step 4: Take screenshot to verify initial load
```

---

## 2. Phase 1: Foundation Validation

### 2.1 Layout Shell

| # | Check | MCP Tool | Expected Result |
|---|-------|----------|-----------------|
| 1 | Page loads without errors | `navigate` → `read_console_messages(pattern: "error")` | No error messages |
| 2 | Sidebar renders at 260px | `computer(action: "screenshot")` | Left sidebar visible with nav items |
| 3 | Header renders at 64px | `computer(action: "screenshot")` | Top header bar visible |
| 4 | Main content area fills remaining space | `read_page(filter: "main")` | Main content element exists |
| 5 | All 6 nav items visible | `find(query: "navigation links")` | Dashboard, Documents, Search, Chat, Jobs, Settings |

### 2.2 Navigation

| # | Check | MCP Tool | Expected Result |
|---|-------|----------|-----------------|
| 1 | Click "Documents" nav link | `find(query: "Documents nav")` → `computer(action: "click")` | URL changes to /documents |
| 2 | Click "Search" nav link | `find(query: "Search nav")` → `computer(action: "click")` | URL changes to /search |
| 3 | Click "Chat" nav link | `find(query: "Chat nav")` → `computer(action: "click")` | URL changes to /chat |
| 4 | Active nav item highlighted | `computer(action: "screenshot")` | Current page link has brand color |
| 5 | Click logo → home | `find(query: "LLM-MD-CLI logo")` → `computer(action: "click")` | URL changes to / |

### 2.3 Sidebar Collapse

| # | Check | MCP Tool | Expected Result |
|---|-------|----------|-----------------|
| 1 | Find collapse toggle | `find(query: "collapse sidebar button")` | Button found |
| 2 | Click collapse | `computer(action: "click")` | Sidebar narrows to 72px, labels hidden |
| 3 | Icons still visible | `computer(action: "screenshot")` | Nav icons visible, no labels |
| 4 | Click expand | `computer(action: "click")` on toggle | Sidebar returns to 260px |

### 2.4 Theme Toggle

| # | Check | MCP Tool | Expected Result |
|---|-------|----------|-----------------|
| 1 | Find theme toggle | `find(query: "theme toggle")` | Sun/Moon button found |
| 2 | Click → dark mode | `computer(action: "click")` | Background changes to dark |
| 3 | Screenshot dark mode | `computer(action: "screenshot")` | Dark backgrounds, light text |
| 4 | Click → light mode | `computer(action: "click")` | Background changes to light |

### 2.5 Responsive (Mobile)

| # | Check | MCP Tool | Expected Result |
|---|-------|----------|-----------------|
| 1 | Resize to mobile | `resize_window(width: 375, height: 812)` | Mobile layout |
| 2 | Sidebar hidden | `computer(action: "screenshot")` | No sidebar visible |
| 3 | Hamburger menu visible | `find(query: "menu button")` | Hamburger icon found |
| 4 | Click hamburger | `computer(action: "click")` | Mobile nav drawer opens |
| 5 | Click nav item | Click any link | Drawer closes, navigates |
| 6 | Reset to desktop | `resize_window(width: 1440, height: 900)` | Full layout restored |

---

## 3. Phase 2: Component Library Validation

### 3.1 Create a Test Page

Create a temporary `/test-components` route that renders all UI components with sample data. This page is for development-time validation only.

### 3.2 Button Component

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Primary variant renders | Screenshot | Brand-600 background |
| 2 | Secondary variant renders | Screenshot | Outline border |
| 3 | Ghost variant renders | Screenshot | Transparent background |
| 4 | Danger variant renders | Screenshot | Red-600 background |
| 5 | Loading state shows spinner | Screenshot | Spinner icon visible |
| 6 | Disabled state | `find` → check `disabled` attribute | Opacity 50%, no pointer events |
| 7 | Focus ring on tab | `computer(action: "key", text: "Tab")` | Blue ring visible |
| 8 | Hover state | `computer(action: "hover")` | Background darkens |

### 3.3 Input Component

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Label renders above | Screenshot | Label text visible |
| 2 | Error state | Screenshot | Red border, error message below |
| 3 | Icon prepended | Screenshot | Icon inside input left side |
| 4 | Focus ring | Click input | Brand ring appears |
| 5 | Dark mode | Toggle theme | Colors correct |

### 3.4 Dialog Component

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Opens with animation | Trigger dialog → screenshot | Modal visible with backdrop |
| 2 | Backdrop click closes | Click outside modal | Dialog closes |
| 3 | X button closes | Click X | Dialog closes |
| 4 | Focus trapped inside | Tab through elements | Focus stays within modal |
| 5 | Escape key closes | Press Escape | Dialog closes |

### 3.5 DataTable Component

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Renders with data | Screenshot | Table with rows visible |
| 2 | Sort column click | Click header | Sort indicator, data reorders |
| 3 | Checkbox selection | Click checkbox | Row highlighted, bulk bar appears |
| 4 | Loading state | Screenshot | Skeleton rows |
| 5 | Empty state | Screenshot | EmptyState component |

---

## 4. Phase 3: Dashboard Validation

### 4.1 Navigate to Dashboard

```
navigate(url: "http://localhost:3000/")
```

### 4.2 Stats Cards

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | 4 stat cards visible | `find(query: "stat cards")` | Documents, Vectors, Namespaces, Queries cards |
| 2 | Values populated from API | `read_network_requests(urlPattern: "status")` | GET /api/status called |
| 3 | Card hover effect | Hover on card → screenshot | Shadow elevation |
| 4 | Click Documents card | Click → check URL | Navigates to /documents |
| 5 | Loading skeleton | Throttle network → refresh | Skeleton shimmer visible |

### 4.3 Quick Actions

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Upload action card | `find(query: "Upload")` | Upload card visible |
| 2 | New Chat action card | `find(query: "New Chat")` | Chat card visible |
| 3 | Click New Chat | Click | Navigates to /chat |
| 4 | Click Upload | Click | Opens upload modal or navigates |

### 4.4 Recent Activity

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Activity list visible | `find(query: "Recent Activity")` | Section header found |
| 2 | Jobs data loaded | `read_network_requests(urlPattern: "jobs")` | GET /api/jobs called |
| 3 | Status icons correct | Screenshot | Correct icons per status |
| 4 | "View All" link | `find(query: "View All")` → click | Navigates to /jobs |

### 4.5 System Status

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Status widget visible | `find(query: "System Status")` | Section found |
| 2 | Health data loaded | `read_network_requests(urlPattern: "health")` | GET /health/detailed called |
| 3 | Green dots for healthy | Screenshot | Green pulsing dots |
| 4 | Red dots if service down | Stop Redis → refresh → screenshot | Red dot for Redis |

---

## 5. Phase 4: Documents Validation

### 5.1 Navigate

```
navigate(url: "http://localhost:3000/documents")
```

### 5.2 Namespace Sidebar

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Namespace tree visible | `find(query: "Namespaces")` | Sidebar with namespace list |
| 2 | "All" item shown | `find(query: "All")` | "All" with total count |
| 3 | Click namespace | Click a namespace | Documents filtered |
| 4 | Active namespace highlighted | Screenshot | Brand color background |

### 5.3 Upload Flow

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Upload button visible | `find(query: "Upload button")` | Button found |
| 2 | Click opens modal | Click Upload | Dialog opens |
| 3 | Drop zone visible | Screenshot | Dashed border zone |
| 4 | File picker works | Use `upload_image` or file input | File selected |
| 5 | Namespace selector | `find(query: "namespace selector")` | Dropdown available |
| 6 | Upload progress | Start upload → screenshot | Progress bar visible |
| 7 | Network request sent | `read_network_requests(urlPattern: "upload")` | POST /api/upload called |
| 8 | Success state | Wait for completion | Success message shown |

### 5.4 View Toggle

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | List/grid toggle | `find(query: "view toggle")` | Toggle buttons found |
| 2 | Click grid view | Click grid icon | Grid layout renders |
| 3 | Click list view | Click list icon | Table layout renders |

### 5.5 Document Preview

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Click document | Click row/card | Preview modal opens |
| 2 | Metadata shown | Screenshot | Filename, namespace, chunks, date |
| 3 | Content rendered | Screenshot | Markdown content visible |
| 4 | Close modal | Click X or backdrop | Modal closes |

---

## 6. Phase 5: Search Validation

### 6.1 Navigate

```
navigate(url: "http://localhost:3000/search")
```

### 6.2 Search Bar

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Large search input visible | `find(query: "search input")` | Prominent input centered |
| 2 | Placeholder text | Screenshot | "Search your documents..." |
| 3 | Type query | `form_input(value: "embeddings")` | Text appears in input |
| 4 | Press Enter | `computer(action: "key", text: "Return")` | Search executes |
| 5 | Loading spinner | Screenshot during search | Spinner visible |
| 6 | API called | `read_network_requests(urlPattern: "query")` | POST /api/query called |

### 6.3 Results

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Results appear | `find(query: "result cards")` | Result cards visible |
| 2 | Score badges colored | Screenshot | Green/blue/yellow/gray based on score |
| 3 | "Ask about this" button | `find(query: "Ask about this")` | Button on each result |
| 4 | Click "Ask about this" | Click | Navigates to /chat with context |
| 5 | Results count shown | `find(query: "results")` | "Found X results" text |

### 6.4 Filters

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Filter panel visible | `find(query: "Filters")` | Filter controls rendered |
| 2 | Change Top-K | Select different value | Number of results changes |
| 3 | Filter by namespace | Select namespace | Results filtered |
| 4 | Active filter chips | Screenshot | Chips shown below search |
| 5 | Clear all | Click "Clear all" | Filters reset |

### 6.5 URL State

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | URL updates after search | Check URL | `/search?q=embeddings&topk=5` |
| 2 | Navigate to URL with params | `navigate(url: "...?q=test&ns=work&topk=10")` | Search auto-executes |

### 6.6 Search History

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Clear input | Clear search field | History section appears |
| 2 | Previous searches shown | Screenshot | Recent search items visible |
| 3 | Click history item | Click | Search re-executes |

---

## 7. Phase 6: Chat Validation (Most Critical)

### 7.1 Navigate

```
navigate(url: "http://localhost:3000/chat")
```

### 7.2 Empty State

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Welcome message | `find(query: "Ask questions")` | Welcome text visible |
| 2 | Example prompts | `find(query: "example")` | Clickable suggestion chips |
| 3 | Namespace selector | `find(query: "namespace")` | Dropdown available |
| 4 | Provider selector | `find(query: "provider")` | Dropdown available |

### 7.3 Send Message

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Type message | `form_input` on textarea | Text appears |
| 2 | Select namespace | Select from dropdown | Namespace set |
| 3 | Click send / Enter | Click send button or press Enter | Message sent |
| 4 | User message appears | Screenshot | User bubble on right |
| 5 | "Thinking" indicator | Screenshot immediately | Loading/thinking state |
| 6 | SSE stream starts | `read_network_requests(urlPattern: "ask")` | POST /api/ask with stream:true |
| 7 | Streaming text appears | Screenshot during stream | Text appearing progressively |
| 8 | Cursor blinks | Screenshot | Blinking cursor at end |
| 9 | Stream completes | Wait → screenshot | Full response rendered |
| 10 | Sources shown | `find(query: "Sources")` | Source files listed |

### 7.4 Conversation Management

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Conversation appears in sidebar | `find(query: "conversation")` | New conversation listed |
| 2 | Click "New Chat" | Click button | New empty conversation |
| 3 | Switch conversations | Click different conversation | Messages change |
| 4 | Delete conversation | Right-click → Delete | Confirmation dialog → removed |

### 7.5 Message Actions

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Copy button on assistant msg | Hover on message → `find(query: "Copy")` | Copy button visible |
| 2 | Click copy | Click | Toast "Copied to clipboard" |
| 3 | Regenerate button | `find(query: "Regenerate")` | Button visible |
| 4 | Click regenerate | Click | New streaming response |

### 7.6 Context Panel

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Panel visible on desktop | Screenshot | Right panel with sources |
| 2 | Retrieved chunks listed | `find(query: "chunk")` | Source chunks visible |
| 3 | Score badges on chunks | Screenshot | Colored score indicators |
| 4 | Temperature slider | `find(query: "Temperature")` | Slider control |
| 5 | Collapse panel | Click toggle | Panel hides |

### 7.7 Keyboard Shortcuts

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Enter sends message | Type + Enter | Message sent |
| 2 | Shift+Enter newline | Shift+Enter in input | New line inserted |
| 3 | Escape stops streaming | Start stream → Escape | Stream aborted |
| 4 | Cmd+N new conversation | Keyboard shortcut | New conversation created |

### 7.8 Streaming Error Handling

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Backend error during stream | Stop backend → send message | Error toast shown |
| 2 | Network disconnect | Disconnect network → send | Error message in chat |
| 3 | Abort stream | Click Stop during stream | Stream stops cleanly |

---

## 8. Phase 7: Jobs Validation

### 8.1 Navigate

```
navigate(url: "http://localhost:3000/jobs")
```

### 8.2 Jobs Table

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Table renders | Screenshot | Jobs table with columns |
| 2 | API called | `read_network_requests(urlPattern: "jobs")` | GET /api/jobs called |
| 3 | Status badges correct | Screenshot | Colored badges per status |
| 4 | Progress bars | Screenshot | Progress bars on active jobs |
| 5 | Sort by column | Click column header | Data reorders |
| 6 | Auto-refresh | Wait 5s → check network | New GET /api/jobs request |

### 8.3 Filters

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Status filter | Select "Completed" | Only completed jobs shown |
| 2 | Time range filter | Select "Last 24h" | Filtered by time |
| 3 | Clear filters | Click clear | All jobs shown |

### 8.4 Job Detail

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Click job row | Click | Detail modal opens |
| 2 | Job info displayed | Screenshot | ID, status, dates, progress |
| 3 | Progress bar | Screenshot | Visual progress |
| 4 | Logs section | Screenshot | Log entries visible |
| 5 | Close modal | Click X | Modal closes |

### 8.5 Responsive

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Resize to mobile | `resize_window(width: 375, height: 812)` | Card view instead of table |
| 2 | Cards show all info | Screenshot | Status, name, progress visible |
| 3 | Reset to desktop | `resize_window(width: 1440, height: 900)` | Table view restored |

---

## 9. Phase 8: Settings Validation

### 9.1 Navigate

```
navigate(url: "http://localhost:3000/settings")
```

### 9.2 General Settings

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Settings sidebar visible | `find(query: "General")` | Category list |
| 2 | Backend URL input | `find(query: "Backend URL")` | Input with current URL |
| 3 | Test Connection button | `find(query: "Test")` → click | Status indicator updates |
| 4 | API called | `read_network_requests(urlPattern: "health")` | GET /health called |
| 5 | Save Changes button | `find(query: "Save")` | Button enabled after change |

### 9.3 LLM Providers

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Navigate to LLM section | Click "LLM Providers" | Provider cards visible |
| 2 | Provider status shown | Screenshot | Available/Not configured indicators |
| 3 | Click Edit provider | Click Edit | Modal opens with key input |
| 4 | API called | `read_network_requests(urlPattern: "providers")` | GET /api/providers called |

### 9.4 Appearance

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Theme radio buttons | `find(query: "theme")` | Light/Dark/System options |
| 2 | Click Dark | Click Dark option | Theme changes immediately |
| 3 | Click Light | Click Light option | Theme changes back |
| 4 | Font size controls | `find(query: "Font Size")` | Small/Medium/Large options |

### 9.5 Unsaved Changes

| # | Check | MCP Tool | Expected |
|---|-------|----------|----------|
| 1 | Change a setting | Modify Backend URL | Save button activates |
| 2 | Navigate away | Click nav link | Warning dialog appears |
| 3 | Cancel navigation | Click Cancel | Stay on settings |
| 4 | Confirm navigation | Click Leave | Navigate without saving |

---

## 10. Cross-Cutting Validations

### 10.1 Dark Mode (All Pages)

For EACH page (`/`, `/documents`, `/search`, `/chat`, `/jobs`, `/settings`):

```
1. navigate(url: "http://localhost:3000/{page}")
2. Enable dark mode via settings or toggle
3. computer(action: "screenshot")
4. Verify: No white backgrounds bleeding through
5. Verify: Text is readable (light on dark)
6. Verify: Borders use dark variants
7. Verify: Icons visible against dark bg
```

### 10.2 Responsive Design (All Pages)

For EACH page, test at 3 breakpoints:

```
Desktop:  resize_window(width: 1440, height: 900)  → screenshot
Tablet:   resize_window(width: 768, height: 1024)   → screenshot
Mobile:   resize_window(width: 375, height: 812)    → screenshot
```

Verify for each:

- No horizontal scrollbar
- No text overflow/clipping
- Touch targets ≥ 44px on mobile
- Navigation accessible
- Content readable

### 10.3 Console Error Check (All Pages)

For EACH page:

```
1. navigate to page
2. read_console_messages(onlyErrors: true)
3. Verify: No React errors, no undefined errors, no network errors
```

### 10.4 Network Request Verification

```
1. Navigate through all pages
2. read_network_requests() for each
3. Verify: All API calls use correct endpoints
4. Verify: No 404 or 500 responses
5. Verify: Request payloads match expected schemas
```

### 10.5 Accessibility Quick Check

For EACH page:

```
1. read_page(filter: "interactive") on each page
2. Verify: All buttons have accessible names
3. Verify: All inputs have labels
4. Verify: All images have alt text
5. Tab through page: verify focus order is logical
6. Verify: Focus rings visible on all interactive elements
```

### 10.6 Performance Check

```
1. Open browser DevTools (Performance tab)
2. Navigate to each page
3. Verify: First Contentful Paint < 1.5s
4. Verify: Largest Contentful Paint < 3s
5. Verify: No layout shifts after initial render
6. Verify: Smooth scrolling in chat messages
```

---

## 11. MCP Tool Reference

Quick reference for the MCP browser tools used in this validation plan:

| Tool | Usage | Purpose |
|------|-------|---------|
| `tabs_context_mcp` | First call in any session | Get tab IDs |
| `tabs_create_mcp` | Create new tab | Fresh testing tab |
| `navigate` | `navigate(tabId, url)` | Go to page |
| `computer` | `action: "screenshot"` | Capture visual state |
| `computer` | `action: "click", coordinate: [x, y]` | Click elements |
| `computer` | `action: "key", text: "Return"` | Press keyboard keys |
| `find` | `find(tabId, query: "...")` | Locate elements by description |
| `form_input` | `form_input(tabId, ref, value)` | Fill form fields |
| `read_page` | `read_page(tabId)` | Get accessibility tree |
| `read_console_messages` | `read_console_messages(tabId, onlyErrors: true)` | Check for JS errors |
| `read_network_requests` | `read_network_requests(tabId, urlPattern: "...")` | Verify API calls |
| `resize_window` | `resize_window(tabId, width, height)` | Test responsive design |
| `get_page_text` | `get_page_text(tabId)` | Extract rendered text |
| `javascript_tool` | `javascript_tool(tabId, action: "...")` | Run custom JS checks |

### MCP Validation Workflow Pattern

```
# Pattern for validating any page:

1. Navigate to page
   → mcp__Claude_in_Chrome__navigate(tabId, url)

2. Wait for load
   → mcp__Claude_in_Chrome__computer(tabId, action: "screenshot")

3. Check for errors
   → mcp__Claude_in_Chrome__read_console_messages(tabId, onlyErrors: true, pattern: "error")

4. Verify API calls
   → mcp__Claude_in_Chrome__read_network_requests(tabId, urlPattern: "api")

5. Find key elements
   → mcp__Claude_in_Chrome__find(tabId, query: "element description")

6. Interact
   → mcp__Claude_in_Chrome__computer(tabId, action: "click", coordinate: [...])

7. Verify result
   → mcp__Claude_in_Chrome__computer(tabId, action: "screenshot")

8. Test responsive
   → mcp__Claude_in_Chrome__resize_window(tabId, width: 375, height: 812)
   → mcp__Claude_in_Chrome__computer(tabId, action: "screenshot")

9. Test dark mode
   → Toggle theme
   → mcp__Claude_in_Chrome__computer(tabId, action: "screenshot")
```

---

## Validation Completion Criteria

A page is considered VALIDATED when:

- [ ] All check items pass for that page
- [ ] No console errors
- [ ] All API calls use correct endpoints and receive valid responses
- [ ] Desktop, tablet, and mobile layouts render correctly
- [ ] Dark mode renders correctly
- [ ] All interactive elements have proper hover/focus/active states
- [ ] Keyboard navigation works
- [ ] Loading and empty states render correctly
- [ ] Error states display properly

---

*Run this validation plan after each implementation phase to catch issues early.*
