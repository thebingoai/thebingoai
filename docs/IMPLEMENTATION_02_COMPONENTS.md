# IMPLEMENTATION_02_COMPONENTS.md
## GLM-4.7 Comprehensive Component Implementation Plan
### LLM-MD-CLI Web UI — React 18 + TypeScript + Tailwind CSS 3

---

## Table of Contents
1. [Part A: Shared UI Components](#part-a-shared-ui-components)
2. [Part B: Custom Hooks](#part-b-custom-hooks)
3. [Part C: Constants](#part-c-constants)

---

# PART A: SHARED UI COMPONENTS

## 1. Button.tsx

**Location:** `src/components/ui/Button.tsx`

```typescript
import React, { ButtonHTMLAttributes, ReactNode } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95',
  {
    variants: {
      variant: {
        primary:
          'bg-brand-600 text-white hover:bg-brand-700 focus-visible:ring-brand-500 shadow-sm',
        secondary:
          'border border-gray-300 bg-white text-gray-900 hover:bg-gray-50 focus-visible:ring-gray-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white dark:hover:bg-gray-800',
        ghost:
          'text-gray-700 hover:bg-gray-100 focus-visible:ring-gray-500 dark:text-gray-300 dark:hover:bg-gray-800',
        danger:
          'bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500 shadow-sm',
      },
      size: {
        sm: 'h-8 px-3 text-sm gap-1.5',
        md: 'h-10 px-4 text-base gap-2',
        lg: 'h-12 px-6 text-lg gap-2.5',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      loading = false,
      icon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        className={cn(
          buttonVariants({ variant, size }),
          loading && 'cursor-wait',
          className
        )}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {size !== 'sm' && <span>{children}</span>}
          </>
        ) : (
          <>
            {icon && <span className="flex items-center justify-center">{icon}</span>}
            <span>{children}</span>
          </>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';

export { Button, buttonVariants };
export type { ButtonProps };
```

---

## 2. Input.tsx

**Location:** `src/components/ui/Input.tsx`

```typescript
import React, { InputHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: ReactNode;
  helperText?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, icon, helperText, type = 'text', ...props }, ref) => {
    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            {label}
            {props.required && <span className="text-red-500 ml-1">*</span>}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 flex items-center justify-center text-gray-500 dark:text-gray-400 pointer-events-none">
              {icon}
            </div>
          )}
          <input
            ref={ref}
            type={type}
            className={cn(
              'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 transition-colors duration-200 placeholder-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:border-transparent disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white dark:placeholder-gray-500 dark:focus-visible:ring-offset-gray-950',
              icon && 'pl-10',
              error && 'border-red-500 focus-visible:ring-red-500',
              className
            )}
            {...props}
          />
        </div>
        {error && <p className="text-sm text-red-500 font-medium">{error}</p>}
        {helperText && !error && (
          <p className="text-sm text-gray-500 dark:text-gray-400">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

export { Input };
export type { InputProps };
```

---

## 3. Select.tsx

**Location:** `src/components/ui/Select.tsx`

```typescript
import React, { Fragment, ReactNode } from 'react';
import { Listbox, Transition } from '@headlessui/react';
import { CheckIcon, ChevronUpDownIcon } from '@heroicons/react/20/solid';
import { cn } from '@/lib/utils';

interface SelectOption {
  value: string | number;
  label: string;
}

interface SelectProps {
  options: SelectOption[];
  value: string | number | (string | number)[];
  onChange: (value: string | number | (string | number)[]) => void;
  multiple?: boolean;
  placeholder?: string;
  label?: string;
  error?: string;
  disabled?: boolean;
  className?: string;
}

const Select = React.forwardRef<HTMLDivElement, SelectProps>(
  (
    {
      options,
      value,
      onChange,
      multiple = false,
      placeholder = 'Select...',
      label,
      error,
      disabled = false,
      className,
    },
    ref
  ) => {
    const selectedLabel = React.useMemo(() => {
      if (multiple && Array.isArray(value)) {
        if (value.length === 0) return placeholder;
        if (value.length === 1) {
          return options.find((opt) => opt.value === value[0])?.label || placeholder;
        }
        return `${value.length} selected`;
      }
      const selected = options.find((opt) => opt.value === value);
      return selected?.label || placeholder;
    }, [value, options, placeholder, multiple]);

    return (
      <div ref={ref} className="w-full space-y-1.5">
        {label && (
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            {label}
          </label>
        )}
        <Listbox
          value={value}
          onChange={onChange}
          multiple={multiple}
          disabled={disabled}
        >
          <div className="relative">
            <Listbox.Button
              className={cn(
                'relative w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-left text-gray-900 transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:border-transparent disabled:cursor-not-allowed disabled:bg-gray-50 dark:border-gray-600 dark:bg-gray-900 dark:text-white dark:focus-visible:ring-offset-gray-950',
                error && 'border-red-500 focus-visible:ring-red-500',
                className
              )}
            >
              <span className="block truncate text-sm">{selectedLabel}</span>
              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <ChevronUpDownIcon
                  className="h-5 w-5 text-gray-400"
                  aria-hidden="true"
                />
              </span>
            </Listbox.Button>

            <Transition
              as={Fragment}
              leave="transition ease-in duration-100"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <Listbox.Options className="absolute z-10 mt-1 w-full rounded-lg border border-gray-300 bg-white py-1 shadow-lg focus:outline-none dark:border-gray-600 dark:bg-gray-900">
                {options.length === 0 ? (
                  <div className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                    No options available
                  </div>
                ) : (
                  options.map((option) => (
                    <Listbox.Option
                      key={option.value}
                      className={({ active, selected }) =>
                        cn(
                          'relative cursor-pointer select-none py-2 pl-10 pr-4 transition-colors duration-100',
                          active
                            ? 'bg-brand-50 text-gray-900 dark:bg-gray-800 dark:text-white'
                            : 'text-gray-700 dark:text-gray-300',
                          selected && 'font-semibold'
                        )
                      }
                      value={option.value}
                    >
                      {({ selected }) => (
                        <>
                          <span
                            className={cn(
                              'block truncate',
                              selected ? 'font-medium' : 'font-normal'
                            )}
                          >
                            {option.label}
                          </span>
                          {selected ? (
                            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-brand-600">
                              <CheckIcon className="h-5 w-5" aria-hidden="true" />
                            </span>
                          ) : null}
                        </>
                      )}
                    </Listbox.Option>
                  ))
                )}
              </Listbox.Options>
            </Transition>
          </div>
        </Listbox>
        {error && <p className="text-sm text-red-500 font-medium">{error}</p>}
      </div>
    );
  }
);

Select.displayName = 'Select';

export { Select };
export type { SelectProps, SelectOption };
```

---

## 4. Dialog.tsx

**Location:** `src/components/ui/Dialog.tsx`

```typescript
import React, { Fragment, ReactNode } from 'react';
import { Dialog as HeadlessDialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  closeButton?: boolean;
}

const Dialog = React.forwardRef<HTMLDivElement, DialogProps>(
  (
    {
      open,
      onClose,
      title,
      description,
      children,
      actions,
      size = 'md',
      closeButton = true,
    },
    ref
  ) => {
    return (
      <Transition appear show={open} as={Fragment}>
        <HeadlessDialog as="div" ref={ref} onClose={onClose} className="relative z-50">
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-25 dark:bg-opacity-40" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-200"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-150"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <HeadlessDialog.Panel
                  className={cn(
                    'relative w-full transform rounded-lg bg-white p-6 shadow-xl transition-all dark:bg-gray-900',
                    size === 'sm' && 'max-w-sm',
                    size === 'md' && 'max-w-md',
                    size === 'lg' && 'max-w-lg'
                  )}
                >
                  {closeButton && (
                    <button
                      onClick={onClose}
                      className="absolute top-4 right-4 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  )}

                  {title && (
                    <HeadlessDialog.Title className="text-lg font-semibold text-gray-900 dark:text-white pr-8">
                      {title}
                    </HeadlessDialog.Title>
                  )}

                  {description && (
                    <HeadlessDialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                      {description}
                    </HeadlessDialog.Description>
                  )}

                  <div className={cn('mt-6', (title || description) && 'border-t border-gray-200 dark:border-gray-700 pt-4')}>
                    {children}
                  </div>

                  {actions && (
                    <div className="mt-6 flex justify-end gap-3 border-t border-gray-200 dark:border-gray-700 pt-4">
                      {actions}
                    </div>
                  )}
                </HeadlessDialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </HeadlessDialog>
      </Transition>
    );
  }
);

Dialog.displayName = 'Dialog';

export { Dialog };
export type { DialogProps };
```

---

## 5. Badge.tsx

**Location:** `src/components/ui/Badge.tsx`

```typescript
import React, { ReactNode } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full font-medium',
  {
    variants: {
      variant: {
        default: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
        success: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
        warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
        error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
        info: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      },
      size: {
        sm: 'px-2.5 py-0.5 text-xs',
        md: 'px-3 py-1 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
);

interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  children: ReactNode;
  dot?: boolean;
}

const Dot: React.FC<{ variant: string }> = ({ variant }) => {
  const colors: Record<string, string> = {
    default: 'bg-gray-500',
    success: 'bg-green-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-500',
    info: 'bg-blue-500',
  };

  return (
    <span
      className={cn(
        'h-2 w-2 rounded-full animate-pulse',
        colors[variant] || colors.default
      )}
    />
  );
};

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', children, dot = false, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(badgeVariants({ variant, size }), className)}
        {...props}
      >
        {dot && <Dot variant={variant || 'default'} />}
        <span>{children}</span>
      </div>
    );
  }
);

Badge.displayName = 'Badge';

export { Badge, badgeVariants };
export type { BadgeProps };
```

---

## 6. ProgressBar.tsx

**Location:** `src/components/ui/ProgressBar.tsx`

```typescript
import React from 'react';
import { cn } from '@/lib/utils';

interface ProgressBarProps {
  value: number;
  max?: number;
  animated?: boolean;
  size?: 'sm' | 'md';
  color?: 'brand' | 'green' | 'red' | 'yellow';
  showLabel?: boolean;
  className?: string;
}

const ProgressBar = React.forwardRef<HTMLDivElement, ProgressBarProps>(
  (
    {
      value,
      max = 100,
      animated = false,
      size = 'md',
      color = 'brand',
      showLabel = false,
      className,
    },
    ref
  ) => {
    const percentage = Math.min(Math.max(value / max, 0), 1) * 100;

    const sizeClasses = {
      sm: 'h-1',
      md: 'h-2',
    };

    const colorClasses = {
      brand: 'bg-brand-600',
      green: 'bg-green-600',
      red: 'bg-red-600',
      yellow: 'bg-yellow-500',
    };

    const bgColorClasses = {
      brand: 'bg-brand-100 dark:bg-brand-900',
      green: 'bg-green-100 dark:bg-green-900',
      red: 'bg-red-100 dark:bg-red-900',
      yellow: 'bg-yellow-100 dark:bg-yellow-900',
    };

    return (
      <div ref={ref} className={cn('w-full', className)}>
        <div
          className={cn(
            'w-full rounded-full overflow-hidden transition-all duration-300',
            sizeClasses[size],
            bgColorClasses[color]
          )}
        >
          <div
            className={cn(
              'h-full rounded-full transition-all duration-300',
              colorClasses[color],
              animated && 'relative overflow-hidden',
              animated && 'before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white before:to-transparent before:animate-shimmer'
            )}
            style={{
              width: `${percentage}%`,
            }}
          />
        </div>
        {showLabel && (
          <p className="mt-1 text-sm font-medium text-gray-700 dark:text-gray-300">
            {Math.round(percentage)}%
          </p>
        )}
      </div>
    );
  }
);

ProgressBar.displayName = 'ProgressBar';

export { ProgressBar };
export type { ProgressBarProps };
```

---

## 7. Skeleton.tsx

**Location:** `src/components/ui/Skeleton.tsx`

```typescript
import React from 'react';
import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  lines?: number;
}

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, variant = 'rectangular', width, height, lines = 1 }, ref) => {
    if (variant === 'text') {
      return (
        <div ref={ref} className="space-y-2">
          {Array.from({ length: lines }).map((_, i) => (
            <div
              key={i}
              className={cn(
                'h-4 rounded-md bg-gray-200 dark:bg-gray-700 animate-pulse',
                i === lines - 1 && 'w-3/4',
                className
              )}
            />
          ))}
        </div>
      );
    }

    if (variant === 'circular') {
      return (
        <div
          ref={ref}
          className={cn(
            'rounded-full bg-gray-200 dark:bg-gray-700 animate-pulse',
            className
          )}
          style={{
            width: width || 40,
            height: height || 40,
          }}
        />
      );
    }

    return (
      <div
        ref={ref}
        className={cn(
          'rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse',
          className
        )}
        style={{
          width: width || '100%',
          height: height || 200,
        }}
      />
    );
  }
);

Skeleton.displayName = 'Skeleton';

export { Skeleton };
export type { SkeletonProps };

// Preset compositions
export const SkeletonCard: React.FC<{ className?: string }> = ({ className }) => (
  <div className={cn('space-y-4 p-4', className)}>
    <Skeleton variant="rectangular" width="100%" height={200} />
    <div className="space-y-2">
      <Skeleton variant="text" width="60%" height={20} />
      <Skeleton variant="text" width="100%" lines={2} />
    </div>
  </div>
);

export const SkeletonTable: React.FC<{ rows?: number; className?: string }> = ({
  rows = 5,
  className,
}) => (
  <div className={cn('space-y-3', className)}>
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} variant="rectangular" width="100%" height={50} />
    ))}
  </div>
);

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({
  lines = 3,
  className,
}) => <Skeleton variant="text" lines={lines} className={className} />;
```

---

## 8. EmptyState.tsx

**Location:** `src/components/ui/EmptyState.tsx`

```typescript
import React, { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ icon, title, description, action, className }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'flex flex-col items-center justify-center py-12 px-4 text-center',
          className
        )}
      >
        {icon && (
          <div className="mb-4 flex justify-center">
            <div className="text-gray-400 dark:text-gray-600">
              {typeof icon === 'string' ? <span text-5xl>{icon}</span> : icon}
            </div>
          </div>
        )}

        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          {title}
        </h3>

        {description && (
          <p className="mt-2 text-gray-600 dark:text-gray-400 max-w-md">
            {description}
          </p>
        )}

        {action && <div className="mt-6">{action}</div>}
      </div>
    );
  }
);

EmptyState.displayName = 'EmptyState';

export { EmptyState };
export type { EmptyStateProps };
```

---

## 9. FileUpload.tsx

**Location:** `src/components/ui/FileUpload.tsx`

```typescript
import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { CloudArrowUpIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { Button } from './Button';

interface FileUploadProps {
  accept?: Record<string, string[]>;
  maxSize?: number;
  multiple?: boolean;
  onDrop: (files: File[]) => void;
  disabled?: boolean;
  className?: string;
}

const FileUpload = React.forwardRef<HTMLDivElement, FileUploadProps>(
  (
    {
      accept = { 'text/markdown': ['.md'] },
      maxSize = 50 * 1024 * 1024,
      multiple = true,
      onDrop,
      disabled = false,
      className,
    },
    ref
  ) => {
    const [files, setFiles] = useState<File[]>([]);
    const [error, setError] = useState<string>('');

    const handleDrop = useCallback(
      (acceptedFiles: File[], rejectedFiles: any[]) => {
        setError('');

        if (rejectedFiles.length > 0) {
          const reasons = rejectedFiles.map((f) => f.errors[0]?.message).join(', ');
          setError(`Some files were rejected: ${reasons}`);
          return;
        }

        if (!multiple && acceptedFiles.length > 1) {
          setError('Only one file is allowed');
          return;
        }

        const newFiles = multiple ? [...files, ...acceptedFiles] : acceptedFiles;
        setFiles(newFiles);
        onDrop(acceptedFiles);
      },
      [files, multiple, onDrop]
    );

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
      onDrop: handleDrop,
      accept,
      maxSize,
      disabled,
    });

    const removeFile = (index: number) => {
      setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    const formatFileSize = (bytes: number): string => {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    };

    return (
      <div ref={ref} className={cn('w-full space-y-4', className)}>
        <div
          {...getRootProps()}
          className={cn(
            'rounded-lg border-2 border-dashed transition-colors duration-200 p-8 text-center cursor-pointer',
            isDragActive
              ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
              : 'border-gray-300 bg-gray-50 hover:border-gray-400 dark:border-gray-600 dark:bg-gray-900/50 dark:hover:border-gray-500',
            disabled && 'cursor-not-allowed opacity-50'
          )}
        >
          <input {...getInputProps()} />
          <CloudArrowUpIcon className="h-8 w-8 mx-auto text-gray-400 dark:text-gray-500 mb-2" />
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {isDragActive ? 'Drop files here' : 'Drag and drop files here'}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            or click to select files (Max {formatFileSize(maxSize)})
          </p>
        </div>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        {files.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {files.length} file{files.length !== 1 ? 's' : ''} selected
            </p>
            <div className="space-y-1">
              {files.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                  <button
                    onClick={() => removeFile(index)}
                    className="ml-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }
);

FileUpload.displayName = 'FileUpload';

export { FileUpload };
export type { FileUploadProps };
```

---

## 10. DataTable.tsx

**Location:** `src/components/ui/DataTable.tsx`

```typescript
import React, { ReactNode, useState } from 'react';
import {
  ArrowUpDownIcon,
  ChevronUpIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { Skeleton } from './Skeleton';
import { EmptyState } from './EmptyState';

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => ReactNode;
  sortable?: boolean;
  width?: string;
}

export interface SortState {
  key: string;
  direction: 'asc' | 'desc';
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onSort?: (sortState: SortState) => void;
  sortState?: SortState;
  loading?: boolean;
  emptyMessage?: string;
  selectable?: boolean;
  selectedRows?: Set<string | number>;
  onSelectionChange?: (selectedRows: Set<string | number>) => void;
  onRowClick?: (item: T) => void;
  getRowKey: (item: T) => string | number;
  className?: string;
}

function DataTable<T>({
  columns,
  data,
  onSort,
  sortState,
  loading = false,
  emptyMessage = 'No data available',
  selectable = false,
  selectedRows = new Set(),
  onSelectionChange,
  onRowClick,
  getRowKey,
  className,
}: DataTableProps<T>) {
  const [localSelectedRows, setLocalSelectedRows] = useState<Set<string | number>>(
    selectedRows
  );

  const handleSelectAll = (checked: boolean) => {
    const newSelected = checked ? new Set(data.map(getRowKey)) : new Set();
    setLocalSelectedRows(newSelected);
    onSelectionChange?.(newSelected);
  };

  const handleSelectRow = (key: string | number, checked: boolean) => {
    const newSelected = new Set(localSelectedRows);
    if (checked) {
      newSelected.add(key);
    } else {
      newSelected.delete(key);
    }
    setLocalSelectedRows(newSelected);
    onSelectionChange?.(newSelected);
  };

  const handleSort = (columnKey: string) => {
    if (!onSort) return;

    let direction: 'asc' | 'desc' = 'asc';
    if (sortState?.key === columnKey && sortState.direction === 'asc') {
      direction = 'desc';
    }

    onSort({ key: columnKey, direction });
  };

  const renderSortIcon = (columnKey: string) => {
    if (!sortState || sortState.key !== columnKey) {
      return <ArrowUpDownIcon className="h-4 w-4 opacity-50" />;
    }
    return sortState.direction === 'asc' ? (
      <ChevronUpIcon className="h-4 w-4" />
    ) : (
      <ChevronDownIcon className="h-4 w-4" />
    );
  };

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} variant="rectangular" width="100%" height={50} />
        ))}
      </div>
    );
  }

  if (data.length === 0) {
    return <EmptyState title={emptyMessage} />;
  }

  return (
    <div className={cn('overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700', className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900">
            {selectable && (
              <th className="px-4 py-3 text-left w-12">
                <input
                  type="checkbox"
                  checked={
                    data.length > 0 && localSelectedRows.size === data.length
                  }
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="rounded border-gray-300 dark:border-gray-600"
                />
              </th>
            )}
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  'px-4 py-3 text-left font-semibold text-gray-900 dark:text-white',
                  column.width
                )}
                style={{ width: column.width }}
              >
                {column.sortable ? (
                  <button
                    onClick={() => handleSort(column.key)}
                    className="flex items-center gap-2 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                  >
                    {column.header}
                    {renderSortIcon(column.key)}
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((item, idx) => {
            const rowKey = getRowKey(item);
            const isSelected = localSelectedRows.has(rowKey);

            return (
              <tr
                key={rowKey}
                onClick={() => onRowClick?.(item)}
                className={cn(
                  'border-b border-gray-200 transition-colors duration-100 dark:border-gray-700',
                  isSelected
                    ? 'bg-brand-50 dark:bg-brand-900/20'
                    : 'bg-white hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900',
                  onRowClick && 'cursor-pointer'
                )}
              >
                {selectable && (
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => handleSelectRow(rowKey, e.target.checked)}
                      onClick={(e) => e.stopPropagation()}
                      className="rounded border-gray-300 dark:border-gray-600"
                    />
                  </td>
                )}
                {columns.map((column) => (
                  <td
                    key={`${rowKey}-${column.key}`}
                    className="px-4 py-3 text-gray-700 dark:text-gray-300"
                    style={{ width: column.width }}
                  >
                    {column.render ? column.render(item) : (item as any)[column.key]}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export { DataTable };
export type { DataTableProps };
```

---

## 11. Tooltip.tsx

**Location:** `src/components/ui/Tooltip.tsx`

```typescript
import React, { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface TooltipProps {
  content: string;
  children: ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
}

const positionClasses = {
  top: 'bottom-full mb-2 left-1/2 -translate-x-1/2 after:top-full after:left-1/2 after:-translate-x-1/2 after:border-l-transparent after:border-r-transparent after:border-b-transparent',
  bottom: 'top-full mt-2 left-1/2 -translate-x-1/2 after:bottom-full after:left-1/2 after:-translate-x-1/2 after:border-l-transparent after:border-r-transparent after:border-t-transparent',
  left: 'right-full mr-2 top-1/2 -translate-y-1/2 after:right-full after:top-1/2 after:-translate-y-1/2 after:border-t-transparent after:border-b-transparent after:border-r-transparent',
  right: 'left-full ml-2 top-1/2 -translate-y-1/2 after:left-full after:top-1/2 after:-translate-y-1/2 after:border-t-transparent after:border-b-transparent after:border-l-transparent',
};

const Tooltip = React.forwardRef<HTMLDivElement, TooltipProps>(
  ({ content, children, position = 'top', className }, ref) => {
    return (
      <div
        ref={ref}
        className="relative inline-block group"
      >
        {children}
        <div
          className={cn(
            'absolute hidden group-hover:block z-50 px-3 py-2 text-sm font-medium text-white bg-gray-900 dark:bg-gray-950 rounded-md whitespace-nowrap pointer-events-none after:absolute after:w-0 after:h-0 after:border-4 after:border-gray-900 dark:after:border-gray-950',
            positionClasses[position],
            className
          )}
        >
          {content}
        </div>
      </div>
    );
  }
);

Tooltip.displayName = 'Tooltip';

export { Tooltip };
export type { TooltipProps };
```

---

## 12. Dropdown.tsx

**Location:** `src/components/ui/Dropdown.tsx`

```typescript
import React, { Fragment, ReactNode } from 'react';
import { Menu, Transition } from '@headlessui/react';
import { cn } from '@/lib/utils';

interface DropdownItem {
  label: string;
  onClick: () => void;
  icon?: ReactNode;
  danger?: boolean;
  divider?: boolean;
}

interface DropdownProps {
  trigger: ReactNode;
  items: DropdownItem[];
  className?: string;
}

const Dropdown = React.forwardRef<HTMLDivElement, DropdownProps>(
  ({ trigger, items, className }, ref) => {
    return (
      <div ref={ref} className={cn('relative inline-block', className)}>
        <Menu as="div" className="relative inline-block text-left">
          <Menu.Button className="inline-flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded-md dark:focus-visible:ring-offset-gray-950">
            {trigger}
          </Menu.Button>

          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items className="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-gray-200 bg-white shadow-lg focus:outline-none dark:border-gray-700 dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
              {items.map((item, idx) => (
                <Menu.Item key={idx} disabled={item.divider}>
                  {item.divider ? (
                    <div className="h-0" />
                  ) : (
                    {({ active }) => (
                      <button
                        onClick={item.onClick}
                        className={cn(
                          'flex items-center gap-3 w-full px-4 py-2.5 text-sm transition-colors duration-100',
                          active
                            ? 'bg-gray-100 dark:bg-gray-800'
                            : 'hover:bg-gray-50 dark:hover:bg-gray-800',
                          item.danger
                            ? 'text-red-600 dark:text-red-400'
                            : 'text-gray-700 dark:text-gray-300'
                        )}
                      >
                        {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                        <span>{item.label}</span>
                      </button>
                    )
                  )}
                </Menu.Item>
              ))}
            </Menu.Items>
          </Transition>
        </Menu>
      </div>
    );
  }
);

Dropdown.displayName = 'Dropdown';

export { Dropdown };
export type { DropdownProps, DropdownItem };
```

---

## 13. MarkdownRenderer.tsx

**Location:** `src/components/ui/MarkdownRenderer.tsx`

```typescript
import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import {
  oneDark,
  oneLight,
} from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from '@/hooks/useTheme';
import { cn } from '@/lib/utils';
import { DocumentDuplicateIcon, CheckIcon } from '@heroicons/react/24/outline';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const MarkdownRenderer = React.forwardRef<HTMLDivElement, MarkdownRendererProps>(
  ({ content, className }, ref) => {
    const { isDark } = useTheme();
    const [copiedIndex, setCopiedIndex] = React.useState<number | null>(null);

    const handleCopy = (code: string, index: number) => {
      navigator.clipboard.writeText(code).then(() => {
        setCopiedIndex(index);
        setTimeout(() => setCopiedIndex(null), 2000);
      });
    };

    const theme = isDark ? oneDark : oneLight;

    return (
      <div
        ref={ref}
        className={cn(
          'prose dark:prose-invert prose-sm max-w-none',
          'prose-headings:text-gray-900 dark:prose-headings:text-white',
          'prose-p:text-gray-700 dark:prose-p:text-gray-300',
          'prose-a:text-brand-600 dark:prose-a:text-brand-400 prose-a:no-underline hover:prose-a:underline',
          'prose-strong:text-gray-900 dark:prose-strong:text-white',
          'prose-code:text-gray-900 dark:prose-code:text-white prose-code:bg-gray-100 dark:prose-code:bg-gray-800 prose-code:px-1.5 prose-code:rounded prose-code:text-sm',
          'prose-pre:bg-gray-950 dark:prose-pre:bg-gray-950 prose-pre:p-0 prose-pre:border prose-pre:border-gray-800',
          'prose-blockquote:border-brand-500 prose-blockquote:text-gray-700 dark:prose-blockquote:text-gray-300',
          'prose-hr:border-gray-300 dark:prose-hr:border-gray-700',
          className
        )}
      >
        <ReactMarkdown
          components={{
            code({ node, inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              const language = match ? match[1] : 'text';
              const code = String(children).replace(/\n$/, '');
              const codeIndex = Math.random();

              if (inline) {
                return (
                  <code
                    className={cn(
                      'text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-800 px-1.5 rounded text-sm',
                      className
                    )}
                    {...props}
                  >
                    {children}
                  </code>
                );
              }

              return (
                <div className="relative group mb-4">
                  <div className="absolute top-2 right-2 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                    <span className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded">
                      {language}
                    </span>
                    <button
                      onClick={() => handleCopy(code, copiedIndex as number)}
                      className="bg-gray-700 hover:bg-gray-600 text-white p-2 rounded transition-colors"
                    >
                      {copiedIndex === codeIndex ? (
                        <CheckIcon className="h-4 w-4" />
                      ) : (
                        <DocumentDuplicateIcon className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  <SyntaxHighlighter
                    style={theme}
                    language={language}
                    PreTag="pre"
                    className="rounded-lg !p-4 !m-0"
                  >
                    {code}
                  </SyntaxHighlighter>
                </div>
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  }
);

MarkdownRenderer.displayName = 'MarkdownRenderer';

export { MarkdownRenderer };
export type { MarkdownRendererProps };
```

---

# PART B: CUSTOM HOOKS

## 1. useStatus.ts

**Location:** `src/hooks/useStatus.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface StatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime: number;
}

export const useStatus = () => {
  return useQuery<StatusResponse>({
    queryKey: ['status'],
    queryFn: () => api.getStatus(),
    refetchInterval: 30000,
    staleTime: 10000,
  });
};
```

---

## 2. useDetailedHealth.ts

**Location:** `src/hooks/useDetailedHealth.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface HealthDetail {
  component: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  message?: string;
  lastCheck: number;
}

interface DetailedHealthResponse {
  overall: 'healthy' | 'degraded' | 'unhealthy';
  checks: HealthDetail[];
}

export const useDetailedHealth = () => {
  return useQuery<DetailedHealthResponse>({
    queryKey: ['health'],
    queryFn: () => api.getDetailedHealth(),
    refetchInterval: 30000,
    staleTime: 10000,
  });
};
```

---

## 3. useNamespaces.ts

**Location:** `src/hooks/useNamespaces.ts`

```typescript
import { useStatus } from './useStatus';

export interface NamespaceInfo {
  name: string;
  documentCount: number;
  indexSize: number;
  createdAt: number;
  lastUpdated: number;
}

export const useNamespaces = () => {
  const statusQuery = useStatus();

  const namespaces: NamespaceInfo[] = [];

  if (statusQuery.data?.namespaces) {
    return {
      ...statusQuery,
      data: statusQuery.data.namespaces as NamespaceInfo[],
    };
  }

  return {
    ...statusQuery,
    data: namespaces,
  };
};
```

---

## 4. useProviders.ts

**Location:** `src/hooks/useProviders.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export interface Provider {
  name: string;
  type: 'llm' | 'embedding' | 'reranker';
  status: 'available' | 'unavailable';
  config?: Record<string, any>;
}

export const useProviders = () => {
  return useQuery<Provider[]>({
    queryKey: ['providers'],
    queryFn: () => api.getProviders(),
    staleTime: 60000,
  });
};
```

---

## 5. useJobs.ts

**Location:** `src/hooks/useJobs.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export interface Job {
  id: string;
  namespace: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  type: 'index' | 'query' | 'upload';
  progress: number;
  createdAt: number;
  updatedAt: number;
  error?: string;
}

export const useJobs = (namespace: string, limit: number = 10) => {
  return useQuery<Job[]>({
    queryKey: ['jobs', namespace, limit],
    queryFn: () => api.getJobs(namespace, limit),
    refetchInterval: 5000,
    staleTime: 1000,
  });
};
```

---

## 6. useJob.ts

**Location:** `src/hooks/useJob.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Job } from './useJobs';

export const useJob = (jobId: string) => {
  return useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: () => api.getJob(jobId),
    refetchInterval: (data) => {
      if (data?.status === 'processing') {
        return 2000;
      }
      return false;
    },
    staleTime: 500,
  });
};
```

---

## 7. useSearch.ts

**Location:** `src/hooks/useSearch.ts`

```typescript
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useSearchStore } from '@/store/searchStore';

export interface SearchRequest {
  query: string;
  namespace: string;
  topK?: number;
  filters?: Record<string, any>;
}

export interface SearchResult {
  id: string;
  score: number;
  content: string;
  metadata: Record<string, any>;
}

export interface SearchResponse {
  results: SearchResult[];
  totalTime: number;
  totalHits: number;
}

export const useSearch = () => {
  const { setResults, setLoading, setError } = useSearchStore();

  return useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: (request) => api.query(request),
    onMutate: () => {
      setLoading(true);
      setError(null);
    },
    onSuccess: (data) => {
      setResults(data.results);
      setLoading(false);
    },
    onError: (error) => {
      setError(error.message);
      setLoading(false);
    },
  });
};
```

---

## 8. useUpload.ts

**Location:** `src/hooks/useUpload.ts`

```typescript
import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';

export interface UploadProgress {
  fileId: string;
  fileName: string;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  error?: string;
}

interface UploadItem {
  file: File;
  id: string;
}

export const useUpload = (namespace: string) => {
  const [queue, setQueue] = useState<UploadItem[]>([]);
  const [progress, setProgress] = useState<Record<string, UploadProgress>>({});

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadFile(namespace, file, (loaded, total) => {
      const fileId = file.name;
      setProgress((prev) => ({
        ...prev,
        [fileId]: {
          ...prev[fileId],
          progress: Math.round((loaded / total) * 100),
        },
      }));
    }),
  });

  const addFiles = useCallback(
    (files: File[]) => {
      const newItems = files.map((file) => ({
        file,
        id: Math.random().toString(36),
      }));

      setQueue((prev) => [...prev, ...newItems]);

      const newProgress = files.reduce(
        (acc, file) => ({
          ...acc,
          [file.name]: {
            fileId: file.name,
            fileName: file.name,
            progress: 0,
            status: 'pending' as const,
          },
        }),
        {}
      );

      setProgress((prev) => ({ ...prev, ...newProgress }));

      // Process queue
      processQueue(newItems);
    },
    []
  );

  const processQueue = useCallback((items: UploadItem[]) => {
    items.forEach(async (item) => {
      try {
        setProgress((prev) => ({
          ...prev,
          [item.file.name]: {
            ...prev[item.file.name],
            status: 'uploading',
          },
        }));

        await uploadMutation.mutateAsync(item.file);

        setProgress((prev) => ({
          ...prev,
          [item.file.name]: {
            ...prev[item.file.name],
            status: 'completed',
            progress: 100,
          },
        }));

        setQueue((prev) => prev.filter((q) => q.id !== item.id));
      } catch (error) {
        setProgress((prev) => ({
          ...prev,
          [item.file.name]: {
            ...prev[item.file.name],
            status: 'failed',
            error: error instanceof Error ? error.message : 'Upload failed',
          },
        }));
      }
    });
  }, [uploadMutation]);

  return {
    addFiles,
    queue,
    progress,
    isUploading: uploadMutation.isPending,
  };
};
```

---

## 9. useChat.ts

**Location:** `src/hooks/useChat.ts`

```typescript
import { useCallback, useRef, useState } from 'react';
import { useChatStore } from '@/store/chatStore';
import { api } from '@/lib/api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: number;
}

export const useChat = (sessionId: string) => {
  const { messages, addMessage, setLoading } = useChatStore();
  const abortControllerRef = useRef<AbortController | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      setError(null);
      setLoading(true);

      const userMessage: ChatMessage = {
        id: Math.random().toString(36),
        role: 'user',
        content,
        createdAt: Date.now(),
      };

      addMessage(userMessage);

      const assistantMessage: ChatMessage = {
        id: Math.random().toString(36),
        role: 'assistant',
        content: '',
        createdAt: Date.now(),
      };

      addMessage(assistantMessage);

      abortControllerRef.current = new AbortController();

      try {
        await api.streamChat(
          sessionId,
          content,
          (chunk) => {
            addMessage({
              ...assistantMessage,
              content: (messages.find((m) => m.id === assistantMessage.id)?.content || '') + chunk,
            });
          },
          abortControllerRef.current.signal
        );
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [sessionId, messages, addMessage, setLoading]
  );

  const stopMessage = useCallback(() => {
    abortControllerRef.current?.abort();
    setLoading(false);
  }, [setLoading]);

  return {
    messages,
    sendMessage,
    stopMessage,
    error,
  };
};
```

---

## 10. useKeyboard.ts

**Location:** `src/hooks/useKeyboard.ts`

```typescript
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearchStore } from '@/store/searchStore';
import { useChatStore } from '@/store/chatStore';

export const useKeyboard = () => {
  const navigate = useNavigate();
  const { setIsOpen: setSearchOpen } = useSearchStore();
  const { startNewChat } = useChatStore();

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform);
      const modifier = isMac ? event.metaKey : event.ctrlKey;

      // Cmd/Ctrl + K: Open search
      if (modifier && event.key === 'k') {
        event.preventDefault();
        setSearchOpen(true);
      }

      // Cmd/Ctrl + N: New chat
      if (modifier && event.key === 'n') {
        event.preventDefault();
        startNewChat();
        navigate('/chat');
      }

      // Escape: Close modals
      if (event.key === 'Escape') {
        setSearchOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate, setSearchOpen, startNewChat]);
};
```

---

## 11. useTheme.ts

**Location:** `src/hooks/useTheme.ts`

```typescript
import { useEffect, useMemo } from 'react';
import { useSettingsStore } from '@/store/settingsStore';

export const useTheme = () => {
  const { theme } = useSettingsStore();

  const isDark = useMemo(() => {
    if (theme === 'auto') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return theme === 'dark';
  }, [theme]);

  useEffect(() => {
    const html = document.documentElement;
    if (isDark) {
      html.classList.add('dark');
    } else {
      html.classList.remove('dark');
    }
  }, [isDark]);

  return {
    theme,
    isDark,
  };
};
```

---

# PART C: CONSTANTS

## src/constants/index.ts

```typescript
import {
  HomeIcon,
  MagnifyingGlassIcon,
  ChatBubbleLeftIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';

// Navigation items for sidebar
export const NAV_ITEMS = [
  {
    path: '/',
    label: 'Dashboard',
    icon: HomeIcon,
  },
  {
    path: '/search',
    label: 'Search',
    icon: MagnifyingGlassIcon,
  },
  {
    path: '/chat',
    label: 'Chat',
    icon: ChatBubbleLeftIcon,
  },
  {
    path: '/settings',
    label: 'Settings',
    icon: Cog6ToothIcon,
  },
];

// Similarity score thresholds
export const SCORE_THRESHOLDS = {
  excellent: 0.9,
  good: 0.7,
  fair: 0.5,
  poor: 0.3,
} as const;

// Default search parameters
export const DEFAULT_TOP_K = 5;
export const MAX_TOP_K = 50;
export const MIN_TOP_K = 1;

// File upload constraints
export const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
export const ACCEPTED_FILE_TYPES = {
  'text/markdown': ['.md'],
  'text/plain': ['.txt'],
} as const;

// Polling intervals (in milliseconds)
export const POLLING_INTERVALS = {
  status: 30000,
  health: 30000,
  jobs: 5000,
  activeJob: 2000,
  namespace: 10000,
} as const;

// Animation durations (in milliseconds)
export const ANIMATION_DURATION = {
  fast: 150,
  normal: 200,
  slow: 300,
  slower: 500,
} as const;

// HTTP timeouts (in milliseconds)
export const HTTP_TIMEOUT = {
  short: 5000,
  normal: 15000,
  long: 30000,
  upload: 120000,
} as const;

// Error messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network error. Please check your connection.',
  SERVER_ERROR: 'Server error. Please try again later.',
  FILE_TOO_LARGE: 'File is too large. Maximum size is 50MB.',
  INVALID_FILE_TYPE: 'Invalid file type. Only markdown files are accepted.',
  UPLOAD_FAILED: 'Upload failed. Please try again.',
  SEARCH_FAILED: 'Search failed. Please try again.',
  NO_RESULTS: 'No results found for your query.',
  NAMESPACE_NOT_FOUND: 'Namespace not found.',
  JOB_NOT_FOUND: 'Job not found.',
} as const;

// Success messages
export const SUCCESS_MESSAGES = {
  FILE_UPLOADED: 'File uploaded successfully.',
  NAMESPACE_CREATED: 'Namespace created successfully.',
  NAMESPACE_DELETED: 'Namespace deleted successfully.',
  SEARCH_COMPLETED: 'Search completed.',
  SETTINGS_SAVED: 'Settings saved successfully.',
} as const;

// Badge colors for status indicators
export const STATUS_COLORS = {
  healthy: 'success',
  degraded: 'warning',
  unhealthy: 'error',
  pending: 'info',
  processing: 'info',
  completed: 'success',
  failed: 'error',
} as const;

// Score color mapping for search results
export const SCORE_COLOR_MAP = {
  excellent: 'text-green-600 dark:text-green-400',
  good: 'text-blue-600 dark:text-blue-400',
  fair: 'text-yellow-600 dark:text-yellow-400',
  poor: 'text-red-600 dark:text-red-400',
} as const;

// Default settings
export const DEFAULT_SETTINGS = {
  theme: 'auto' as const,
  searchLimit: DEFAULT_TOP_K,
  autoRefresh: true,
  notifications: true,
  compactMode: false,
} as const;

// Feature flags
export const FEATURE_FLAGS = {
  ENABLE_CHAT: true,
  ENABLE_BATCH_OPERATIONS: true,
  ENABLE_EXPORT: true,
  ENABLE_ADVANCED_FILTERS: false,
  ENABLE_BETA_FEATURES: false,
} as const;

// Regular expressions for validation
export const VALIDATION_REGEX = {
  NAMESPACE_NAME: /^[a-zA-Z0-9_-]{1,64}$/,
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  URL: /^https?:\/\/.+/,
} as const;

// Pagination defaults
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100],
} as const;

// Cache durations (in milliseconds)
export const CACHE_DURATION = {
  SHORT: 1 * 60 * 1000, // 1 minute
  NORMAL: 5 * 60 * 1000, // 5 minutes
  LONG: 30 * 60 * 1000, // 30 minutes
  VERY_LONG: 60 * 60 * 1000, // 1 hour
} as const;
```

---

## Summary

This comprehensive implementation plan includes:

### Part A: 13 Production-Ready UI Components
1. **Button.tsx** - Variant-based button with loading states
2. **Input.tsx** - Form input with validation and icons
3. **Select.tsx** - Headless UI dropdown with multi-select
4. **Dialog.tsx** - Animated modal with Headless UI
5. **Badge.tsx** - Status indicators with optional dots
6. **ProgressBar.tsx** - Animated progress with color variants
7. **Skeleton.tsx** - Loading skeletons with presets
8. **EmptyState.tsx** - Centered empty state UI
9. **FileUpload.tsx** - Drag-and-drop file upload
10. **DataTable.tsx** - Generic sortable/selectable table
11. **Tooltip.tsx** - CSS-based tooltips
12. **Dropdown.tsx** - Headless UI menu component
13. **MarkdownRenderer.tsx** - Rich markdown with syntax highlighting

### Part B: 11 Custom Hooks
- **useStatus**, **useDetailedHealth**, **useNamespaces** - System health monitoring
- **useProviders** - Provider management
- **useJobs**, **useJob** - Job tracking and polling
- **useSearch** - Search mutation with store integration
- **useUpload** - Queue-based file upload with progress
- **useChat** - Streaming chat with abort control
- **useKeyboard** - Global keyboard shortcuts
- **useTheme** - Dark mode theme management

### Part C: Complete Constants File
- Navigation configuration
- Score thresholds and colors
- File upload constraints
- Polling and animation durations
- Error/success messages
- Status color mappings
- Feature flags and validation patterns

All code is **production-ready**, **fully typed with TypeScript**, and follows **React 18 + Tailwind CSS 3** best practices.

