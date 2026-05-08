<template>
  <div :class="['home-screen', { 'is-sending': props.isSending }]">
    <div class="home-inner">

      <!-- ── Greeting + hero heading ──────────────────────── -->
      <div class="eyebrow home-hero-eyebrow" style="margin-bottom: 16px; letter-spacing: 0.12em;">
        {{ greeting }}, {{ firstName }}
      </div>

      <h1 class="home-hero-heading">
        What should we<br />
        <em class="home-hero-em">figure out</em> today?
      </h1>

      <p class="home-hero-sub">
        Ask anything about
        <span v-if="primaryConnection" class="font-mono text-[13px]">{{ primaryConnection }}</span>
        <span v-else>your connected data</span>
        — I'll pick the right tables, write the SQL, and draft a dashboard if the answer deserves one.
      </p>

      <!-- ── Hero composer ──────────────────────────────────── -->
      <div ref="composerWrapRef" class="home-composer-anim-wrap">
        <ChatComposer @send="handleSend" />
      </div>

      <!-- ── Try a saved skill ──────────────────────────────── -->
      <div class="home-section" style="margin-top: 44px;">
        <div class="home-section-header">
          <div class="eyebrow">Try a saved skill</div>
          <div class="home-section-rule" />
          <span class="home-section-count">
            {{ skills.length > 0 ? `${skills.length} in your library` : 'none yet' }}
          </span>
        </div>

        <!-- Skills grid -->
        <div v-if="skills.length > 0" class="home-skills-grid">
          <button
            v-for="skill in displaySkills"
            :key="skill.id"
            class="home-skill-card"
            @click="useSkill(skill)"
          >
            <div class="home-skill-icon">{{ skillGlyph(skill) }}</div>
            <div class="home-skill-title">{{ skill.name }}</div>
            <div class="home-skill-meta">
              <span class="font-mono">{{ skill.reference_count }} runs</span>
              <span class="home-skill-dot">·</span>
              <span>{{ skill.skill_type }}</span>
            </div>
          </button>
        </div>

        <!-- Empty state -->
        <div v-else class="home-skills-empty">
          <Sparkles class="h-5 w-5 text-[var(--ink-3)] mb-2" />
          <p>No saved skills yet — skills are created automatically as Bingo learns your patterns.</p>
          <NuxtLink to="/settings?tab=skills" class="home-skills-empty-link">Browse settings →</NuxtLink>
        </div>
      </div>

      <!-- ── Scheduled · running in background ─────────────── -->
      <div v-if="scheduledDashboards.length > 0" class="home-section" style="margin-top: 36px;">
        <div class="home-section-header">
          <div class="eyebrow">Scheduled · running in the background</div>
          <div class="home-section-rule" />
        </div>
        <div class="home-schedule-list">
          <div
            v-for="(dash, i) in scheduledDashboards"
            :key="dash.id"
            class="home-sched-row"
            :style="{ borderBottom: i < scheduledDashboards.length - 1 ? '1px solid var(--line)' : 'none' }"
          >
            <Activity class="h-3.5 w-3.5 text-[var(--ok)] flex-shrink-0" />
            <span class="home-sched-time font-mono">{{ dash.schedule?.cron_expression ?? '—' }}</span>
            <span class="home-sched-title">{{ dash.title }}</span>
            <span class="home-sched-next">next run scheduled</span>
            <ChevronRight class="h-3 w-3 text-[var(--ink-3)] flex-shrink-0" />
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { Activity, ChevronRight } from 'lucide-vue-next'
import ChatComposer from '~/components/chat/ChatComposer.vue'

const emit = defineEmits<{
  send: []
}>()

const chatStore = useChatStore()
const authStore = useAuthStore()
const api = useApi()

const props = defineProps<{ isSending?: boolean }>()

const composerWrapRef = ref<HTMLElement | null>(null)

// Calculates how far the composer must travel to reach the page bottom
const composerTransform = ref('translateY(100px)')
watch(() => props.isSending, (sending) => {
  if (sending && composerWrapRef.value) {
    const rect = composerWrapRef.value.getBoundingClientRect()
    const distance = window.innerHeight - rect.bottom - 16
    composerTransform.value = `translateY(${Math.max(distance, 80)}px)`
  }
})

// ── Data ────────────────────────────────────────────────────
interface SkillItem { id: string; name: string; description: string; skill_type: string; reference_count: number }
interface DashItem  { id: number; title: string; schedule?: { cron_expression?: string } | null }

const skills = ref<SkillItem[]>([])
const scheduledDashboards = ref<DashItem[]>([])
const primaryConnection = ref<string>('')

onMounted(async () => {
  // Load skills
  try {
    const res = await api.skills.list() as SkillItem[]
    skills.value = Array.isArray(res) ? res.filter((s: SkillItem) => s.is_active !== false) : []
  } catch { skills.value = [] }

  // Load connections (for subtitle)
  try {
    const conns = await api.connections.list() as any[]
    const first = Array.isArray(conns) ? conns[0] : (conns?.connections?.[0])
    if (first?.name) primaryConnection.value = first.name
  } catch {}

  // Load dashboards for scheduled section
  try {
    const res = await api.dashboards.list() as any
    const all: DashItem[] = Array.isArray(res) ? res : (res?.dashboards ?? [])
    scheduledDashboards.value = all.filter((d: any) => d.schedule_cron || d.schedule)
  } catch { scheduledDashboards.value = [] }
})

