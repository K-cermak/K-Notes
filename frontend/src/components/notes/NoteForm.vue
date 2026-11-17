<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { JSONContent } from '@tiptap/core'
import { Editor, EditorContent } from '@tiptap/vue-3'
import { Archive, ArchiveRestore, Pin, PinOff, Undo2 } from '@lucide/vue'
import { convertNote } from '@/db/checklist'
import { byName, setNoteLabel } from '@/db/labels'
import { createNote, isNoteEmpty, purgeNote, updateNote } from '@/db/notes'
import { emptyDoc } from '@/db/richtext'
import { db, type LocalNote, type RichDoc } from '@/db/schema'
import { noteExtensions } from '@/editor/extensions'
import { noteBackground, type NoteColor } from '@/notes'
import { useDebouncedSave } from '@/composables/useDebouncedSave'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { useNoteActions } from '@/composables/useNoteActions'
import { iconButton } from '@/components/ui/menu'
import ChecklistEditor from './ChecklistEditor.vue'
import ColorPicker from './ColorPicker.vue'
import FormatMenu from './FormatMenu.vue'
import NoteMenu from './NoteMenu.vue'
import LabelChips from '@/components/labels/LabelChips.vue'
import LabelPicker from '@/components/labels/LabelPicker.vue'

/**
 * Title, body and toolbar of a note, shared by the composer and the editor. With no noteId it is a
 * draft: the note is only created once something is typed, so opening and closing leaves nothing.
 */
const props = defineProps<{
  noteId: string | null
  autofocus?: 'title' | 'body'
  /** The kind of note a draft becomes. */
  type?: LocalNote['type']
  /** Labels a new note gets, as when it is written in a label's view. */
  labelIds?: string[]
}>()
const emit = defineEmits<{ close: [] }>()

const { t, d } = useI18n()
const router = useRouter()
const actions = useNoteActions()

const id = ref(props.noteId)
const note = useLiveQuery(() => (id.value ? db.notes.get(id.value) : undefined), undefined, id)
const labels = useLiveQuery(
  async () => {
    if (!id.value) return []
    const memberships = await db.noteLabels.where('note_id').equals(id.value).toArray()
    const found = await db.labels.bulkGet(memberships.map((m) => m.label_id))
    return found.filter((label) => label !== undefined).sort(byName)
  },
  [],
  id,
)
const picking = ref(false)

// The menu closes first and hands focus back to its button; the picker opens after that.
function pickLabels(): void {
  setTimeout(() => (picking.value = true))
}
const draft = ref<{ type: LocalNote['type']; color: NoteColor; pinned: boolean }>({
  type: props.type ?? 'text',
  color: 'default',
  pinned: false,
})
const title = ref('')
let focused = false

const noteType = computed(() => note.value?.type ?? draft.value.type)
const color = computed(() => note.value?.color ?? draft.value.color)
const pinned = computed(() => note.value?.pinned ?? draft.value.pinned)
const trashed = computed(() => note.value?.trashed_at != null)

// A stored empty note has no blocks at all; the editor needs one paragraph to put the cursor in,
// or block formatting has nothing to apply to.
function editorContent(doc: RichDoc): JSONContent {
  // The stored schema is a subset of Tiptap's JSON; only the null for absent parts differs.
  return (
    doc.content?.length ? doc : { type: 'doc', content: [{ type: 'paragraph' }] }
  ) as JSONContent
}

/**
 * The editor is created once the note's content is known, with that content, rather than filled in
 * afterwards: content set into an editor that is still being mounted could be lost, and the
 * first keystroke then replaced the note.
 */
const editor = shallowRef<Editor>()

function createEditor(content: JSONContent, editable: boolean): void {
  editor.value = new Editor({
    extensions: noteExtensions(t('note.body')),
    content,
    editable,
    // Tiptap would add a <style> element, which the Content Security Policy blocks; main.css has the rules.
    injectCSS: false,
    onUpdate: () => schedule(),
    onFocus: () => (focused = true),
    onBlur: () => {
      focused = false
      flush()
    },
    editorProps: { attributes: { 'aria-label': t('note.body'), 'data-testid': 'editor-body' } },
  })
  if (props.autofocus === 'body' && noteType.value === 'text') editor.value.commands.focus('end')
}

// What this form last wrote, so its own writes coming back through the live query are not
// mistaken for changes from another device.
let lastSaved = { title: '', content: '' }

