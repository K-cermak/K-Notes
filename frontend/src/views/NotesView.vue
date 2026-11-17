<script setup lang="ts">
import { computed, provide } from 'vue'
import { Archive, Lightbulb, Search, Tag, Trash2 } from '@lucide/vue'
import { byName } from '@/db/labels'
import { byPosition } from '@/db/notes'
import { db, type LocalAttachment, type LocalChecklistItem, type LocalLabel } from '@/db/schema'
import { matches } from '@/db/search'
import { NOTE_ORDER, type NotesView } from '@/notes'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { useNoteActions } from '@/composables/useNoteActions'
import { useInstanceStore } from '@/stores/instance'
import { useSessionStore } from '@/stores/session'
import EmptyState from '@/components/EmptyState.vue'
import NoteSection from '@/components/notes/NoteSection.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const props = defineProps<{ view: NotesView; labelId?: string; query?: string }>()

const session = useSessionStore()
const instance = useInstanceStore()
const actions = useNoteActions()
const all = useLiveQuery(async () => (await db.notes.toArray()).sort(byPosition), [])
const labelRows = useLiveQuery(() => db.labels.toArray(), [])
const memberships = useLiveQuery(() => db.noteLabels.toArray(), [])
const items = useLiveQuery(async () => (await db.checklistItems.toArray()).sort(byPosition), [])
const attachments = useLiveQuery(async () => (await db.attachments.toArray()).sort(byPosition), [])

function byNote<T extends { note_id: string }>(rows: T[]): Map<string, T[]> {
  const result = new Map<string, T[]>()
  for (const row of rows) {
    const list = result.get(row.note_id)
    if (list) list.push(row)
    else result.set(row.note_id, [row])
  }
  return result
}
const itemsByNote = computed(() => byNote<LocalChecklistItem>(items.value))
const attachmentsByNote = computed(() => byNote<LocalAttachment>(attachments.value))

const labelsByNote = computed(() => {
  const byId = new Map(labelRows.value.map((label) => [label.id, label]))
  const result = new Map<string, LocalLabel[]>()
  for (const membership of memberships.value) {
    const label = byId.get(membership.label_id)
    if (!label) continue
    result.set(membership.note_id, [...(result.get(membership.note_id) ?? []), label])
  }
  for (const labels of result.values()) labels.sort(byName)
  return result
})

const layout = computed(() => session.user?.default_view ?? 'grid')
const live = computed(() => all.value.filter((note) => note.trashed_at === null))

/** Sections of the current view: [heading key, notes]; an empty heading key means no heading. */
const sections = computed((): [string, typeof all.value][] => {
  if (props.view === 'trash') return [['', all.value.filter((note) => note.trashed_at !== null)]]
  if (props.view === 'archive') return [['', live.value.filter((note) => note.archived)]]
  if (props.view === 'search') {
    // Results are split into active and archived; trashed notes never show up (SPEC 9).
    const found = props.query
      ? live.value.filter((note) => matches(note.searchText, props.query!))
      : []
    const active = found.filter((note) => !note.archived)
    const archived = found.filter((note) => note.archived)
    return [
      [archived.length ? 'notes.active' : '', active],
      ['notes.archived', archived],
    ]
  }
  const active = live.value.filter(
    (note) =>
      !note.archived &&
      (props.view !== 'label' ||
        labelsByNote.value.get(note.id)?.some((l) => l.id === props.labelId)),
  )
  const pinned = active.filter((note) => note.pinned)
  return [
    ['notes.pinned', pinned],
    [pinned.length ? 'notes.others' : '', active.filter((note) => !note.pinned)],
  ]
})
// Shift+click selects a range in the order the notes are shown, across sections.
provide(
  NOTE_ORDER,
  computed(() => sections.value.flatMap(([, notes]) => notes.map((note) => note.id))),
)
const visibleCount = computed(() =>
  sections.value.reduce((sum, [, notes]) => sum + notes.length, 0),
)
const retention = computed(() => instance.config?.trash_retention_days ?? 0)

const empty = computed(() => {
  if (props.view === 'search') {
    return { icon: Search, key: props.query ? 'empty.search' : 'empty.searchPrompt' }
  }
  return {
    notes: { icon: Lightbulb, key: 'empty.notes' },
    archive: { icon: Archive, key: 'empty.archive' },
    trash: { icon: Trash2, key: 'empty.trash' },
    label: { icon: Tag, key: 'empty.label' },
  }[props.view]
})
</script>

<template>
  <div class="flex flex-col gap-8">
    <div
      v-if="view === 'trash' && (retention > 0 || visibleCount > 0)"
      class="mx-auto flex w-full max-w-[600px] flex-col gap-3 sm:flex-row sm:items-center"
    >
      <UiNotice v-if="retention > 0" class="flex-1">
        {{ $t('trash.notice', { days: retention }, retention) }}
      </UiNotice>
      <UiButton
        v-if="visibleCount > 0"
        variant="danger"
        class="self-end sm:self-auto"
        @click="actions.emptyTrash()"
      >
        {{ $t('trash.empty') }}
      </UiButton>
    </div>
    <EmptyState v-if="visibleCount === 0" :icon="empty.icon" :text="$t(empty.key)" />
    <!-- Keyed by the view, so switching views lays out the new list rather than animating it in. -->
    <template v-for="([heading, notes], index) in sections" :key="`${view}:${labelId}:${index}`">
      <NoteSection
        v-if="notes.length > 0"
        :notes="notes"
        :layout="layout"
        :labels="labelsByNote"
        :items="itemsByNote"
        :attachments="attachmentsByNote"
        :sortable="view !== 'trash' && view !== 'search'"
        :animated="view !== 'search'"
        :heading="heading ? $t(heading) : undefined"
      />
    </template>
  </div>
</template>
