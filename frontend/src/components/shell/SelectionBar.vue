<script setup lang="ts">
import { computed, ref } from 'vue'
import { Archive, ArchiveRestore, Pin, PinOff, Tag, Trash2, Undo2, X } from '@lucide/vue'
import { db } from '@/db/schema'
import type { NotesView } from '@/notes'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { useNoteActions } from '@/composables/useNoteActions'
import { useSelectionStore } from '@/stores/selection'
import { iconButton } from '@/components/ui/menu'
import ColorPicker from '@/components/notes/ColorPicker.vue'
import LabelPicker from '@/components/labels/LabelPicker.vue'

/** Replaces the top bar while notes are selected (SPEC 9, Ordering and selection). */
const props = defineProps<{ view: NotesView }>()

const selection = useSelectionStore()
const actions = useNoteActions()
const picking = ref(false)

const notes = useLiveQuery(
  async () => (await db.notes.bulkGet(selection.ids)).filter((note) => note !== undefined),
  [],
  () => selection.ids.join(),
)
const allPinned = computed(() => notes.value.length > 0 && notes.value.every((n) => n.pinned))
const color = computed(() => {
  const colors = new Set(notes.value.map((note) => note.color))
  return colors.size === 1 ? [...colors][0]! : null
})
const archived = computed(() => props.view === 'archive')

// Actions that move the notes out of the current view end the selection.
async function finish(action: (ids: string[]) => Promise<unknown>): Promise<void> {
  const ids = [...selection.ids]
  selection.clear()
  await action(ids)
}
</script>

<template>
  <header
    class="sticky top-0 z-20 flex h-16 items-center gap-1 border-b border-line bg-bg pt-[env(safe-area-inset-top)] pr-3 pl-2 sm:pl-3"
    data-testid="selection-bar"
  >
    <button
      type="button"
      :class="iconButton"
      :aria-label="$t('selection.clear')"
      :title="$t('selection.clear')"
      @click="selection.clear()"
    >
      <X :size="20" />
    </button>
    <span
      class="ml-1 flex-1 truncate font-mono text-base font-semibold tabular-nums"
      data-testid="selection-count"
    >
      {{ $t('selection.count', { count: selection.ids.length }) }}
    </span>
    <template v-if="view === 'trash'">
      <button
        type="button"
        :class="iconButton"
        :aria-label="$t('note.restore')"
        :title="$t('note.restore')"
        @click="finish(actions.restoreMany)"
      >
        <Undo2 :size="18" />
      </button>
      <button
        type="button"
        :class="iconButton"
        :aria-label="$t('note.deleteForever')"
        :title="$t('note.deleteForever')"
        @click="actions.purgeMany([...selection.ids]).then((done) => done && selection.clear())"
      >
        <Trash2 :size="18" />
      </button>
    </template>
    <template v-else>
      <button
        type="button"
        :class="iconButton"
        :aria-label="$t(allPinned ? 'note.unpin' : 'note.pin')"
        :title="$t(allPinned ? 'note.unpin' : 'note.pin')"
        @click="finish((ids) => actions.updateMany(ids, { pinned: !allPinned }))"
      >
        <PinOff v-if="allPinned" :size="18" />
        <Pin v-else :size="18" />
      </button>
      <ColorPicker
        :model-value="color"
        side="bottom"
        @update:model-value="(value) => actions.updateMany([...selection.ids], { color: value })"
      />
      <LabelPicker v-model:open="picking" :note-ids="selection.ids">
        <button
          type="button"
          :class="iconButton"
          :aria-label="$t('selection.labels')"
          :title="$t('selection.labels')"
          @click="picking = !picking"
        >
          <Tag :size="18" />
        </button>
      </LabelPicker>
      <button
        type="button"
        :class="iconButton"
        :aria-label="$t(archived ? 'note.unarchive' : 'note.archive')"
        :title="$t(archived ? 'note.unarchive' : 'note.archive')"
        data-testid="selection-archive"
        @click="finish((ids) => actions.archiveMany(ids, !archived))"
      >
        <ArchiveRestore v-if="archived" :size="18" />
        <Archive v-else :size="18" />
      </button>
      <button
        type="button"
        :class="iconButton"
        :aria-label="$t('note.delete')"
        :title="$t('note.delete')"
        @click="finish(actions.trashMany)"
      >
        <Trash2 :size="18" />
      </button>
    </template>
  </header>
</template>
