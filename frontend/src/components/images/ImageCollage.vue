<script setup lang="ts">
import { computed } from 'vue'
import { X } from '@lucide/vue'
import type { LocalAttachment } from '@/db/schema'
import NoteImage from './NoteImage.vue'

/**
 * A note's images edge to edge, in rows of up to three whose images share one height
 * (SPEC 9, Note card). Each image grows with its aspect ratio, which keeps a row's heights equal;
 * the ratio is scaled up because flex-grow factors that sum to less than 1 leave space unfilled.
 */
const props = defineProps<{
  attachments: LocalAttachment[]
  lazy?: boolean
  /** Shows a remove button on each image. */
  removable?: boolean
}>()
const emit = defineEmits<{
  open: [index: number, event: MouseEvent]
  remove: [id: string]
  missing: []
}>()

function rowSizes(count: number): number[] {
  const sizes: number[] = []
  for (let left = count; left > 0;) {
    // Four left become two pairs rather than three and a lone image.
    const size = left === 4 ? 2 : Math.min(3, left)
    sizes.push(size)
    left -= size
  }
  return sizes
}

const rows = computed(() => {
  let start = 0
  return rowSizes(props.attachments.length).map((size) => {
    const row = props.attachments
      .slice(start, start + size)
      .map((a, i) => ({ a, index: start + i }))
    start += size
    return row
  })
})
</script>

<template>
  <div v-if="attachments.length" class="flex flex-col gap-0.5" data-testid="image-collage">
    <div v-for="(row, r) in rows" :key="r" class="flex gap-0.5">
      <div
        v-for="{ a, index } in row"
        :key="a.id"
        class="group/image relative min-w-0"
        :style="{ flex: `${(100 * a.width) / a.height} 1 0%` }"
      >
        <!-- On cards (lazy), a tall image is cropped so it does not fill the whole screen. -->
        <NoteImage
          :attachment="a"
          :lazy="lazy"
          class="cursor-pointer"
          :class="lazy && 'max-h-[480px]'"
          @click="(event: MouseEvent) => emit('open', index, event)"
          @missing="emit('missing')"
        />
        <button
          v-if="removable"
          type="button"
          class="absolute top-1.5 right-1.5 grid size-8 cursor-pointer place-items-center bg-[color-mix(in_srgb,var(--bg)_85%,transparent)] text-ink opacity-0 transition-opacity duration-150 group-focus-within/image:opacity-100 group-hover/image:opacity-100 focus-visible:opacity-100 pointer-coarse:opacity-100"
          :aria-label="$t('images.remove')"
          :title="$t('images.remove')"
          data-testid="remove-image"
          @click.stop="emit('remove', a.id)"
        >
          <X :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>
