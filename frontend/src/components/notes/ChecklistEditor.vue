<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { ChevronDown, Plus } from '@lucide/vue'
import {
  insertItems,
  noteItems,
  planItems,
  removeItem,
  updateItem,
  type ItemPatch,
  type NewItem,
} from '@/db/checklist'
import { byPosition } from '@/db/notes'
import { insertKeys } from '@/db/positions'
import type { LocalChecklistItem } from '@/db/schema'
import { useDebouncedSave } from '@/composables/useDebouncedSave'
import { useLiveQuery } from '@/composables/useLiveQuery'
import ChecklistItemRow from './ChecklistItemRow.vue'

/** The items of a checklist note in the editor (SPEC 9, Checklists). */
const props = defineProps<{
  noteId: string | null
  readonly: boolean
  /** Creates the note of a draft, so that its first item has a note to belong to. */
  ensureNote: () => Promise<string | null>
  autofocus?: boolean
}>()

type Row = InstanceType<typeof ChecklistItemRow>

const items = useLiveQuery(
  () => (props.noteId ? noteItems(props.noteId) : []),
  [],
  () => props.noteId,
)

/**
 * New items show up as soon as Enter is pressed, before they are written, so the next keystroke
 * already lands in the new row. They stay here until the database has them.
 */
const unwritten = new Map<string, LocalChecklistItem>()
/** Removed items disappear at once too, even before the database has them, or gets rid of them. */
const removed = new Set<string>()

function allItems(): LocalChecklistItem[] {
  return [...items.value, ...unwritten.values()]
    .filter((item) => !removed.has(item.id))
    .sort(byPosition)
}

// Local copies for the drag lists, which reorder them while dragging; refreshed from the database
// whenever no drag is under way.
const unchecked = ref<LocalChecklistItem[]>([])
const checked = ref<LocalChecklistItem[]>([])
let dragged: LocalChecklistItem[] | null = null
function refresh(): void {
  for (const item of items.value) unwritten.delete(item.id)
  if (dragged) return
  const all = allItems()
  unchecked.value = all.filter((item) => !item.checked)
  checked.value = all.filter((item) => item.checked)
}
watch(items, refresh, { immediate: true })
const showChecked = ref(true)

// Every write goes through one queue, so an edit never reaches the database before the item it
// edits. Typed text waits for the debounce like the note's title; other changes are queued at once.
let queue = Promise.resolve()
function enqueue(task: () => Promise<unknown>): Promise<void> {
  const run = async () => {
    await task()
  }
  queue = queue.then(run, run)
  return queue
}

const drafts = reactive(new Map<string, string>())
async function writeDrafts(): Promise<void> {
  const entries = [...drafts]
  drafts.clear()
  for (const [id, text] of entries) await updateItem(id, { text })
}
const { schedule, flush: flushTimer } = useDebouncedSave(() => enqueue(writeDrafts))

function takeDraft(id: string): { text?: string } {
  const text = drafts.get(id)
  drafts.delete(id)
  return text === undefined ? {} : { text }
}

const rows = new Map<string, Row>()
function track(id: string, row: unknown): void {
  if (row) rows.set(id, row as Row)
  else rows.delete(id)
}

const root = ref<HTMLElement | null>(null)

// Only while focus is still in the list: a user who has moved on to the title keeps it there.
async function focusItem(id: string, caret: 'start' | 'end'): Promise<void> {
  await nextTick()
  const active = document.activeElement
  if (active && active !== document.body && !root.value?.contains(active)) return
  rows.get(id)?.focus(caret)
}

/** Shows new items after the given one (or at the start) at once and queues their write. */
function insert(noteId: string, afterId: string | null, texts: string[], caret: 'start' | 'end') {
  const all = allItems()
  const index = afterId === null ? 0 : all.findIndex((item) => item.id === afterId) + 1
  const planned: NewItem[] = planItems(noteId, all, index, texts)
  const last = planned.at(-1)
  if (!last) return
  for (const item of planned) unwritten.set(item.id, { ...item, checked: false, serverSeq: 0 })
  refresh()
  void enqueue(async () => {
    // Items over the per-note limit are not written; they must not linger on screen either.
    const written = new Set(await insertItems(planned))
    for (const item of planned) if (!written.has(item.id)) unwritten.delete(item.id)
    refresh()
  })
  void focusItem(last.id, caret)
}

function onText(id: string, text: string): void {
  drafts.set(id, text)
  schedule()
}

function change(item: LocalChecklistItem, patch: ItemPatch): void {
  const fields = { ...patch, ...takeDraft(item.id) }
  void enqueue(() => updateItem(item.id, fields))
}

function onRemove(item: LocalChecklistItem): void {
  takeDraft(item.id)
  unwritten.delete(item.id)
  removed.add(item.id)
  refresh()
  void enqueue(async () => {
    await removeItem(item.id)
    removed.delete(item.id)
  })
}

function onRemoveBack(item: LocalChecklistItem, list: LocalChecklistItem[]): void {
  const index = list.findIndex((other) => other.id === item.id)
  const target = list[index - 1] ?? list[index + 1]
  onRemove(item)
  if (target) rows.get(target.id)?.focus('end')
}

function onSplit(
  item: LocalChecklistItem,
  first: string,
  rest: string[],
  caret: 'start' | 'end',
): void {
  onText(item.id, first)
  insert(item.note_id, item.id, rest, caret)
}

