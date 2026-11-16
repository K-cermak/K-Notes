<script setup lang="ts">
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { Check, Palette } from '@lucide/vue'
import { NOTE_COLORS, noteBackground, type NoteColor } from '@/notes'
import { floatingPanel, iconButton } from '@/components/ui/menu'

const color = defineModel<NoteColor>({ required: true })
</script>

<template>
  <PopoverRoot>
    <PopoverTrigger :class="iconButton" :aria-label="$t('note.color')" :title="$t('note.color')">
      <Palette :size="18" />
    </PopoverTrigger>
    <PopoverPortal>
      <PopoverContent :class="floatingPanel" side="top" align="start" :side-offset="4">
        <div class="grid grid-cols-6 gap-1.5 p-2" role="radiogroup" :aria-label="$t('note.color')">
          <button
            v-for="key in NOTE_COLORS"
            :key="key"
            type="button"
            role="radio"
            :aria-checked="color === key"
            :aria-label="$t(`colors.${key}`)"
            :title="$t(`colors.${key}`)"
            class="grid size-8 cursor-pointer place-items-center border border-line-hover text-ink transition-colors duration-150 hover:border-ink aria-checked:border-ink pointer-coarse:size-10"
            :style="{ background: noteBackground(key) }"
            @click="color = key"
          >
            <Check v-if="color === key" :size="16" />
          </button>
        </div>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