// An existing note is read-only until it has loaded: saving before that would overwrite it with
// the empty form.
const loaded = ref(props.noteId === null)

// A checklist keeps its text in items; the hidden editor's content is not written then.
function bodyContent(): RichDoc {
  if (noteType.value === 'checklist') return emptyDoc()
  return (editor.value?.getJSON() ?? emptyDoc()) as RichDoc
}

async function write(): Promise<void> {
  if (!loaded.value) return
  const content = bodyContent()
  lastSaved = { title: title.value, content: JSON.stringify(content) }
  if (id.value) {
    await updateNote(
      id.value,
      noteType.value === 'checklist' ? { title: title.value } : { title: title.value, content },
    )
  } else if (title.value.trim() || (noteType.value === 'text' && editor.value?.getText().trim())) {
    await create(content)
  }
}

async function create(content: RichDoc): Promise<string> {
  const created = await createNote({ title: title.value, content, ...draft.value })
  for (const labelId of props.labelIds ?? []) await setNoteLabel(created, labelId, true)
  id.value = created
  return created
}

/** Labels and checklist items need a note to belong to, even before anything is typed. */
async function ensureNote(): Promise<string | null> {
  await queue
  return id.value ?? (await create(bodyContent()))
}

// Saves run one after another: leaving a field and closing the form both save, and two
// overlapping saves of a draft would each create the note.
let queue = Promise.resolve()
function save(): Promise<void> {
  queue = queue.then(write, write)
  return queue
}

const { schedule, flush, pending } = useDebouncedSave(save)

if (props.noteId === null) createEditor(editorContent(emptyDoc()), true)

// Loads the note into a new editor; after that, changes from other devices show up unless the user
// is typing here.
watch(
  note,
  (value) => {
    if (!value) return
    const content = JSON.stringify(value.content)
    const instance = editor.value
    if (!instance) {
      title.value = value.title
      lastSaved = { title: value.title, content }
      loaded.value = true
      createEditor(editorContent(value.content), value.trashed_at == null)
      return
    }
    instance.setEditable(value.trashed_at == null, false)
    if (pending() || focused) return
    if (value.title !== lastSaved.title) title.value = value.title
    if (content !== lastSaved.content && content !== JSON.stringify(instance.getJSON())) {
      instance.commands.setContent(editorContent(value.content), { emitUpdate: false })
      // setContent leaves the whole document selected, so the next keystroke would replace it.
      instance.commands.setTextSelection(0)
    }
    lastSaved = { title: value.title, content }
  },
  { immediate: true },
)

function setColor(value: NoteColor): void {
  if (id.value) void updateNote(id.value, { color: value })
  else draft.value.color = value
}

function togglePin(): void {
  if (id.value) void actions.pin(id.value, !pinned.value)
  else draft.value.pinned = !pinned.value
}

const checklist = ref<{ flush: () => Promise<void> } | null>(null)

/** Saves what is pending and discards the note if it is empty (SPEC 9, Editor). */
async function finish(): Promise<void> {
  flush()
  await save()
  await checklist.value?.flush()
  if (id.value && !trashed.value && (await isNoteEmpty(id.value))) await purgeNote(id.value)
}

async function convert(to: LocalNote['type']): Promise<void> {
  flush()
  await save()
  await checklist.value?.flush()
  if (id.value) await convertNote(id.value, to)
  else draft.value.type = to
}

async function run(action: (noteId: string) => Promise<unknown>): Promise<void> {
  await save()
  if (!id.value) return
  const noteId = id.value
  emit('close')
  await action(noteId)
}

const edited = computed(() => {
  const at = note.value?.updated_at
  if (!at) return ''
  const sameDay = new Date(at).toDateString() === new Date().toDateString()
  return t('note.edited', { time: d(new Date(at), sameDay ? 'time' : 'date') })
})

function onKeydown(event: KeyboardEvent): void {
  // Tiptap handles Escape in the body (and marks it handled) before the dialog sees it, so the
  // form closes itself. Escape in a menu or popover never gets here: those live in portals.
  if (event.key === 'Escape' || (event.key === 'Enter' && (event.metaKey || event.ctrlKey))) {
    event.preventDefault()
    emit('close')
  }
}

onBeforeUnmount(() => editor.value?.destroy())

defineExpose({ finish })
</script>