// "+ List item": typing there turns into a new item, and what was typed moves into it. A draft
// note is created first; lines finished with Enter meanwhile become items of their own.
const adding = ref('')
const addField = ref<HTMLInputElement | null>(null)
let creating = false
let enteredLines: string[] = []

async function onAddInput(): Promise<void> {
  if (creating || !adding.value) return
  creating = true
  const noteId = props.noteId ?? (await props.ensureNote())
  creating = false
  const lines = [...enteredLines, adding.value]
  enteredLines = []
  adding.value = ''
  if (noteId) insert(noteId, unchecked.value.at(-1)?.id ?? null, lines, 'end')
}

function onAddEnter(event: KeyboardEvent): void {
  if (event.isComposing) return
  event.preventDefault()
  if (!creating) return
  enteredLines.push(adding.value)
  adding.value = ''
}

async function onAddPaste(event: ClipboardEvent): Promise<void> {
  const pasted = event.clipboardData?.getData('text/plain') ?? ''
  if (!/[\r\n]/.test(pasted)) return
  event.preventDefault()
  const noteId = props.noteId ?? (await props.ensureNote())
  const lines = pasted.split(/\r?\n|\r/).filter((line) => line.trim())
  if (noteId) insert(noteId, unchecked.value.at(-1)?.id ?? null, lines, 'end')
}

function onDragStart(list: LocalChecklistItem[]): void {
  dragged = [...list]
}

// Moving an item writes its position alone, so a move merges with edits from other devices.
function onDragEnd(event: { oldIndex?: number; newIndex?: number }): void {
  const before = dragged
  dragged = null
  const { oldIndex, newIndex } = event
  const moved = oldIndex === undefined ? undefined : before?.[oldIndex]
  if (!before || !moved || newIndex === undefined || oldIndex === newIndex) {
    refresh()
    return
  }
  const others = before.filter((item) => item.id !== moved.id).map((item) => item.position)
  change(moved, { position: insertKeys(others, newIndex)[0]! })
}

onMounted(() => {
  if (props.autofocus) addField.value?.focus()
})

defineExpose({
  /** Writes everything pending now; the form calls it before it closes. */
  async flush(): Promise<void> {
    flushTimer()
    await enqueue(writeDrafts)
  },
})
</script>

<template>
  <div ref="root" class="-ml-2 flex flex-col pb-2" data-testid="checklist">
    <VueDraggable
      v-model="unchecked"
      handle=".drag-handle"
      :animation="150"
      :disabled="readonly"
      :force-fallback="true"
      ghost-class="opacity-30"
      @start="onDragStart(unchecked)"
      @end="onDragEnd"
    >
      <ChecklistItemRow
        v-for="item in unchecked"
        :key="item.id"
        :ref="(row) => track(item.id, row)"
        :item="item"
        :readonly="readonly"
        :dirty="drafts.has(item.id)"
        @text="(text) => onText(item.id, text)"
        @check="(value) => change(item, { checked: value })"
        @remove="onRemove(item)"
        @remove-back="onRemoveBack(item, unchecked)"
        @split="(first, rest, caret) => onSplit(item, first, rest, caret)"
      />
    </VueDraggable>
    <label
      v-if="!readonly"
      class="flex h-8 cursor-text items-center gap-1 border-y border-transparent focus-within:border-[color-mix(in_srgb,var(--ink)_14%,transparent)]"
    >
      <span class="w-5 shrink-0" />
      <span class="grid h-8 shrink-0 place-items-center px-0.5 text-muted">
        <Plus :size="18" />
      </span>
      <input
        ref="addField"
        v-model="adding"
        class="min-w-0 flex-1 bg-transparent py-1.5 outline-none placeholder:text-muted"
        :placeholder="$t('checklist.add')"
        :aria-label="$t('checklist.add')"
        data-testid="add-item"
        @input="onAddInput"
        @keydown.enter="onAddEnter"
        @paste="onAddPaste"
      />
    </label>
    <template v-if="checked.length > 0">
      <button
        type="button"
        class="ui-disclosure mt-2 ml-2 flex h-8 gap-2 border-t border-[color-mix(in_srgb,var(--ink)_10%,transparent)] pt-1"
        :aria-expanded="showChecked"
        data-testid="checked-toggle"
        @click="showChecked = !showChecked"
      >
        <ChevronDown class="ui-disclosure__icon" />
        {{ $t('checklist.checked', { count: checked.length }, checked.length) }}
      </button>
      <VueDraggable
        v-show="showChecked"
        v-model="checked"
        handle=".drag-handle"
        :animation="150"
        :disabled="readonly"
        :force-fallback="true"
        ghost-class="opacity-30"
        @start="onDragStart(checked)"
        @end="onDragEnd"
      >
        <ChecklistItemRow
          v-for="item in checked"
          :key="item.id"
          :ref="(row) => track(item.id, row)"
          :item="item"
          :readonly="readonly"
          :dirty="drafts.has(item.id)"
          @text="(text) => onText(item.id, text)"
          @check="(value) => change(item, { checked: value })"
          @remove="onRemove(item)"
          @remove-back="onRemoveBack(item, checked)"
          @split="(first, rest, caret) => onSplit(item, first, rest, caret)"
        />
      </VueDraggable>
    </template>
  </div>
</template>
