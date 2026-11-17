<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LocalAttachment, LocalChecklistItem, LocalLabel, LocalNote } from '@/db/schema'
import { useMasonry } from '@/composables/useMasonry'
import NoteCard from './NoteCard.vue'

const props = defineProps<{
  notes: LocalNote[]
  layout: 'grid' | 'list'
  heading?: string
  labels: Map<string, LocalLabel[]>
  items: Map<string, LocalChecklistItem[]>
  attachments: Map<string, LocalAttachment[]>
}>()

const container = ref<HTMLElement | null>(null)
const keys = computed(() => props.notes.map((note) => note.id))
const { layout: masonry, track } = useMasonry(container, keys)
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
    <div v-if="layout === 'list'" class="mx-auto flex w-full max-w-[600px] flex-col gap-3">
      <NoteCard
        v-for="note in notes"
        :key="note.id"
        :note="note"
        :labels="labels.get(note.id) ?? []"
        :items="items.get(note.id) ?? []"
        :attachments="attachments.get(note.id) ?? []"
      />
    </div>
    <div
      v-else
      ref="container"
      class="relative w-full"
      :style="{ height: `${masonry.height}px` }"
      data-testid="masonry"
    >
      <div
        v-for="note in notes"
        :key="note.id"
        :ref="(el) => track(note.id, el)"
        :data-masonry-key="note.id"
        class="absolute top-0 left-0 transition-transform duration-200 ease-out motion-reduce:transition-none"
        :class="!masonry.measured && 'invisible'"
        :style="{
          width: `${masonry.cardWidth}px`,
          transform: `translate(${masonry.placements.get(note.id)?.x ?? 0}px, ${masonry.placements.get(note.id)?.y ?? 0}px)`,
        }"
      >
        <NoteCard
          :note="note"
          :labels="labels.get(note.id) ?? []"
          :items="items.get(note.id) ?? []"
          :attachments="attachments.get(note.id) ?? []"
        />
      </div>
    </div>
  </section>
</template>
