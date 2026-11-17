<script setup lang="ts">
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuTrigger,
} from 'reka-ui'
import { Copy, EllipsisVertical, ListChecks, Tag, Trash2, Type, Undo2 } from '@lucide/vue'
import { iconButton, menuItem, menuPanel } from '@/components/ui/menu'

defineProps<{ trashed: boolean; checklist?: boolean }>()

const emit = defineEmits<{
  trash: []
  copy: []
  restore: []
  purge: []
  labels: []
  convert: [to: 'text' | 'checklist']
}>()

// The label picker opens in the menu's place and focuses its filter field; the menu must not hand
// the focus back to its button as it closes, or typing would go nowhere.
let pickingLabels = false
function pickLabels(): void {
  pickingLabels = true
  emit('labels')
}
function onCloseAutoFocus(event: Event): void {
  if (pickingLabels) event.preventDefault()
  pickingLabels = false
}
</script>

<template>
  <DropdownMenuRoot :modal="false">
    <DropdownMenuTrigger :class="iconButton" :aria-label="$t('note.more')" :title="$t('note.more')">
      <EllipsisVertical :size="18" />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent
        :class="menuPanel"
        side="top"
        align="start"
        :side-offset="4"
        @close-auto-focus="onCloseAutoFocus"
      >
        <template v-if="trashed">
          <DropdownMenuItem :class="menuItem" @select="emit('restore')">
            <Undo2 :size="16" /> {{ $t('note.restore') }}
          </DropdownMenuItem>
          <DropdownMenuItem :class="[menuItem, 'text-danger']" @select="emit('purge')">
            <Trash2 :size="16" /> {{ $t('note.deleteForever') }}
          </DropdownMenuItem>
        </template>
        <template v-else>
          <DropdownMenuItem :class="menuItem" @select="emit('trash')">
            <Trash2 :size="16" /> {{ $t('note.delete') }}
          </DropdownMenuItem>
          <DropdownMenuItem :class="menuItem" @select="pickLabels">
            <Tag :size="16" /> {{ $t('labels.add') }}
          </DropdownMenuItem>
          <DropdownMenuItem :class="menuItem" @select="emit('copy')">
            <Copy :size="16" /> {{ $t('note.copy') }}
          </DropdownMenuItem>
          <DropdownMenuItem
            :class="menuItem"
            @select="emit('convert', checklist ? 'text' : 'checklist')"
          >
            <template v-if="checklist">
              <Type :size="16" /> {{ $t('note.hideCheckboxes') }}
            </template>
            <template v-else> <ListChecks :size="16" /> {{ $t('note.showCheckboxes') }} </template>
          </DropdownMenuItem>
        </template>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
