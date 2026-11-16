<script setup lang="ts">
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuTrigger,
} from 'reka-ui'
import { Copy, EllipsisVertical, Tag, Trash2, Undo2 } from '@lucide/vue'
import { iconButton, menuItem, menuPanel } from '@/components/ui/menu'

defineProps<{ trashed: boolean }>()

const emit = defineEmits<{ trash: []; copy: []; restore: []; purge: []; labels: [] }>()
</script>

<template>
  <DropdownMenuRoot :modal="false">
    <DropdownMenuTrigger :class="iconButton" :aria-label="$t('note.more')" :title="$t('note.more')">
      <EllipsisVertical :size="18" />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent :class="menuPanel" side="top" align="start" :side-offset="4">
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
          <DropdownMenuItem :class="menuItem" @select="emit('labels')">
            <Tag :size="16" /> {{ $t('labels.add') }}
          </DropdownMenuItem>
          <DropdownMenuItem :class="menuItem" @select="emit('copy')">
            <Copy :size="16" /> {{ $t('note.copy') }}
          </DropdownMenuItem>
        </template>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
