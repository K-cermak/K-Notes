<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { GripVertical, X } from '@lucide/vue'
import type { LocalChecklistItem } from '@/db/schema'
import { MAX_ITEM_LENGTH } from '@/db/checklist'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'

const props = defineProps<{
  item: LocalChecklistItem
  readonly: boolean
  /** True while this row has typed text that has not been written yet. */
  dirty: boolean
}>()
const emit = defineEmits<{
  text: [value: string]
  check: [checked: boolean]
  remove: []
  /** Backspace in an empty item. */
  removeBack: []
  /** Enter or a multi-line paste: this item keeps `first`, the rest become new items below. */
  split: [first: string, rest: string[], caret: 'start' | 'end']
}>()

const field = ref<HTMLTextAreaElement | null>(null)
const text = ref(props.item.text)
const focused = ref(false)

// Changes from other devices show up unless the user is typing here.
watch(
  () => props.item.text,
  (value) => {
    if (!focused.value && !props.dirty) text.value = value
  },
)

function fit(): void {
  const el = field.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}
watch(text, () => nextTick(fit))
const observer = new ResizeObserver(fit)
onMounted(() => field.value && observer.observe(field.value))
onBeforeUnmount(() => observer.disconnect())

function onInput(): void {
  emit('text', text.value)
}

function onKeydown(event: KeyboardEvent): void {
  const el = field.value
  if (!el || event.isComposing) return
  if (event.key === 'Enter' && !event.shiftKey && !event.metaKey && !event.ctrlKey) {
    event.preventDefault()
    const before = text.value.slice(0, el.selectionStart)
    const after = text.value.slice(el.selectionEnd)
    text.value = before
    emit('split', before, [after], 'start')
  } else if (event.key === 'Backspace' && text.value === '') {
    event.preventDefault()
    emit('removeBack')
  }
}

// Several pasted lines become several items (SPEC 9, Checklists); blank lines are skipped.
function onPaste(event: ClipboardEvent): void {
  const el = field.value
  const pasted = event.clipboardData?.getData('text/plain') ?? ''
  if (!el || !/[\r\n]/.test(pasted)) return
  event.preventDefault()
  const combined =
    text.value.slice(0, el.selectionStart) + pasted + text.value.slice(el.selectionEnd)
  const [first = '', ...rest] = combined.split(/\r?\n|\r/)
  text.value = first
  emit(
    'split',
    first,
    rest.filter((line) => line.trim()),
    'end',
  )
}

defineExpose({
  focus(caret: 'start' | 'end'): void {
    const el = field.value
    if (!el) return
    el.focus()
    const at = caret === 'start' ? 0 : el.value.length
    el.setSelectionRange(at, at)
  },
})
</script>

<template>
  <div
    class="group/item flex items-start gap-1 border-y border-transparent focus-within:border-[color-mix(in_srgb,var(--ink)_14%,transparent)]"
    data-testid="checklist-item"
    :data-checked="item.checked"
  >
    <span
      v-if="!readonly"
      class="drag-handle grid h-8 w-5 shrink-0 cursor-grab touch-none place-items-center text-muted opacity-0 group-focus-within/item:opacity-100 group-hover/item:opacity-100 pointer-coarse:opacity-100"
      :aria-hidden="true"
    >
      <GripVertical :size="16" />
    </span>
    <span class="grid h-8 shrink-0 place-items-center px-1" :class="readonly && 'ml-1'">
      <UiCheckbox
        :model-value="item.checked"
        :disabled="readonly"
        :aria-label="text"
        data-testid="item-checkbox"
        @update:model-value="(value) => emit('check', value === true)"
      />
    </span>
    <textarea
      ref="field"
      v-model="text"
      rows="1"
      class="min-w-0 flex-1 resize-none overflow-hidden bg-transparent py-1.5 leading-5 outline-none placeholder:text-faint pointer-coarse:text-base"
      :class="item.checked && 'text-muted line-through'"
      :readonly="readonly"
      :maxlength="MAX_ITEM_LENGTH"
      :aria-label="$t('checklist.item')"
      data-testid="item-text"
      @input="onInput"
      @keydown="onKeydown"
      @paste="onPaste"
      @focus="focused = true"
      @blur="focused = false"
    />
    <button
      v-if="!readonly"
      type="button"
      class="grid size-8 shrink-0 cursor-pointer place-items-center text-muted opacity-0 transition-colors duration-150 group-focus-within/item:opacity-100 group-hover/item:opacity-100 hover:bg-[color-mix(in_srgb,var(--ink)_6%,transparent)] hover:text-ink pointer-coarse:opacity-100"
      :aria-label="$t('checklist.remove')"
      :title="$t('checklist.remove')"
      data-testid="item-remove"
      @click="emit('remove')"
    >
      <X :size="16" />
    </button>
  </div>
</template>