<template>
  <div
    class="flex min-h-0 flex-1 flex-col text-ink"
    :style="{ background: noteBackground(color) }"
    data-testid="note-form"
    @keydown="onKeydown"
  >
    <div class="min-h-0 flex-1 overflow-y-auto px-4 pt-3 pb-2">
      <div
        v-if="note?.conflict_of"
        class="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 border border-[color-mix(in_srgb,var(--warning)_35%,transparent)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] px-3 py-2 text-label"
        data-testid="conflict"
      >
        <span class="flex-1">{{ $t('note.conflictCopy') }}</span>
        <button
          type="button"
          class="cursor-pointer font-medium text-accent"
          @click="router.push(`/note/${note.conflict_of}`)"
        >
          {{ $t('note.openOriginal') }}
        </button>
        <button
          type="button"
          class="cursor-pointer font-medium text-accent"
          @click="updateNote(note.id, { conflict_of: null })"
        >
          {{ $t('note.dismissConflict') }}
        </button>
      </div>
      <div class="flex items-start gap-2">
        <input
          v-model="title"
          class="min-w-0 flex-1 bg-transparent py-1.5 text-base font-semibold tracking-[-0.01em] outline-none placeholder:text-faint"
          :placeholder="$t('note.title')"
          :aria-label="$t('note.title')"
          :readonly="trashed || !loaded"
          :autofocus="autofocus === 'title'"
          maxlength="1000"
          data-testid="editor-title"
          @input="schedule"
          @focus="focused = true"
          @blur="((focused = false), flush())"
        />
        <button
          v-if="!trashed"
          type="button"
          :class="[iconButton, '-mr-2', pinned && 'text-ink']"
          :aria-label="$t(pinned ? 'note.unpin' : 'note.pin')"
          :aria-pressed="pinned"
          :title="$t(pinned ? 'note.unpin' : 'note.pin')"
          @click="togglePin"
        >
          <PinOff v-if="pinned" :size="18" />
          <Pin v-else :size="18" />
        </button>
      </div>
      <!-- v-show: the editor keeps its instance while the note is a checklist. -->
      <EditorContent v-show="noteType === 'text'" :editor="editor" class="min-h-12 pb-2" />
      <ChecklistEditor
        v-if="noteType === 'checklist' && loaded"
        ref="checklist"
        :note-id="id"
        :readonly="trashed"
        :ensure-note="ensureNote"
        :autofocus="autofocus === 'body'"
      />
      <LabelChips v-if="id" :note-id="id" :labels="labels" :color="color" class="pt-1 pb-2" />
    </div>
    <div
      class="flex flex-wrap items-center gap-0.5 px-2 pt-1 pb-[max(8px,env(safe-area-inset-bottom))]"
    >
      <template v-if="trashed && note">
        <button
          type="button"
          :class="iconButton"
          :aria-label="$t('note.restore')"
          :title="$t('note.restore')"
          @click="run(actions.restore)"
        >
          <Undo2 :size="18" />
        </button>
      </template>
      <template v-else>
        <FormatMenu v-if="noteType === 'text'" :editor="editor" />
        <ColorPicker :model-value="color" @update:model-value="setColor" />
        <button
          type="button"
          :class="iconButton"
          :disabled="!note"
          :aria-label="$t(note?.archived ? 'note.unarchive' : 'note.archive')"
          :title="$t(note?.archived ? 'note.unarchive' : 'note.archive')"
          @click="run((noteId) => actions.archive(noteId, !note?.archived))"
        >
          <ArchiveRestore v-if="note?.archived" :size="18" />
          <Archive v-else :size="18" />
        </button>
      </template>
      <LabelPicker v-if="!trashed" v-model:open="picking" :note-id="id" :ensure-note="ensureNote">
        <NoteMenu
          :trashed="false"
          :checklist="noteType === 'checklist'"
          @convert="convert"
          @trash="run(actions.trash)"
          @copy="run(actions.copy)"
          @labels="pickLabels"
        />
      </LabelPicker>
      <NoteMenu
        v-else-if="note"
        :trashed="true"
        @restore="run(actions.restore)"
        @purge="note && actions.purge(note.id).then((done) => done && emit('close'))"
      />
      <span class="ml-auto px-2 font-mono text-meta text-muted tabular-nums" data-testid="edited">{{
        edited
      }}</span>
      <button
        type="button"
        class="h-9 cursor-pointer px-4 font-medium text-ink hover:bg-[color-mix(in_srgb,var(--ink)_6%,transparent)]"
        data-testid="close-note"
        @click="emit('close')"
      >
        {{ $t('common.close') }}
      </button>
    </div>
  </div>
</template>
