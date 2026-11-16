<script setup lang="ts">
import { ref } from 'vue'

import { Archive, Lightbulb, NotebookPen, Trash2 } from '@lucide/vue'
import branding from '@branding'
import type { NotesView } from '@/notes'

/**
 * Desktop: an icon rail that expands on hover or with the menu button. Phone: an overlay opened
 * with the menu button (SPEC 9, Layout).
 */
const props = defineProps<{ compact: boolean; current: NotesView }>()
const open = defineModel<boolean>('open', { required: true })

const hovered = ref(false)
let hoverTimer: ReturnType<typeof setTimeout> | null = null

const items = [
  { view: 'notes', to: '/', icon: Lightbulb },
  { view: 'archive', to: '/archive', icon: Archive },
  { view: 'trash', to: '/trash', icon: Trash2 },
] as const

// A short delay keeps the rail from flickering open when the pointer only passes over it.
function enter(): void {
  hoverTimer = setTimeout(() => (hovered.value = true), 150)
}
function leave(): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  hovered.value = false
}
function navigated(): void {
  if (props.compact) open.value = false
}
</script>

<template>
  <div
    v-if="compact && open"
    class="fixed inset-0 z-30 animate-fade bg-[color-mix(in_srgb,var(--ink)_28%,transparent)]"
    @click="open = false"
  />
  <nav
    :aria-label="$t('nav.label')"
    class="fixed bottom-0 left-0 z-30 flex flex-col overflow-hidden bg-bg py-2 transition-[width,transform] duration-200 ease-out motion-reduce:transition-none"
    :class="
      compact
        ? [
            'top-0 w-[280px] border-r border-line pt-[max(8px,env(safe-area-inset-top))]',
            open ? 'translate-x-0 shadow-float' : '-translate-x-full',
          ]
        : [
            'top-16',
            open || hovered ? 'w-[280px]' : 'w-[72px]',
            hovered && !open && 'border-r border-line shadow-float',
          ]
    "
    data-testid="drawer"
    @pointerenter="!compact && enter()"
    @pointerleave="!compact && leave()"
  >
    <div v-if="compact" class="mb-2 flex h-14 items-center gap-3 px-5">
      <span class="grid size-8 place-items-center bg-ink text-bg" aria-hidden="true">
        <NotebookPen :size="18" />
      </span>
      <span class="text-[17px] font-semibold tracking-[-0.02em]">{{ branding.name }}</span>
    </div>
    <RouterLink
      v-for="item in items"
      :key="item.view"
      :to="item.to"
      class="flex h-12 shrink-0 items-center gap-6 px-6 whitespace-nowrap transition-colors duration-150 hover:bg-[color-mix(in_srgb,var(--ink)_5%,var(--bg))]"
      :class="
        current === item.view
          ? 'bg-[color-mix(in_srgb,var(--ink)_8%,var(--bg))] font-medium text-ink'
          : 'text-muted'
      "
      :aria-current="current === item.view ? 'page' : undefined"
      @click="navigated"
    >
      <component :is="item.icon" :size="20" />
      <span
        class="transition-opacity duration-150"
        :class="!compact && !open && !hovered && 'opacity-0'"
      >
        {{ $t(`nav.${item.view}`) }}
      </span>
    </RouterLink>
  </nav>
</template>
