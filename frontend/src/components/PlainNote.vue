<script setup lang="ts">
import { ref, watch } from 'vue'
import { Trash2, X } from '@lucide/vue'
import { purgeNote, updateNote } from '@/db/notes'
import { fromPlainText, plainText } from '@/db/richtext'
import type { LocalNote } from '@/db/schema'
import { useDebouncedSave } from '@/composables/useDebouncedSave'
import UiButton from '@/components/ui/UiButton.vue'

// Part of the deliberately plain phase 3 interface, which exists to exercise sync.
const props = defineProps<{ note: LocalNote }>()

const title = ref(props.note.title)
const text = ref(plainText(props.note.content))
let editing = false

const { schedule, flush, pending } = useDebouncedSave(() =>
  updateNote(props.note.id, { title: title.value, content: fromPlainText(text.value) }),
)

// Pulled changes show up unless the user is in the middle of typing here.
watch(
  () => props.note,
  (note) => {
    if (editing || pending()) return
    title.value = note.title
    text.value = plainText(note.content)
  },
)

function blur(): void {
  editing = false
  flush()
}
</script>

<template>
  <li class="flex flex-col gap-2 border border-line p-3" data-testid="note" :data-note-id="note.id">
    <div
      v-if="note.conflict_of"
      class="flex items-center justify-between gap-2 text-label text-warning"
      data-testid="conflict"
    >
      {{ $t('plain.conflict') }}
      <UiButton
        variant="ghost"
        size="sm"
        icon-only
        :aria-label="$t('plain.dismissConflict')"
        @click="updateNote(note.id, { conflict_of: null })"
      >
        <X :size="16" />
      </UiButton>
    </div>
    <input
      v-model="title"
      class="w-full bg-transparent font-semibold tracking-[-0.01em] outline-none placeholder:text-faint"
      :placeholder="$t('plain.title')"
      :aria-label="$t('plain.title')"
      data-testid="note-title"
      @focus="editing = true"
      @blur="blur"
      @input="schedule"
    />
    <textarea
      v-model="text"
      rows="2"
      class="field-sizing-content w-full resize-none bg-transparent outline-none placeholder:text-faint"
      :placeholder="$t('plain.text')"
      :aria-label="$t('plain.text')"
      data-testid="note-text"
      @focus="editing = true"
      @blur="blur"
      @input="schedule"
    />
    <div class="flex justify-end">
      <UiButton
        variant="ghost"
        size="sm"
        icon-only
        :aria-label="$t('plain.delete')"
        data-testid="delete"
        @click="purgeNote(note.id)"
      >
        <Trash2 :size="16" />
      </UiButton>
    </div>
  </li>
</template>
