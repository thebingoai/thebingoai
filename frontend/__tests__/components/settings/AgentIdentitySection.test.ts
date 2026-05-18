import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive, watch } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('reactive', reactive)
vi.stubGlobal('watch', watch)

import AgentIdentitySection from '~/components/settings/AgentIdentitySection.vue'

const baseProfile = {
  display_name: 'Bingo',
  pronouns: 'they/them',
  tagline: 'Your BI co-pilot',
  avatar_url: 'data:image/png;base64,STALE',
  default_model: '',
  temperature: 0.4,
  max_output_tokens: 4096,
  soul: '',
  user_profile: { address_as: '', pronouns: '', role: '', team: '', timezone: '', working_hours: '' },
  user_narrative: '',
  vocabulary: [],
  sensitivities: [],
  version: 1,
  published_version: 1,
  published_at: null,
  published_avatar_url: null,
  published_display_name: 'Bingo',
}

describe('AgentIdentitySection', () => {
  it('does not render the upload or restore controls', () => {
    const wrapper = mount(AgentIdentitySection, {
      props: { profile: baseProfile, isPublished: true, models: null },
    })
    expect(wrapper.find('input[type="file"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Replace avatar')
    expect(wrapper.text()).not.toContain('Restore default')
  })

  it('renders both theme-aware logos and ignores stored avatar_url', () => {
    const wrapper = mount(AgentIdentitySection, {
      props: { profile: baseProfile, isPublished: true, models: null },
    })
    const imgs = wrapper.findAll('img')
    // jsdom URL-encodes spaces in the `src` attribute when read via attributes().
    // Match either form so the test isn't sensitive to that serialization.
    const norm = (s: string | undefined) => (s ?? '').replace(/%20/g, ' ')
    const light = imgs.find(i => norm(i.attributes('src')) === '/logo/BINGO Logo Design_FA_Icon.png')
    const dark  = imgs.find(i => norm(i.attributes('src')) === '/logo/BINGO Logo Design_FA_Icon_W.png')
    expect(light).toBeTruthy()
    expect(dark).toBeTruthy()
    expect(light!.classes()).toContain('dark:hidden')
    expect(dark!.classes()).toContain('hidden')
    expect(dark!.classes()).toContain('dark:block')
    // Stale uploaded data_url must not appear anywhere
    expect(wrapper.html()).not.toContain('STALE')
  })

  it('does not declare an avatar-file emit', () => {
    const wrapper = mount(AgentIdentitySection, {
      props: { profile: baseProfile, isPublished: true, models: null },
    })
    expect((wrapper.vm as any).$options.emits ?? []).not.toContain('avatar-file')
  })
})
