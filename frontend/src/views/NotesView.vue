<script setup lang="ts">
import { computed } from 'vue'
import { Archive, Lightbulb, Trash2 } from '@lucide/vue'
import { byPosition } from '@/db/notes'
import { db } from '@/db/schema'
import type { NotesView } from '@/notes'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { useNoteActions } from '@/composables/useNoteActions'
import { useInstanceStore } from '@/stores/instance'
import { useSessionStore } from '@/stores/session'
import EmptyState from '@/components/EmptyState.vue'
import NoteSection from '@/components/notes/NoteSection.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const props = defineProps<{ view: NotesView }>()

const session = useSessionStore()
const instance = useInstanceStore()
const actions = useNoteActions()
const all = useLiveQuery(async () => (await db.notes.toArray()).sort(byPosition), [])

const layout = computed(() => session.user?.default_view ?? 'grid')
const visible = computed(() =>
  all.value.filter((note) => {
    if (props.view === 'trash') return note.trashed_at !== null
    if (note.trashed_at !== null) return false
    return props.view === 'archive' ? note.archived : !note.archived
  }),
)
const pinned = computed(() => (props.view === 'notes' ? visible.value.filter((n) => n.pinned) : []))
const others = computed(() =>
  props.view === 'notes' ? visible.value.filter((n) => !n.pinned) : visible.value,
)
const retention = computed(() => instance.config?.trash_retention_days ?? 0)

const empty = {
  notes: { icon: Lightbulb, key: 'empty.notes' },
  archive: { icon: Archive, key: 'empty.archive' },
  trash: { icon: Trash2, key: 'empty.trash' },
}
</script>

<template>
  <div class="flex flex-col gap-8">
    <div
      v-if="view === 'trash' && (retention > 0 || visible.length > 0)"
      class="mx-auto flex w-full max-w-[600px] flex-col gap-3 sm:flex-row sm:items-center"
    >
      <UiNotice v-if="retention > 0" class="flex-1">
        {{ $t('trash.notice', { days: retention }, retention) }}
      </UiNotice>
      <UiButton
        v-if="visible.length > 0"
        variant="danger"
        class="self-end sm:self-auto"
        @click="actions.emptyTrash()"
      >
        {{ $t('trash.empty') }}
      </UiButton>
    </div>
    <EmptyState v-if="visible.length === 0" :icon="empty[view].icon" :text="$t(empty[view].key)" />
    <NoteSection
      v-if="pinned.length > 0"
      :notes="pinned"
      :layout="layout"
      :heading="$t('notes.pinned')"
    />
    <NoteSection
      v-if="others.length > 0"
      :notes="others"
      :layout="layout"
      :heading="pinned.length > 0 ? $t('notes.others') : undefined"
    />
  </div>
</template>
