# LLM-MD-CLI Web UI - Implementation Plan 01: Foundation (Layout & Navigation)

**Project**: LLM-MD-CLI Web UI
**Stack**: React 18 + TypeScript + Tailwind CSS 3 + Vite
**Backend**: FastAPI (RAG system for markdown indexing/querying)
**Status**: Foundation Layer
**Date**: 2025-02

---

## Overview

This document provides complete, production-ready implementations for the core layout shell and navigation components. These form the foundation of the LLM-MD-CLI Web UI, establishing a responsive, theme-aware application structure.

### Components to Implement

1. **ThemeProvider.tsx** - Global theme context and system preferences handling
2. **Layout.tsx** - Main application shell with responsive sidebar
3. **Sidebar.tsx** - Persistent navigation with collapse/expand
4. **Header.tsx** - Top navigation bar with search and theme toggle
5. **MobileNav.tsx** - Mobile-responsive drawer navigation

---

## Directory Structure

```
src/
├── components/
│   └── layout/
│       ├── ThemeProvider.tsx
│       ├── Layout.tsx
│       ├── Sidebar.tsx
│       ├── Header.tsx
│       └── MobileNav.tsx
├── stores/
│   └── settingsStore.ts
├── lib/
│   └── utils.ts
├── types/
│   └── index.ts
└── App.tsx
```

---

## 1. ThemeProvider.tsx

**Path**: `src/components/layout/ThemeProvider.tsx`

```typescript
import React, { createContext, useContext, useEffect, useState } from 'react';
import { useSettingsStore } from '@/stores/settingsStore';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
  theme: Theme;
  effectiveTheme: 'light' | 'dark';
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

interface ThemeProviderProps {
  children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const { theme: storedTheme, setTheme: setStoredTheme } = useSettingsStore();
  const [effectiveTheme, setEffectiveTheme] = useState<'light' | 'dark'>('light');

  // Handle system preference changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = () => {
      updateTheme(storedTheme);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [storedTheme]);

  // Update effective theme based on settings and system preference
  const updateTheme = (themeValue: Theme) => {
    let theme: 'light' | 'dark' = 'light';

    if (themeValue === 'system') {
      theme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
    } else {
      theme = themeValue as 'light' | 'dark';
    }

    setEffectiveTheme(theme);
    updateDOM(theme);
  };

  // Update DOM classes and attributes
  const updateDOM = (theme: 'light' | 'dark') => {
    const htmlElement = document.documentElement;

    if (theme === 'dark') {
      htmlElement.classList.add('dark');
    } else {
      htmlElement.classList.remove('dark');
    }

    // Store computed theme in data attribute for CSS queries if needed
    htmlElement.setAttribute('data-theme', theme);
  };

  // Initialize and update on mount
  useEffect(() => {
    updateTheme(storedTheme);
  }, [storedTheme]);

  const handleSetTheme = (newTheme: Theme) => {
    setStoredTheme(newTheme);
    updateTheme(newTheme);
  };

  return (
    <ThemeContext.Provider
      value={{
        theme: storedTheme,
        effectiveTheme,
        setTheme: handleSetTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};
```

---

## 2. Layout.tsx

**Path**: `src/components/layout/Layout.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useSettingsStore } from '@/stores/settingsStore';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { MobileNav } from './MobileNav';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children?: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { sidebarCollapsed } = useSettingsStore();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile breakpoint (768px = md breakpoint)
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);

    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close mobile nav on resize to desktop
  useEffect(() => {
    if (!isMobile) {
      setMobileNavOpen(false);
    }
  }, [isMobile]);

  const sidebarWidth = sidebarCollapsed ? 72 : 260;

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950">
      {/* Desktop Sidebar */}
      {!isMobile && <Sidebar />}

      {/* Mobile Navigation Drawer */}
      {isMobile && (
        <MobileNav
          isOpen={mobileNavOpen}
          onClose={() => setMobileNavOpen(false)}
        />
      )}

      {/* Main Content Area */}
      <div
        className={cn(
          'flex flex-1 flex-col overflow-hidden transition-[margin-left] duration-300 ease-in-out',
          !isMobile && (sidebarCollapsed ? 'ml-72' : 'ml-260')
        )}
        style={
          !isMobile
            ? {
                marginLeft: `${sidebarWidth}px`,
              }
            : undefined
        }
      >
        {/* Header with top navigation and search */}
        <Header onMobileMenuClick={() => setMobileNavOpen(true)} />

        {/* Page Content */}
        <main className="flex-1 overflow-auto">
          <div className="container max-w-full h-full">
            {children || <Outlet />}
          </div>
        </main>
      </div>
    </div>
  );
};
```

