<script setup lang="ts">
import { useRouter } from 'vue-router'
import { X } from '@lucide/vue'
import type { LocalLabel } from '@/db/schema'
import { setNoteLabel } from '@/db/labels'
import { noteLine, type NoteColor } from '@/notes'

const props = defineProps<{
  noteId: string
  labels: LocalLabel[]
  color: NoteColor
  limit?: number
}>()

const router = useRouter()
</script>

<template>
  <ul v-if="labels.length" class="flex flex-wrap gap-1.5" data-testid="label-chips">
    <li
      v-for="label in labels.slice(0, limit ?? labels.length)"
      :key="label.id"
      class="group/chip flex h-6 max-w-full items-center border text-meta text-ink"
      :style="{ borderColor: noteLine(color) }"
    >
      <button
        type="button"
        class="min-w-0 cursor-pointer truncate px-1.5"
        data-testid="label-chip"
        @click.stop="router.push(`/label/${label.id}`)"
      >
        {{ label.name }}
      </button>
      <button
        type="button"
        class="hidden size-5 shrink-0 cursor-pointer place-items-center text-muted group-hover/chip:grid hover:text-ink pointer-coarse:grid"
        :aria-label="$t('labels.remove', { name: label.name })"
        @click.stop="setNoteLabel(props.noteId, label.id, false)"
      >
        <X :size="12" />
      </button>
    </li>
    <li
      v-if="limit && labels.length > limit"
      class="ui-meta flex h-6 items-center border px-1.5"
      :style="{ borderColor: noteLine(color) }"
    >
      +{{ labels.length - limit }}
    </li>
  </ul>
</template>