// ── Greeting ────────────────────────────────────────────────
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
})

const firstName = computed(() => {
  const email = authStore.user?.email ?? ''
  const local = email.split('@')[0] ?? ''
  return local.charAt(0).toUpperCase() + local.slice(1)
})

// ── Send handler ────────────────────────────────────────────
const handleSend = () => {
  emit('send')
}

// ── Skills ──────────────────────────────────────────────────
const displaySkills = computed(() => skills.value.slice(0, 6))

// Deterministic glyph per skill type / name
const GLYPHS = ['✦', '◈', '⬡', '✧', '◉', '⬥', '✺', '◇', '⊹', '✶']
const skillGlyph = (skill: SkillItem) => {
  const idx = Math.abs(skill.id.charCodeAt(0) + skill.id.charCodeAt(1)) % GLYPHS.length
  return GLYPHS[idx]
}

const useSkill = (skill: SkillItem) => {
  chatStore.inputText = skill.name
  nextTick(() => textareaRef.value?.focus())
}
</script>

<style scoped>
/* ── Outer scroll container ──────────────────────────────── */
.home-screen {
  flex: 1;
  overflow-y: auto;
  background: var(--paper-0);
}

.home-inner {
  max-width: 760px;
  width: 100%;
  margin: 0 auto;
  padding: 80px 40px 60px;
}

/* ── Hero heading ────────────────────────────────────────── */
.home-hero-heading {
  margin: 0;
  font-family: var(--font-display);
  font-size: 56px;
  line-height: 1.05;
  letter-spacing: -0.02em;
  color: var(--ink-0);
  font-weight: 500;
  font-variation-settings: 'opsz' 72;
}
.home-hero-em {
  font-style: italic;
  font-weight: 400;
  color: var(--ember);
}

.home-hero-sub {
  font-size: 16px;
  color: var(--ink-1);
  line-height: 1.6;
  max-width: 560px;
  margin-top: 18px;
  margin-bottom: 0;
}

/* ── Hero composer wrapper (for send animation) ── */
.home-composer-anim-wrap {
  /* ease-in = accelerates downward like a natural slide */
  transition: transform 0.5s ease-in;
}
/* ── Section header ──────────────────────────────────────── */
.home-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.home-section-rule {
  flex: 1;
  border-top: 1px dashed var(--line-2);
  height: 1px;
  align-self: center;
}
.home-section-count {
  font-size: 11px;
  color: var(--ink-2);
  flex-shrink: 0;
}

/* ── Skills grid ─────────────────────────────────────────── */
.home-skills-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.home-skill-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  background: var(--paper-0);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  min-height: 96px;
  text-align: left;
  font-family: var(--font-sans);
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.home-skill-card:hover {
  border-color: var(--line-2);
  background: var(--paper-1);
  box-shadow: var(--shadow-2);
}

.home-skill-icon {
  font-size: 22px;
  color: var(--ember);
  font-family: var(--font-display);
  margin-bottom: 8px;
  line-height: 1;
}

.home-skill-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
  color: var(--ink-0);
  margin-bottom: auto;
  flex: 1;
}

.home-skill-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 10.5px;
  color: var(--ink-2);
}
.home-skill-dot { color: var(--line-2); }

.home-skills-empty {
  border: 1px dashed var(--line);
  border-radius: 12px;
  padding: 28px;
  text-align: center;
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.6;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.home-skills-empty-link {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ember);
  text-decoration: none;
}
.home-skills-empty-link:hover { text-decoration: underline; }

/* ── Scheduled list ──────────────────────────────────────── */
.home-schedule-list {
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--paper-1);
}

.home-sched-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  font-size: 12.5px;
}

.home-sched-time {
  width: 96px;
  color: var(--ink-2);
  font-size: 11px;
  flex-shrink: 0;
}

.home-sched-title {
  flex: 1;
  font-weight: 500;
  color: var(--ink-0);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.home-sched-next {
  font-size: 11px;
  color: var(--ink-2);
  flex-shrink: 0;
}

/* ── Send-from-New-Task in-place animation ───────────────────
   Transitions are always declared so they fire the moment the
   .is-sending class changes the property values. */
.home-hero-eyebrow,
.home-hero-heading,
.home-hero-sub {
  transition: opacity 0.4s ease-out, transform 0.45s ease-out;
}
.home-composer-anim-wrap {
  /* ease-in = accelerates downward like a natural slide; no opacity — stays
     fully visible so it appears to physically travel to the ChatInputBar position */
  transition: transform 0.5s ease-in;
}
.home-section {
  transition: opacity 0.38s ease-out, transform 0.42s ease-out;
}

/* Values that trigger the transitions when .is-sending is applied */
.is-sending .home-hero-eyebrow,
.is-sending .home-hero-heading,
.is-sending .home-hero-sub {
  opacity: 0;
  transform: translateY(-36px);
}
.is-sending .home-composer-anim-wrap {
  transform: v-bind(composerTransform);
  /* opacity intentionally omitted — box stays visible as it slides to the bottom */
}
.is-sending .home-section {
  opacity: 0;
  transform: translateY(28px);
}
</style>