---

## 3. Sidebar.tsx

**Path**: `src/components/layout/Sidebar.tsx`

```typescript
import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Search,
  MessageSquare,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useSettingsStore } from '@/stores/settingsStore';
import { cn } from '@/lib/utils';

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    path: '/',
    icon: <LayoutDashboard className="w-5 h-5" />,
  },
  {
    label: 'Documents',
    path: '/documents',
    icon: <FileText className="w-5 h-5" />,
  },
  {
    label: 'Search',
    path: '/search',
    icon: <Search className="w-5 h-5" />,
  },
  {
    label: 'Chat',
    path: '/chat',
    icon: <MessageSquare className="w-5 h-5" />,
  },
  {
    label: 'Jobs',
    path: '/jobs',
    icon: <Activity className="w-5 h-5" />,
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: <Settings className="w-5 h-5" />,
  },
];

export const Sidebar: React.FC = () => {
  const { sidebarCollapsed, setSidebarCollapsed } = useSettingsStore();

  const sidebarWidth = sidebarCollapsed ? 72 : 260;

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-screen bg-white dark:bg-slate-900',
        'border-r border-slate-200 dark:border-slate-700',
        'flex flex-col transition-[width] duration-300 ease-in-out',
        'z-40'
      )}
      style={{ width: `${sidebarWidth}px` }}
    >
      {/* Logo Section */}
      <div
        className={cn(
          'flex items-center justify-center h-16 px-4',
          'border-b border-slate-200 dark:border-slate-700',
          'transition-all duration-300'
        )}
      >
        {!sidebarCollapsed && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">LM</span>
            </div>
            <span className="font-semibold text-slate-900 dark:text-white text-sm">
              LLM-MD-CLI
            </span>
          </div>
        )}
        {sidebarCollapsed && (
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">LM</span>
          </div>
        )}
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-2 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg',
                'transition-all duration-150 ease-out',
                'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
                'dark:focus:ring-offset-slate-900',
                isActive
                  ? 'bg-brand-50 dark:bg-brand-950 text-brand-600 dark:text-brand-400 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
              )
            }
            title={item.label}
          >
            <span
              className={cn(
                'flex-shrink-0',
                'transition-colors duration-150'
              )}
            >
              {item.icon}
            </span>
            {!sidebarCollapsed && (
              <span className="text-sm font-medium whitespace-nowrap">
                {item.label}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse Toggle Button */}
      <div
        className={cn(
          'h-16 px-3 py-4',
          'border-t border-slate-200 dark:border-slate-700',
          'flex items-center justify-center'
        )}
      >
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className={cn(
            'p-2 rounded-lg',
            'text-slate-600 dark:text-slate-400',
            'hover:bg-slate-100 dark:hover:bg-slate-800',
            'transition-all duration-150 ease-out',
            'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
            'dark:focus:ring-offset-slate-900'
          )}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <ChevronLeft className="w-5 h-5" />
          )}
        </button>
      </div>
    </aside>
  );
};
```

---

## 4. Header.tsx

**Path**: `src/components/layout/Header.tsx`

