<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter, type RouteLocationNormalizedLoaded } from 'vue-router'
import { ListChecks, Plus } from '@lucide/vue'
import type { LocalNote } from '@/db/schema'
import type { NotesView as View } from '@/notes'
import { useMediaQuery } from '@/composables/useMediaQuery'
import { dismissInstallHint, wantsInstallHint } from '@/pwa'
import { useSessionStore } from '@/stores/session'
import NotesView from '@/views/NotesView.vue'
import EditLabelsDialog from '@/components/labels/EditLabelsDialog.vue'
import NavDrawer from '@/components/shell/NavDrawer.vue'
import NoteComposer from '@/components/shell/NoteComposer.vue'
import NoteEditorDialog from '@/components/shell/NoteEditorDialog.vue'
import SelectionBar from '@/components/shell/SelectionBar.vue'
import TopBar from '@/components/shell/TopBar.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import { useSelectionStore } from '@/stores/selection'
import { useSyncStore } from '@/stores/sync'

// One shell for the notes, archive and trash routes and for /note/:id, which opens the editor
// over whichever list was showing.
const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const sync = useSyncStore()
const selection = useSelectionStore()
const wide = useMediaQuery('(min-width: 640px)')
const compact = computed(() => !wide.value)
const drawerOpen = ref(false)
const composer = ref<{ start: (type?: LocalNote['type']) => void } | null>(null)
const editLabels = ref(false)
const installHint = ref(wantsInstallHint())

function closeInstallHint(): void {
  dismissInstallHint()
  installHint.value = false
}
const topBar = ref<{ focusSearch: () => void } | null>(null)

// The list behind the editor: the last route that was not a note, so closing returns to it.
const background = shallowRef<RouteLocationNormalizedLoaded | null>(null)
watch(
  () => route.fullPath,
  () => {
    if (route.name !== 'note') background.value = { ...route }
  },
  { immediate: true },
)
const view = computed((): View => background.value?.meta.view ?? 'notes')
const labelId = computed(() =>
  view.value === 'label' ? String(background.value?.params.id ?? '') : undefined,
)
const query = computed(() =>
  view.value === 'search' ? String(background.value?.query.q ?? '') : '',
)
const listPath = computed(() => background.value?.fullPath ?? '/')
// A selection belongs to the list it was made in.
watch(listPath, () => selection.clear())
const editing = computed(() => route.name === 'note')
const composing = computed(() => view.value === 'notes' || view.value === 'label')

function newNote(type: LocalNote['type'] = 'text'): void {
  if (!sync.hasRoom()) return
  if (!compact.value && composing.value) {
    composer.value?.start(type)
    return
  }
  void router.push({
    path: '/note/new',
    query: {
      ...(labelId.value ? { label: labelId.value } : {}),
      ...(type === 'checklist' ? { type } : {}),
    },
  })
}

function typing(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
  )
}

// Keyboard shortcuts (SPEC 9): c for a new note, l for a new checklist, / for search.
function onKeydown(event: KeyboardEvent): void {
  if (
    event.defaultPrevented ||
    event.metaKey ||
    event.ctrlKey ||
    event.altKey ||
    typing(event.target)
  )
    return
  if (editing.value) return
  if (event.key === 'Escape' && selection.active) {
    event.preventDefault()
    selection.clear()
  } else if (event.key === 'c' || event.key === 'l') {
    event.preventDefault()
    newNote(event.key === 'l' ? 'checklist' : 'text')
  } else if (event.key === '/') {
    event.preventDefault()
    topBar.value?.focusSearch()
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <SelectionBar v-if="selection.active" :view="view" />
  <TopBar
    v-show="!selection.active"
    ref="topBar"
    :compact="compact"
    :drawer-open="drawerOpen"
    @menu="drawerOpen = !drawerOpen"
  />
  <NavDrawer
    v-model:open="drawerOpen"
    :compact="compact"
    :current="view"
    :label-id="labelId"
    @edit-labels="editLabels = true"
  />
  <main
    class="flex flex-col gap-8 px-3 pt-6 pb-28 transition-[margin] duration-200 ease-out motion-reduce:transition-none sm:px-6"
    :class="!compact && (drawerOpen ? 'ml-[280px]' : 'ml-[72px]')"
  >
    <UiNotice v-if="session.expired" tone="warning" class="mx-auto w-full max-w-[600px]">
      {{ $t('sync.signInAgain') }}
      <RouterLink to="/login" class="font-medium text-accent">{{ $t('login.submit') }}</RouterLink>
    </UiNotice>
    <UiNotice
      v-if="installHint"
      tone="info"
      class="mx-auto w-full max-w-[600px]"
      data-testid="install-hint"
    >
      <p>{{ $t('pwa.installHint') }}</p>
      <button
        type="button"
        class="mt-1 cursor-pointer font-medium text-accent"
        @click="closeInstallHint"
      >
        {{ $t('pwa.dismiss') }}
      </button>
    </UiNotice>
    <UiNotice
      v-if="sync.storageFull"
      tone="warning"
      class="mx-auto w-full max-w-[600px]"
      data-testid="storage-full"
    >
      {{ $t('storage.fullNotice') }}
      <RouterLink to="/settings/profile" class="font-medium text-accent">
        {{ $t('storage.details') }}
      </RouterLink>
    </UiNotice>
    <UiNotice v-if="sync.rejected > 0" tone="error" class="mx-auto w-full max-w-[600px]">
      {{ $t('sync.rejected', { count: sync.rejected }, sync.rejected) }}
    </UiNotice>
    <NoteComposer
      v-if="!compact && composing"
      :key="labelId"
      ref="composer"
      :label-ids="labelId ? [labelId] : undefined"
    />
    <NotesView :view="view" :label-id="labelId" :query="query" />
  </main>
  <!-- Phones have no composer bar, so a new list gets its own smaller button above the main one. -->
  <div
    v-if="compact && composing"
    class="fixed right-[max(16px,env(safe-area-inset-right))] bottom-[max(16px,env(safe-area-inset-bottom))] z-20 flex flex-col items-center gap-3"
  >
    <button
      type="button"
      class="grid size-11 cursor-pointer place-items-center border border-line bg-bg text-ink shadow-float active:bg-[color-mix(in_srgb,var(--ink)_6%,var(--bg))]"
      :aria-label="$t('composer.newList')"
      :title="$t('composer.newList')"
      data-testid="fab-list"
      @click="newNote('checklist')"
    >
      <ListChecks :size="20" />
    </button>
    <button
      type="button"
      class="grid size-14 cursor-pointer place-items-center bg-accent text-on-accent shadow-float active:bg-accent-hover"
      :aria-label="$t('composer.new')"
      data-testid="fab"
      @click="newNote()"
    >
      <Plus :size="24" />
    </button>
  </div>
  <NoteEditorDialog v-if="editing" :fallback="listPath" />
  <EditLabelsDialog v-model:open="editLabels" />
</template>
