<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Editor } from '@tiptap/core'
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import {
  Bold,
  Heading1,
  Heading2,
  Italic,
  Pilcrow,
  RemoveFormatting,
  Type,
  Underline,
} from '@lucide/vue'
import { floatingPanel, iconButton } from '@/components/ui/menu'

const props = defineProps<{ editor: Editor | undefined }>()

// Opened with the mouse, the menu leaves focus (and the selection) in the editor, so typing goes
// on in the new format. Opened from the keyboard it takes focus as usual.
const byPointer = ref(false)
const open = ref(false)

// Closed after a choice, so it does not cover the text being typed in the new format.
function choose(run: (editor: Editor) => boolean): void {
  if (props.editor) run(props.editor)
  open.value = false
}

const blocks = computed(() => [
  {
    key: 'h1',
    icon: Heading1,
    active: props.editor?.isActive('heading', { level: 1 }),
    run: (e: Editor) => e.chain().focus().toggleHeading({ level: 1 }).run(),
  },
  {
    key: 'h2',
    icon: Heading2,
    active: props.editor?.isActive('heading', { level: 2 }),
    run: (e: Editor) => e.chain().focus().toggleHeading({ level: 2 }).run(),
  },
  {
    key: 'normal',
    icon: Pilcrow,
    active: props.editor?.isActive('paragraph'),
    run: (e: Editor) => e.chain().focus().setParagraph().run(),
  },
])
const marks = computed(() => [
  {
    key: 'bold',
    icon: Bold,
    active: props.editor?.isActive('bold'),
    run: (e: Editor) => e.chain().focus().toggleBold().run(),
  },
  {
    key: 'italic',
    icon: Italic,
    active: props.editor?.isActive('italic'),
    run: (e: Editor) => e.chain().focus().toggleItalic().run(),
  },
  {
    key: 'underline',
    icon: Underline,
    active: props.editor?.isActive('underline'),
    run: (e: Editor) => e.chain().focus().toggleUnderline().run(),
  },
  {
    key: 'clear',
    icon: RemoveFormatting,
    active: false,
    run: (e: Editor) => e.chain().focus().unsetAllMarks().setParagraph().run(),
  },
])
</script>

<template>
  <PopoverRoot v-model:open="open">
    <PopoverTrigger
      :class="iconButton"
      :disabled="!editor"
      :aria-label="$t('format.title')"
      :title="$t('format.title')"
      @pointerdown="byPointer = true"
      @mousedown.prevent
      @keydown="byPointer = false"
    >
      <Type :size="18" />
    </PopoverTrigger>
    <PopoverPortal>
      <PopoverContent
        :class="floatingPanel"
        side="top"
        align="start"
        :side-offset="4"
        @open-auto-focus="(event: Event) => byPointer && event.preventDefault()"
        @close-auto-focus="(event: Event) => byPointer && event.preventDefault()"
      >
        <div class="flex items-center gap-0.5 p-1" role="toolbar" :aria-label="$t('format.title')">
          <template v-for="(group, index) in [blocks, marks]" :key="index">
            <span v-if="index > 0" class="mx-1 h-6 w-px bg-line" aria-hidden="true" />
            <button
              v-for="item in group"
              :key="item.key"
              type="button"
              :class="[
                iconButton,
                item.active && 'bg-[color-mix(in_srgb,var(--ink)_8%,transparent)] text-ink',
              ]"
              :aria-label="$t(`format.${item.key}`)"
              :aria-pressed="item.key === 'clear' ? undefined : !!item.active"
              :title="$t(`format.${item.key}`)"
              @mousedown.prevent
              @click="choose(item.run)"
            >
              <component :is="item.icon" :size="18" />
            </button>
          </template>
        </div>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