```typescript
import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, Search, Sun, Moon } from 'lucide-react';
import { useTheme } from './ThemeProvider';
import { cn } from '@/lib/utils';

interface HeaderProps {
  onMobileMenuClick?: () => void;
}

// Page titles for each route
const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/documents': 'Documents',
  '/search': 'Search',
  '/chat': 'Chat',
  '/jobs': 'Jobs',
  '/settings': 'Settings',
};

export const Header: React.FC<HeaderProps> = ({ onMobileMenuClick }) => {
  const location = useLocation();
  const { theme, setTheme, effectiveTheme } = useTheme();
  const [searchOpen, setSearchOpen] = useState(false);

  const pageTitle = pageTitles[location.pathname] || 'Page';

  const handleThemeToggle = () => {
    if (theme === 'system') {
      setTheme(effectiveTheme === 'dark' ? 'light' : 'dark');
    } else {
      setTheme(effectiveTheme === 'dark' ? 'light' : 'dark');
    }
  };

  const handleCommandPalette = () => {
    // Trigger command palette (Cmd+K / Ctrl+K)
    // Full implementation in Command Palette component
    setSearchOpen(true);
  };

  return (
    <header
      className={cn(
        'fixed top-0 right-0 left-0',
        'h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm',
        'border-b border-slate-200 dark:border-slate-700',
        'z-30',
        'md:left-72' // Offset by sidebar on desktop
      )}
    >
      <div className="h-full px-4 md:px-6 flex items-center justify-between">
        {/* Left: Mobile Menu & Page Title */}
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {/* Mobile Menu Button */}
          <button
            onClick={onMobileMenuClick}
            className={cn(
              'md:hidden p-2 rounded-lg',
              'text-slate-600 dark:text-slate-400',
              'hover:bg-slate-100 dark:hover:bg-slate-800',
              'transition-all duration-150 ease-out',
              'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
              'dark:focus:ring-offset-slate-900'
            )}
            aria-label="Open mobile menu"
          >
            <Menu className="w-6 h-6" />
          </button>

          {/* Page Title */}
          <h1 className="text-lg font-semibold text-slate-900 dark:text-white whitespace-nowrap">
            {pageTitle}
          </h1>
        </div>

        {/* Right: Search, Theme Toggle */}
        <div className="flex items-center gap-2 md:gap-4">
          {/* Global Search - Command Palette Trigger */}
          <button
            onClick={handleCommandPalette}
            className={cn(
              'hidden sm:flex items-center gap-2 px-3 py-2 rounded-lg',
              'bg-slate-100 dark:bg-slate-800',
              'text-slate-600 dark:text-slate-400 text-sm',
              'hover:bg-slate-200 dark:hover:bg-slate-700',
              'transition-all duration-150 ease-out',
              'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
              'dark:focus:ring-offset-slate-900'
            )}
            title="Global search (Cmd+K)"
          >
            <Search className="w-4 h-4" />
            <span className="hidden md:inline">Search...</span>
            <kbd className="hidden md:inline ml-auto text-xs px-2 py-1 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
              {/(Mac|iPhone|iPad|iPod)/i.test(navigator.userAgent) ? '⌘' : 'Ctrl'}
              K
            </kbd>
          </button>

          {/* Mobile Search Button */}
          <button
            onClick={handleCommandPalette}
            className={cn(
              'sm:hidden p-2 rounded-lg',
              'text-slate-600 dark:text-slate-400',
              'hover:bg-slate-100 dark:hover:bg-slate-800',
              'transition-all duration-150 ease-out',
              'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
              'dark:focus:ring-offset-slate-900'
            )}
            title="Search"
            aria-label="Search"
          >
            <Search className="w-5 h-5" />
          </button>

          {/* Theme Toggle Button */}
          <button
            onClick={handleThemeToggle}
            className={cn(
              'p-2 rounded-lg',
              'text-slate-600 dark:text-slate-400',
              'hover:bg-slate-100 dark:hover:bg-slate-800',
              'transition-all duration-150 ease-out',
              'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
              'dark:focus:ring-offset-slate-900'
            )}
            title={`Switch to ${effectiveTheme === 'dark' ? 'light' : 'dark'} mode`}
            aria-label={`Switch to ${effectiveTheme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {effectiveTheme === 'dark' ? (
              <Sun className="w-5 h-5" />
            ) : (
              <Moon className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
```

---

## 5. MobileNav.tsx

**Path**: `src/components/layout/MobileNav.tsx`

```typescript
import React, { Fragment } from 'react';
import { NavLink } from 'react-router-dom';
import { Dialog, Transition } from '@headlessui/react';
import {
  LayoutDashboard,
  FileText,
  Search,
  MessageSquare,
  Activity,
  Settings,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    path: '/',
    icon: <LayoutDashboard className="w-5 h-5" />,
  },
  {
    label: 'Documents',
    path: '/documents',
    icon: <FileText className="w-5 h-5" />,
  },
  {
    label: 'Search',
    path: '/search',
    icon: <Search className="w-5 h-5" />,
  },
  {
    label: 'Chat',
    path: '/chat',
    icon: <MessageSquare className="w-5 h-5" />,
  },
  {
    label: 'Jobs',
    path: '/jobs',
    icon: <Activity className="w-5 h-5" />,
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: <Settings className="w-5 h-5" />,
  },
];

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MobileNav: React.FC<MobileNavProps> = ({ isOpen, onClose }) => {
  return (
    <Transition show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50 md:hidden" onClose={onClose}>
        {/* Overlay Backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/25 backdrop-blur-sm" />
        </Transition.Child>

        {/* Content */}
        <div className="fixed inset-0 overflow-y-auto">
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="-translate-x-full"
            enterTo="translate-x-0"
            leave="ease-in duration-200"
            leaveFrom="translate-x-0"
            leaveTo="-translate-x-full"
          >
            <Dialog.Panel
              className={cn(
                'w-64 h-full bg-white dark:bg-slate-900',
                'border-r border-slate-200 dark:border-slate-700',
                'flex flex-col transition-transform duration-300'
              )}
            >
              {/* Header */}
              <div
                className={cn(
                  'flex items-center justify-between h-16 px-4',
                  'border-b border-slate-200 dark:border-slate-700'
                )}
              >
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-sm">LM</span>
                  </div>
                  <span className="font-semibold text-slate-900 dark:text-white">
                    LLM-MD-CLI
                  </span>
                </div>

                {/* Close Button */}
                <button
                  onClick={onClose}
                  className={cn(
                    'p-2 rounded-lg',
                    'text-slate-600 dark:text-slate-400',
                    'hover:bg-slate-100 dark:hover:bg-slate-800',
                    'transition-all duration-150 ease-out',
                    'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
                    'dark:focus:ring-offset-slate-900'
                  )}
                  aria-label="Close menu"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Navigation Links */}
              <nav className="flex-1 px-3 py-4 space-y-2">
                {navItems.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={onClose}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3 px-3 py-2.5 rounded-lg',
                        'transition-all duration-150 ease-out',
                        'focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none',
                        'dark:focus:ring-offset-slate-900',
                        isActive
                          ? 'bg-brand-50 dark:bg-brand-950 text-brand-600 dark:text-brand-400 font-semibold'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
                      )
                    }
                  >
                    <span className="flex-shrink-0">{item.icon}</span>
                    <span className="text-sm font-medium">{item.label}</span>
                  </NavLink>
                ))}
              </nav>

              {/* Footer */}
              <div
                className={cn(
                  'h-16 px-4 py-4',
                  'border-t border-slate-200 dark:border-slate-700',
                  'text-xs text-slate-500 dark:text-slate-400'
                )}
              >
                <p>v1.0.0</p>
              </div>
            </Dialog.Panel>
          </Transition.Child>
        </div>
      </Dialog>
    </Transition>
  );
};
```

---

## 6. Supporting Files

### settingsStore.ts

**Path**: `src/stores/settingsStore.ts`

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark' | 'system';

interface SettingsStore {
  // Theme
  theme: Theme;
  setTheme: (theme: Theme) => void;

  // Sidebar
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;

  // Command Palette
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      // Theme defaults to system
      theme: 'system',
      setTheme: (theme) => set({ theme }),

      // Sidebar expanded by default
      sidebarCollapsed: false,
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      // Command palette closed by default
      commandPaletteOpen: false,
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
    }),
    {
      name: 'llm-cli-settings',
      version: 1,
    }
  )
);
```

