<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LocalAttachment, LocalChecklistItem, LocalLabel, LocalNote } from '@/db/schema'
import { updateNote } from '@/db/notes'
import { insertKeys } from '@/db/positions'
import { GRID, LIST, useMasonry } from '@/composables/useMasonry'
import { useNoteDrag } from '@/composables/useNoteDrag'
import { useSelectionStore } from '@/stores/selection'
import NoteCard from './NoteCard.vue'

const props = defineProps<{
  notes: LocalNote[]
  layout: 'grid' | 'list'
  heading?: string
  labels: Map<string, LocalLabel[]>
  items: Map<string, LocalChecklistItem[]>
  attachments: Map<string, LocalAttachment[]>
  /** Whether the notes can be reordered by dragging; not in the trash or in search results. */
  sortable: boolean
  /** Cards joining or leaving fade in and out; not for search results, which change as you type. */
  animated: boolean
}>()

const selection = useSelectionStore()
const container = ref<HTMLElement | null>(null)
const keys = computed(() => props.notes.map((note) => note.id))
const byId = computed(() => new Map(props.notes.map((note) => [note.id, note])))

const drag = useNoteDrag({
  container,
  keys,
  hit: (x, y, dragged) => {
    for (const key of order.value) {
      if (key === dragged) continue
      const place = masonry.value.placements.get(key)
      const height = heights.get(key) ?? 0
      if (
        place &&
        x >= place.x &&
        x <= place.x + masonry.value.cardWidth &&
        y >= place.y &&
        y <= place.y + height
      ) {
        return key
      }
    }
    return null
  },
  canDrag: () => props.sortable,
  onDrop: (id, next) => {
    const others = next.filter((key) => key !== id)
    const positions = others.map((key) => byId.value.get(key)?.position ?? '')
    const [position] = insertKeys(positions, next.indexOf(id))
    if (position) void updateNote(id, { position })
  },
  onLongPress: (id) => {
    if (!selection.has(id)) selection.toggle(id)
  },
})

const order = computed(() => drag.preview.value ?? keys.value)
const {
  layout: masonry,
  heights,
  track,
} = useMasonry(container, order, () => (props.layout === 'list' ? LIST : GRID))

function transform(key: string): string {
  const dragged = drag.drag.value
  const place =
    dragged?.id === key ? { x: dragged.x, y: dragged.y } : masonry.value.placements.get(key)
  return `translate(${place?.x ?? 0}px, ${place?.y ?? 0}px)`
}

function swallow(event: MouseEvent): void {
  if (!drag.swallowClick()) return
  event.stopPropagation()
  event.preventDefault()
}
</script>

<template>
  <section class="flex flex-col gap-2">
    <h2
      v-if="heading"
      class="px-1 text-meta font-medium tracking-[0.08em] text-muted uppercase"
      :class="layout === 'list' && 'mx-auto w-full max-w-[600px]'"
      :style="layout === 'grid' ? { paddingLeft: `${masonry.offset + 4}px` } : undefined"
    >
      {{ heading }}
    </h2>
    <div
      ref="container"
      class="relative w-full"
      :class="layout === 'list' && 'mx-auto max-w-[600px]'"
      :style="{ height: `${masonry.height}px` }"
      data-testid="masonry"
      @click.capture="swallow"
    >
      <TransitionGroup
        :css="animated"
        type="animation"
        enter-active-class="card-enter"
        leave-active-class="card-leave"
        move-class="card-static"
      >
        <div
          v-for="note in notes"
          :key="note.id"
          :ref="(el) => track(note.id, el)"
          :data-masonry-key="note.id"
          class="absolute top-0 left-0 select-none [-webkit-touch-callout:none]"
          :class="[
            !masonry.measured && 'invisible',
            drag.drag.value?.id === note.id
              ? 'z-10 cursor-grabbing shadow-float'
              : 'transition-transform duration-200 ease-out motion-reduce:transition-none',
          ]"
          :style="{ width: `${masonry.cardWidth}px`, transform: transform(note.id) }"
          :data-dragging="drag.drag.value?.id === note.id || undefined"
          @pointerdown="
            (event) => drag.onPointerDown(event, note.id, event.currentTarget as HTMLElement)
          "
        >
          <NoteCard
            :note="note"
            :labels="labels.get(note.id) ?? []"
            :items="items.get(note.id) ?? []"
            :attachments="attachments.get(note.id) ?? []"
          />
        </div>
      </TransitionGroup>
    </div>
  </section>
</template>
