<script lang="ts">
export interface TreeNode {
  type: 'agent' | 'action' | 'result' | 'reasoning'
  label: string
  detail?: string
  status?: 'in-progress' | 'completed' | 'streaming'
  duration?: string
  timestamp?: string
  children: TreeNode[]
  count?: number
}
</script>

<script setup lang="ts">
const props = defineProps<{
  node: TreeNode
  isLast: boolean
  ancestors: boolean[]
}>()

// For children: append whether this node still has siblings below (→ show │ continuation)
const childAncestors = computed(() => [...props.ancestors, !props.isLast])

const detailExpanded = ref(false)

const agentDotClass = computed(() => {
  const label = props.node.label.toLowerCase()
  if (label.includes('orchestrator')) return 'bg-blue-500'
  if (label.includes('data')) return 'bg-purple-500'
  if (label.includes('rag')) return 'bg-green-500'
  return 'bg-gray-400'
})
</script>

<template>
  <div>
    <!-- Node row -->
    <div :class="node.type === 'reasoning' ? 'items-start' : 'items-center'" class="flex text-xs py-0.5 min-h-[18px]">
      <!-- Ancestor continuation lines -->
      <span
        v-for="(hasLine, i) in ancestors"
        :key="i"
        class="font-mono text-gray-300 select-none shrink-0 whitespace-pre"
      >{{ hasLine ? '│   ' : '    ' }}</span>

      <!-- Tree connector -->
      <span class="font-mono text-gray-300 select-none shrink-0 whitespace-pre">{{ isLast ? '└── ' : '├── ' }}</span>

      <!-- Node content -->
      <div class="flex items-center gap-1.5 flex-1 min-w-0">
        <!-- Agent: colored circle -->
        <span
          v-if="node.type === 'agent'"
          :class="agentDotClass"
          class="w-1.5 h-1.5 rounded-full shrink-0"
        />
        <!-- Action in-progress: amber pulsing dot -->
        <span
          v-else-if="node.status === 'in-progress'"
          class="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 animate-pulse"
        />
        <!-- Result: green checkmark -->
        <span
          v-else-if="node.type === 'result'"
          class="text-green-500 shrink-0 text-[10px] leading-none"
        >✓</span>
        <!-- Reasoning: small dot (pulsing amber when streaming, gray when done) -->
        <span
          v-else-if="node.type === 'reasoning'"
          :class="node.status === 'streaming' ? 'bg-amber-400 animate-pulse' : 'bg-gray-300'"
          class="w-1.5 h-1.5 rounded-full shrink-0"
        />
        <!-- Completed action: gray arrow -->
        <span v-else class="text-gray-400 shrink-0 text-[10px] leading-none">›</span>

        <!-- Label -->
        <span
          :class="[
            node.type === 'agent' ? 'font-medium text-gray-800' :
            node.type === 'reasoning' ? 'italic text-gray-600 whitespace-normal break-words' :
            'truncate text-gray-600'
          ]"
        >{{ node.label }}<span v-if="node.status === 'streaming'" class="inline-block w-[5px] h-[10px] bg-amber-400 ml-0.5 animate-blink align-baseline" /></span>

        <!-- Count badge for grouped actions -->
        <span
          v-if="node.count && node.count > 1"
          class="text-[9px] bg-gray-200/70 text-gray-500 px-1 py-px rounded-full ml-1 shrink-0"
        >&times;{{ node.count }}</span>

        <!-- Duration (inline, after label) -->
        <span
          v-if="node.duration"
          class="text-gray-400 font-mono text-[10px] shrink-0"
        >{{ node.duration }}</span>
      </div>

    </div>

    <!-- Detail line (formatted args) shown below the node row -->
    <div v-if="node.detail" class="flex text-[10px] text-gray-400 py-0.5 min-w-0">
      <span
        v-for="(hasLine, i) in ancestors"
        :key="'d'+i"
        class="font-mono text-gray-300 select-none shrink-0 whitespace-pre"
      >{{ hasLine ? '│   ' : '    ' }}</span>
      <span class="font-mono text-gray-300 select-none shrink-0 whitespace-pre">{{ isLast ? '    ' : '│   ' }}</span>
      <div class="min-w-0 overflow-hidden flex-1">
        <div class="prose-detail" :class="{ 'max-h-[3.5rem] overflow-hidden': !detailExpanded }">
          <UiMarkdownRenderer :content="node.detail" />
        </div>
        <button
          @click="detailExpanded = !detailExpanded"
          class="text-blue-400 hover:text-blue-500 mt-0.5 cursor-pointer"
        >{{ detailExpanded ? 'show less' : 'read more...' }}</button>
      </div>
    </div>

    <!-- Children (recursive) -->
    <ChatReasoningTreeNode
      v-for="(child, idx) in node.children"
      :key="idx"
      :node="child"
      :is-last="idx === node.children.length - 1"
      :ancestors="childAncestors"
    />
  </div>
</template>

<style>
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.animate-blink {
  animation: blink 1s step-end infinite;
}
.prose-detail .prose-chat {
  @apply text-[10px] text-gray-500 leading-tight;
}
.prose-detail .prose-chat h1,
.prose-detail .prose-chat h2,
.prose-detail .prose-chat h3,
.prose-detail .prose-chat h4 {
  @apply text-[10px] font-medium mt-1 mb-0.5 text-gray-500;
}
.prose-detail .prose-chat p {
  @apply mb-1 leading-tight;
}
.prose-detail .prose-chat ul,
.prose-detail .prose-chat ol {
  @apply ml-3 mb-1;
}
.prose-detail .prose-chat li {
  @apply mb-0;
}
.prose-detail .prose-chat code {
  @apply text-[9px] px-1 py-0;
}
.prose-detail .prose-chat pre {
  @apply p-2 mb-1 text-[9px];
}
.prose-detail .prose-chat blockquote {
  @apply my-1 pl-2;
}
.prose-detail .prose-chat strong {
  @apply text-gray-600;
}
</style>
