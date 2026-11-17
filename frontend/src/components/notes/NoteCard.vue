<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Archive,
  ArchiveRestore,
  Check,
  ChevronDown,
  ImagePlus,
  Pin,
  PinOff,
  Trash2,
  Undo2,
} from '@lucide/vue'
import { convertNote, updateItem } from '@/db/checklist'
import type { LocalAttachment, LocalChecklistItem, LocalLabel, LocalNote } from '@/db/schema'
import LabelChips from '@/components/labels/LabelChips.vue'
import LabelPicker from '@/components/labels/LabelPicker.vue'
import { updateNote } from '@/db/notes'
import { plainText } from '@/db/richtext'
import { NOTE_ORDER, noteLine, noteSurface } from '@/notes'
import { useNoteActions } from '@/composables/useNoteActions'
import { iconButton } from '@/components/ui/menu'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import ImageCollage from '@/components/images/ImageCollage.vue'
import { useImageAttach } from '@/composables/useImageAttach'
import { useExpandedChecklistsStore } from '@/stores/expandedChecklists'
import { useSelectionStore } from '@/stores/selection'
import { useSyncStore } from '@/stores/sync'
import ColorPicker from './ColorPicker.vue'
import NoteMenu from './NoteMenu.vue'
import RichTextView from './RichTextView'

const props = defineProps<{
  note: LocalNote
  labels: LocalLabel[]
  items: LocalChecklistItem[]
  attachments: LocalAttachment[]
}>()

const router = useRouter()
const actions = useNoteActions()
const images = useImageAttach()
const sync = useSyncStore()
const selection = useSelectionStore()
const order = inject(NOTE_ORDER, ref([]))
const selected = computed(() => selection.has(props.note.id))
const body = ref<HTMLElement | null>(null)
const clipped = ref(false)
const picking = ref(false)

// The menu closes first and hands focus back to its button; the picker opens after that.
function pickLabels(): void {
  setTimeout(() => (picking.value = true))
}

const color = computed(() => props.note.color)
const trashed = computed(() => props.note.trashed_at !== null)
const checklist = computed(() => props.note.type === 'checklist')
// Checklists show unchecked items, then a count of the checked ones, which opens them right on
// the card (SPEC 9, Note card).
const openItems = computed(() => props.items.filter((item) => !item.checked))
const checkedItems = computed(() => props.items.filter((item) => item.checked))
const expanded = useExpandedChecklistsStore()
const showChecked = computed(() => expanded.has(props.note.id))
const empty = computed(() => {
  if (props.note.title || props.attachments.length > 0) return false
  return checklist.value
    ? !props.items.some((item) => item.text.trim())
    : !plainText(props.note.content).trim()
})

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

// While notes are selected, a click selects or deselects instead of opening (SPEC 9).
function activate(event?: MouseEvent | KeyboardEvent): void {
  if (!selection.active) open()
  else if (event?.shiftKey) selection.extend(props.note.id, order.value)
  else selection.toggle(props.note.id)
}

function select(event: MouseEvent): void {
  if (event.shiftKey && selection.active) selection.extend(props.note.id, order.value)
  else selection.toggle(props.note.id)
}
</script>

<template>
  <article
    class="group relative flex flex-col border transition-[border-color] duration-150 hover:border-(--line-hover-card) focus-visible:border-ink focus-visible:outline-none"
    :class="selected && 'outline-2! -outline-offset-2! outline-ink!'"
    :style="{
      ...noteSurface(color),
      borderColor: selected ? 'var(--ink)' : noteLine(color),
      '--line-hover-card':
        color === 'default'
          ? 'var(--line-hover)'
          : `color-mix(in srgb, var(--ink) 30%, var(--note-${color}))`,
    }"
    tabindex="0"
    :aria-label="note.title || $t('note.untitled')"
    data-testid="note-card"
    :data-note-id="note.id"
    :data-selected="selected || undefined"
    @click="activate"
    @keydown.enter.self="activate"
  >
    <button
      type="button"
      class="absolute -top-2.5 -left-2.5 z-[1] grid size-6 cursor-pointer place-items-center border border-ink transition-opacity duration-150 focus-visible:opacity-100"
      :class="
        selected
          ? 'bg-ink text-bg'
          : 'bg-bg text-ink opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 pointer-coarse:hidden'
      "
      :aria-label="$t('selection.select')"
      :aria-pressed="selected"
      :title="$t('selection.select')"
      data-testid="card-select"
      @click.stop="select"
    >
      <Check :size="14" class="[stroke-width:2.2]" />
    </button>
    <ImageCollage :attachments="attachments" lazy @missing="sync.downloadImages(note.id)" />
    <div class="px-4 pt-3 pb-2">
      <p
        v-if="note.conflict_of"
        class="ui-badge ui-badge--warning mb-2"
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
        <ul v-if="checklist" class="flex flex-col" data-testid="card-items">
          <li v-for="item in openItems" :key="item.id" class="flex items-start gap-2 py-0.5">
            <span class="grid h-5 shrink-0 place-items-center" @click.stop>
              <UiCheckbox
                :model-value="false"
                :disabled="trashed"
                :aria-label="item.text"
                @update:model-value="(value) => updateItem(item.id, { checked: value === true })"
              />
            </span>
            <span class="min-w-0 break-words">{{ item.text }}</span>
          </li>
          <li v-if="checkedItems.length > 0" class="pt-1">
            <button
              type="button"
              class="ui-meta flex cursor-pointer items-center gap-1 py-0.5 hover:text-ink"
              :aria-expanded="showChecked"
              data-testid="card-checked"
              @click.stop="expanded.toggle(note.id)"
            >
              <ChevronDown
                :size="14"
                class="transition-transform duration-150"
                :class="!showChecked && '-rotate-90'"
              />
              {{ $t('checklist.checked', { count: checkedItems.length }, checkedItems.length) }}
            </button>
          </li>
          <template v-if="showChecked">
            <li v-for="item in checkedItems" :key="item.id" class="flex items-start gap-2 py-0.5">
              <span class="grid h-5 shrink-0 place-items-center" @click.stop>
                <UiCheckbox
                  :model-value="true"
                  :disabled="trashed"
                  :aria-label="item.text"
                  @update:model-value="(value) => updateItem(item.id, { checked: value === true })"
                />
              </span>
              <span class="min-w-0 break-words text-muted line-through">{{ item.text }}</span>
            </li>
          </template>
        </ul>
        <RichTextView v-else :doc="note.content" />
      </div>
      <p v-if="empty" class="text-[22px] leading-snug text-muted">{{ $t('note.emptyCard') }}</p>
      <LabelChips :note-id="note.id" :labels="labels" :color="color" :limit="3" class="mt-3" />
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
      class="flex items-center gap-0.5 px-1.5 pb-1.5 opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100 has-[[aria-expanded=true]]:opacity-100 has-[[data-state=open]]:opacity-100 pointer-coarse:hidden"
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
          :aria-label="$t('images.add')"
          :title="$t('images.add')"
          data-testid="card-add-image"
          @click="images.pickAndAttach(note.id)"
        >
          <ImagePlus :size="18" />
        </button>
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
        <LabelPicker v-model:open="picking" :note-id="note.id">
          <NoteMenu
            :trashed="false"
            :checklist="checklist"
            @convert="(to) => convertNote(note.id, to)"
            @trash="actions.trash(note.id)"
            @copy="actions.copy(note.id)"
            @labels="pickLabels"
          />
        </LabelPicker>
      </template>
    </div>
  </article>
</template>
