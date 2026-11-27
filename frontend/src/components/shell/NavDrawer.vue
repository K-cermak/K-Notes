<script setup lang="ts">
import { computed, ref } from 'vue'

import { Archive, Lightbulb, Pencil, Tag, Trash2 } from '@lucide/vue'
import { byName } from '@/db/labels'
import { db } from '@/db/schema'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { useSyncStore } from '@/stores/sync'
import AppLogo from '@/components/AppLogo.vue'
import StorageUsage from '@/components/StorageUsage.vue'
import branding from '@branding'
import type { NotesView } from '@/notes'

/**
 * Desktop: an icon rail that expands on hover or with the menu button. Phone: an overlay opened
 * with the menu button (SPEC 9, Layout).
 */
const props = defineProps<{ compact: boolean; current: NotesView; labelId?: string }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ editLabels: [] }>()

const sync = useSyncStore()
const labels = useLiveQuery(async () => (await db.labels.toArray()).sort(byName), [])
const expanded = computed(() => props.compact || open.value || hovered.value)

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
const entry =
  'flex h-12 shrink-0 items-center gap-6 px-6 whitespace-nowrap transition-colors duration-150 hover:bg-[color-mix(in_srgb,var(--ink)_5%,var(--bg))]'
const activeEntry = 'bg-[color-mix(in_srgb,var(--ink)_8%,var(--bg))] font-medium text-ink'
const label = computed(() => [
  'min-w-0 transition-opacity duration-150',
  !expanded.value && 'opacity-0',
])

function navigated(): void {
  if (props.compact) open.value = false
}
</script>

<template>
  <Transition
    leave-active-class="transition-opacity duration-200 ease-out"
    leave-to-class="opacity-0"
  >
    <div
      v-if="compact && open"
      class="fixed inset-0 z-30 animate-fade bg-scrim"
      @click="open = false"
    />
  </Transition>
  <!-- Tailwind 4 moves elements with the translate property, not transform. -->
  <nav
    :aria-label="$t('nav.label')"
    class="fixed bottom-0 left-0 z-30 flex flex-col overflow-x-hidden overflow-y-auto bg-bg py-2 transition-[width,translate] duration-200 ease-out motion-reduce:transition-none"
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
      <AppLogo />
      <span class="text-[17px] font-semibold tracking-[-0.02em]">{{ branding.name }}</span>
    </div>
    <template v-for="item in items" :key="item.view">
      <RouterLink
        :to="item.to"
        :class="[entry, current === item.view && !labelId ? activeEntry : 'text-muted']"
        :aria-current="current === item.view ? 'page' : undefined"
        @click="navigated"
      >
        <component :is="item.icon" :size="20" />
        <span :class="label">{{ $t(`nav.${item.view}`) }}</span>
      </RouterLink>
      <template v-if="item.view === 'notes'">
        <RouterLink
          v-for="tag in labels"
          :key="tag.id"
          :to="`/label/${tag.id}`"
          :class="[entry, labelId === tag.id ? activeEntry : 'text-muted']"
          :aria-current="labelId === tag.id ? 'page' : undefined"
          @click="navigated"
        >
          <Tag :size="20" />
          <span :class="[label, 'truncate']">{{ tag.name }}</span>
        </RouterLink>
        <button
          type="button"
          :class="[entry, 'w-full cursor-pointer text-left text-muted']"
          data-testid="edit-labels-button"
          @click="(navigated(), emit('editLabels'))"
        >
          <Pencil :size="20" />
          <span :class="label">{{ $t('labels.edit') }}</span>
        </button>
      </template>
    </template>
    <!-- A fixed width keeps the text from wrapping while the rail animates open. -->
    <RouterLink
      v-if="sync.storage"
      to="/settings/storage"
      class="mt-auto flex w-[280px] shrink-0 flex-col gap-1 border-t border-line px-6 pt-4 pb-[max(12px,env(safe-area-inset-bottom))] text-label text-muted transition-[opacity,visibility] duration-150 hover:text-ink"
      :class="!expanded && 'invisible opacity-0'"
      data-testid="drawer-storage"
      @click="navigated"
    >
      <span>{{ $t('storage.title') }}</span>
      <StorageUsage :storage="sync.storage" />
    </RouterLink>
  </nav>
</template>
