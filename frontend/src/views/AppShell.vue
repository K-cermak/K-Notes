<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus } from '@lucide/vue'
import type { NotesView as View } from '@/notes'
import { useMediaQuery } from '@/composables/useMediaQuery'
import { useSessionStore } from '@/stores/session'
import NotesView from '@/views/NotesView.vue'
import NavDrawer from '@/components/shell/NavDrawer.vue'
import NoteComposer from '@/components/shell/NoteComposer.vue'
import NoteEditorDialog from '@/components/shell/NoteEditorDialog.vue'
import TopBar from '@/components/shell/TopBar.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import { useSyncStore } from '@/stores/sync'

// One shell for the notes, archive and trash routes and for /note/:id, which opens the editor
// over whichever list was showing.
const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const sync = useSyncStore()
const wide = useMediaQuery('(min-width: 640px)')
const compact = computed(() => !wide.value)
const drawerOpen = ref(false)
const composer = ref<{ start: () => void } | null>(null)
const lastView = ref<View>('notes')

watch(
  () => route.meta.view,
  (view) => {
    if (view) lastView.value = view
  },
  { immediate: true },
)
const view = computed(() => route.meta.view ?? lastView.value)
const listPath = computed(() => ({ notes: '/', archive: '/archive', trash: '/trash' })[view.value])
const editing = computed(() => route.name === 'note')

function newNote(): void {
  if (compact.value || view.value !== 'notes') void router.push('/note/new')
  else composer.value?.start()
}

function typing(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
  )
}

// Keyboard shortcuts (SPEC 9): c for a new note; the others arrive with search and checklists.
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
  if (event.key === 'c') {
    event.preventDefault()
    newNote()
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <TopBar :compact="compact" :drawer-open="drawerOpen" @menu="drawerOpen = !drawerOpen" />
  <NavDrawer v-model:open="drawerOpen" :compact="compact" :current="view" />
  <main
    class="flex flex-col gap-8 px-3 pt-6 pb-28 transition-[margin] duration-200 ease-out motion-reduce:transition-none sm:px-6"
    :class="!compact && (drawerOpen ? 'ml-[280px]' : 'ml-[72px]')"
  >
    <UiNotice v-if="session.expired" tone="warning" class="mx-auto w-full max-w-[600px]">
      {{ $t('sync.signInAgain') }}
      <RouterLink to="/login" class="font-medium text-accent">{{ $t('login.submit') }}</RouterLink>
    </UiNotice>
    <UiNotice v-if="sync.rejected > 0" tone="error" class="mx-auto w-full max-w-[600px]">
      {{ $t('sync.rejected', { count: sync.rejected }, sync.rejected) }}
    </UiNotice>
    <NoteComposer v-if="!compact && view === 'notes'" ref="composer" />
    <NotesView :view="view" />
  </main>
  <button
    v-if="compact && view === 'notes'"
    type="button"
    class="fixed right-4 bottom-[max(16px,env(safe-area-inset-bottom))] z-20 grid size-14 cursor-pointer place-items-center bg-accent text-on-accent shadow-float active:bg-accent-hover"
    :aria-label="$t('composer.new')"
    data-testid="fab"
    @click="newNote"
  >
    <Plus :size="24" />
  </button>
  <NoteEditorDialog v-if="editing" :fallback="listPath" />
</template>
