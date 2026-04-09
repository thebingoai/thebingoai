import { ClipboardList, Code, MessageSquare, Layers, Sparkles } from 'lucide-vue-next'
import type { Component } from 'vue'

const SKILL_TYPE_ICONS: Record<string, Component> = {
  instruction: ClipboardList,
  code: Code,
  prompt: MessageSquare,
  hybrid: Layers,
}

export function getSkillTypeIcon(skillType: string): Component {
  return SKILL_TYPE_ICONS[skillType] || Sparkles
}
