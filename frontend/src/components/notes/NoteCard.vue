<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Archive, ArchiveRestore, Pin, PinOff, Trash2, Undo2 } from '@lucide/vue'
import type { LocalNote } from '@/db/schema'
import { updateNote } from '@/db/notes'
import { plainText } from '@/db/richtext'
import { noteBackground, noteLine } from '@/notes'
import { useNoteActions } from '@/composables/useNoteActions'
import { iconButton } from '@/components/ui/menu'
import ColorPicker from './ColorPicker.vue'
import NoteMenu from './NoteMenu.vue'
import RichTextView from './RichTextView'

const props = defineProps<{ note: LocalNote }>()

const router = useRouter()
const actions = useNoteActions()
const body = ref<HTMLElement | null>(null)
const clipped = ref(false)

const color = computed(() => props.note.color)
const trashed = computed(() => props.note.trashed_at !== null)
const empty = computed(() => !props.note.title && !plainText(props.note.content).trim())

// Long content is cut off with a fade (SPEC 9, Note card). Measured again whenever the card or
// its content changes size, since the first layout happens before the masonry width is known.
function measure(): void {
  clipped.value = !!body.value && body.value.scrollHeight > body.value.clientHeight + 1
}
const observer = new ResizeObserver(measure)
onMounted(() => {
  if (!body.value) return
  observer.observe(body.value)
  if (body.value.firstElementChild) observer.observe(body.value.firstElementChild)
})
onBeforeUnmount(() => observer.disconnect())

function open(): void {
  void router.push(`/note/${props.note.id}`)
}
</script>

<template>
  <article
    class="group relative flex flex-col border transition-[border-color] duration-150 hover:border-(--line-hover-card) focus-visible:border-ink focus-visible:outline-none"
    :style="{
      background: noteBackground(color),
      borderColor: noteLine(color),
      '--line-hover-card':
        color === 'default'
          ? 'var(--line-hover)'
          : `color-mix(in srgb, var(--ink) 30%, var(--note-${color}))`,
    }"
    tabindex="0"
    :aria-label="note.title || $t('note.untitled')"
    data-testid="note-card"
    :data-note-id="note.id"
    @click="open"
    @keydown.enter.self="open"
  >
    <div class="px-4 pt-3 pb-2">
      <p
        v-if="note.conflict_of"
        class="mb-2 inline-block border border-[color-mix(in_srgb,var(--warning)_45%,transparent)] px-1.5 text-meta text-warning"
        data-testid="card-conflict"
      >
        {{ $t('note.conflictCopy') }}
      </p>
      <h3
        v-if="note.title"
        class="pr-7 text-[15px] leading-snug font-semibold tracking-[-0.01em] break-words"
        data-testid="card-title"
      >
        {{ note.title }}
      </h3>
      <div
        ref="body"
        class="max-h-[22rem] overflow-hidden text-sm break-words"
        :class="[note.title && 'mt-1.5', clipped && 'mask-b-from-[calc(100%-48px)]']"
        data-testid="card-body"
      >
        <RichTextView :doc="note.content" />
      </div>
      <p v-if="empty" class="text-[22px] leading-snug text-faint">{{ $t('note.emptyCard') }}</p>
    </div>

    <button
      v-if="!trashed"
      type="button"
      :class="[
        iconButton,
        'absolute top-1.5 right-1.5 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 pointer-coarse:hidden',
        note.pinned && 'text-ink',
      ]"
      :aria-label="$t(note.pinned ? 'note.unpin' : 'note.pin')"
      :aria-pressed="note.pinned"
      :title="$t(note.pinned ? 'note.unpin' : 'note.pin')"
      @click.stop="actions.pin(note.id, !note.pinned)"
    >
      <PinOff v-if="note.pinned" :size="18" />
      <Pin v-else :size="18" />
    </button>

    <div
      class="flex items-center gap-0.5 px-1.5 pb-1.5 opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100 has-[[data-state=open]]:opacity-100 pointer-coarse:hidden"
      @click.stop
    >
      <template v-if="trashed">
        <button
          type="button"
          :class="iconButton"
          :aria-label="$t('note.restore')"
          :title="$t('note.restore')"
          @click="actions.restore(note.id)"
        >
          <Undo2 :size="18" />
        </button>
        <button
          type="button"
          :class="iconButton"
          :aria-label="$t('note.deleteForever')"
          :title="$t('note.deleteForever')"
          @click="actions.purge(note.id)"
        >
          <Trash2 :size="18" />
        </button>
      </template>
      <template v-else>
        <ColorPicker
          :model-value="color"
          @update:model-value="(value) => updateNote(note.id, { color: value })"
        />
        <button
          type="button"
          :class="iconButton"
          :aria-label="$t(note.archived ? 'note.unarchive' : 'note.archive')"
          :title="$t(note.archived ? 'note.unarchive' : 'note.archive')"
          data-testid="card-archive"
          @click="actions.archive(note.id, !note.archived)"
        >
          <ArchiveRestore v-if="note.archived" :size="18" />
          <Archive v-else :size="18" />
        </button>
        <NoteMenu :trashed="false" @trash="actions.trash(note.id)" @copy="actions.copy(note.id)" />
      </template>
    </div>
  </article>
</template>
