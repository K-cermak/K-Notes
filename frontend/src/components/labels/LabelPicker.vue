<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PopoverAnchor, PopoverContent, PopoverPortal, PopoverRoot } from 'reka-ui'
import { Plus } from '@lucide/vue'
import { byName, createLabel, MAX_LABEL_LENGTH, setNoteLabel } from '@/db/labels'
import { db } from '@/db/schema'
import { fold } from '@/db/search'
import { useLiveQuery } from '@/composables/useLiveQuery'
import { floatingPanel } from '@/components/ui/menu'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'

/**
 * Picks labels for a note: a filter field, a checkbox per label and "Create '<text>'" (SPEC 9).
 * Anchored to its slot, so a card or the editor can open it from a menu item. The menu hands focus
 * back to its button as it closes, so focus moving away must not close the picker; a click
 * outside or Escape still does.
 */
const props = defineProps<{ noteId: string | null; ensureNote?: () => Promise<string | null> }>()
const open = defineModel<boolean>('open', { required: true })

const filter = ref('')
const labels = useLiveQuery(async () => (await db.labels.toArray()).sort(byName), [])
const memberships = useLiveQuery(
  () => (props.noteId ? db.noteLabels.where('note_id').equals(props.noteId).toArray() : []),
  [],
)
const selected = computed(() => new Set(memberships.value.map((m) => m.label_id)))
const visible = computed(() => {
  const query = fold(filter.value.trim())
  return query ? labels.value.filter((l) => fold(l.name).includes(query)) : labels.value
})
const canCreate = computed(() => {
  const name = filter.value.trim()
  return (
    !!name && !labels.value.some((l) => l.name.toLocaleLowerCase() === name.toLocaleLowerCase())
  )
})

watch(open, (value) => {
  if (value) filter.value = ''
})

async function targetNote(): Promise<string | null> {
  return props.noteId ?? (await props.ensureNote?.()) ?? null
}

async function toggle(labelId: string, on: boolean): Promise<void> {
  const id = await targetNote()
  if (id) await setNoteLabel(id, labelId, on)
}

async function create(): Promise<void> {
  const labelId = await createLabel(filter.value)
  if (labelId) await toggle(labelId, true)
  filter.value = ''
}
</script>

<template>
  <PopoverRoot v-model:open="open">
    <PopoverAnchor as-child><slot /></PopoverAnchor>
    <PopoverPortal>
      <PopoverContent
        :class="[floatingPanel, 'flex w-[260px] flex-col']"
        side="bottom"
        align="start"
        :side-offset="4"
        data-testid="label-picker"
        @click.stop
        @focus-outside="(event: Event) => event.preventDefault()"
      >
        <p class="px-3 pt-3 text-label font-medium">{{ $t('labels.pickerTitle') }}</p>
        <input
          v-model="filter"
          class="mx-3 my-2 h-9 border-b border-line bg-transparent text-sm outline-none placeholder:text-faint focus:border-ink"
          :placeholder="$t('labels.filter')"
          :aria-label="$t('labels.filter')"
          :maxlength="MAX_LABEL_LENGTH"
          @keydown.enter.prevent="canCreate && create()"
        />
        <ul class="max-h-[260px] overflow-y-auto pb-1">
          <li v-for="label in visible" :key="label.id">
            <label
              class="flex h-10 cursor-pointer items-center gap-3 px-3 hover:bg-[color-mix(in_srgb,var(--ink)_5%,var(--bg))]"
            >
              <UiCheckbox
                :model-value="selected.has(label.id)"
                @update:model-value="(on) => toggle(label.id, on === true)"
              />
              <span class="truncate">{{ label.name }}</span>
            </label>
          </li>
        </ul>
        <button
          v-if="canCreate"
          type="button"
          class="flex h-10 cursor-pointer items-center gap-3 border-t border-line px-3 text-left hover:bg-[color-mix(in_srgb,var(--ink)_5%,var(--bg))]"
          data-testid="create-label"
          @click="create"
        >
          <Plus :size="16" />
          <span class="truncate">{{ $t('labels.create', { name: filter.trim() }) }}</span>
        </button>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