### utils.ts

**Path**: `src/lib/utils.ts`

```typescript
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with proper conflict resolution
 * @param inputs - Class values to merge
 * @returns Merged class string
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format a date to a readable string
 * @param date - Date to format
 * @returns Formatted date string
 */
export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

/**
 * Format a date and time to a readable string
 * @param date - Date to format
 * @returns Formatted date and time string
 */
export function formatDateTime(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

/**
 * Debounce a function
 * @param func - Function to debounce
 * @param wait - Wait time in milliseconds
 * @returns Debounced function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };

    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
```

### types/index.ts

**Path**: `src/types/index.ts`

```typescript
/**
 * Global type definitions for LLM-MD-CLI Web UI
 */

/**
 * API Response wrapper
 */
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

/**
 * Pagination metadata
 */
export interface PaginationMeta {
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/**
 * Paginated API response
 */
export interface PaginatedResponse<T = any> {
  success: boolean;
  data: T[];
  meta: PaginationMeta;
  error?: string;
}

/**
 * Document metadata
 */
export interface DocumentMetadata {
  id: string;
  title: string;
  filePath: string;
  fileSize: number;
  mimeType: string;
  createdAt: string;
  updatedAt: string;
  indexedAt?: string;
  wordCount: number;
}

/**
 * Search result
 */
export interface SearchResult {
  id: string;
  documentId: string;
  documentTitle: string;
  snippet: string;
  relevanceScore: number;
  highlightedSnippet?: string;
}

/**
 * Chat message
 */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: string[];
}

/**
 * Job status enum
 */
export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

/**
 * Background job
 */
export interface BackgroundJob {
  id: string;
  type: 'index' | 'delete' | 'export';
  status: JobStatus;
  progress: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  metadata?: Record<string, any>;
}
```

### App.tsx

**Path**: `src/App.tsx`

```typescript
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './components/layout/ThemeProvider';
import { Layout } from './components/layout/Layout';

// Import pages (to be created)
// import { Dashboard } from './pages/Dashboard';
// import { Documents } from './pages/Documents';
// import { Search } from './pages/Search';
// import { Chat } from './pages/Chat';
// import { Jobs } from './pages/Jobs';
// import { Settings } from './pages/Settings';

function App() {
  return (
    <ThemeProvider>
      <Router>
        <Routes>
          <Route element={<Layout />}>
            {/* Routes will be added here */}
            {/* <Route index element={<Dashboard />} />
            <Route path="documents" element={<Documents />} />
            <Route path="search" element={<Search />} />
            <Route path="chat" element={<Chat />} />
            <Route path="jobs" element={<Jobs />} />
            <Route path="settings" element={<Settings />} /> */}
          </Route>
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
```

---

## Design System Constants

### Tailwind Configuration Additions

Add these utilities to your `tailwind.config.ts` for custom spacing:

```typescript
export default {
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',  // Primary brand color
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#082f49',
          950: '#051e3e',
        },
      },
      spacing: {
        'sidebar': '260px',
        'sidebar-collapsed': '72px',
      },
    },
  },
};
```

### CSS Variables (Optional)

Add to `src/index.css` for CSS-in-JS compatibility:

```css
@layer base {
  :root {
    --color-brand-50: #f0f9ff;
    --color-brand-500: #0ea5e9;
    --color-brand-600: #0284c7;

    --sidebar-width: 260px;
    --sidebar-width-collapsed: 72px;
    --header-height: 64px;
  }

  .dark {
    color-scheme: dark;
  }
}
```

---

## Implementation Checklist

- [ ] Create `src/components/layout/` directory
- [ ] Implement `ThemeProvider.tsx` with context and system preference detection
- [ ] Implement `Layout.tsx` with responsive sidebar handling
- [ ] Implement `Sidebar.tsx` with navigation and collapse functionality
- [ ] Implement `Header.tsx` with search trigger and theme toggle
- [ ] Implement `MobileNav.tsx` with accessible drawer component
- [ ] Create `settingsStore.ts` with Zustand store
- [ ] Create `utils.ts` with `cn()` helper
- [ ] Create `types/index.ts` with global type definitions
- [ ] Update `App.tsx` to use `ThemeProvider` and `Layout`
- [ ] Install dependencies: `zustand`, `@headlessui/react`, `lucide-react`, `clsx`, `tailwind-merge`
- [ ] Test responsive behavior at mobile (< 768px), tablet, and desktop breakpoints
- [ ] Test theme switching and persistence
- [ ] Test sidebar collapse/expand animation
- [ ] Test keyboard navigation and focus management
- [ ] Test dark mode color contrast (WCAG AA minimum)

---

## Dependencies Required

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.1",
    "@headlessui/react": "^1.7.17",
    "lucide-react": "^0.294.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.1"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "@types/react": "^18.2.37",
    "@types/react-dom": "^18.2.15",
    "tailwindcss": "^3.4.0"
  }
}
```

---

## Next Steps

After implementing this foundation layer:

1. **Component Pages** - Implement Dashboard, Documents, Search, Chat, Jobs, Settings pages
2. **Command Palette** - Full implementation with fuzzy search and keybindings
3. **API Integration** - Connect to FastAPI backend for data fetching
4. **Error Handling** - Global error boundary and toast notifications
5. **Authentication** - Login/logout flow with protected routes
6. **Accessibility** - Full WCAG 2.1 AA compliance audit
7. **Performance** - Code splitting, lazy loading, and optimization

---

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile Safari 14+
- Chrome Mobile latest

---

## Notes

- All components use TypeScript for type safety
- Dark mode is system-aware and user-customizable
- Sidebar collapse state is persisted to localStorage
- Responsive design follows mobile-first approach
- All interactive elements have focus rings and hover states
- Animations use CSS transitions for smooth UX
- Icons from lucide-react for consistent styling
- Accessibility features: ARIA labels, semantic HTML, keyboard navigation

---

**Document Version**: 1.0
**Last Updated**: 2025-02
**Status**: Ready for Implementation
