<script setup lang="ts">
import { Monitor, Moon, Sun } from '@lucide/vue'
import { themes, type Theme } from '@/theme'

const model = defineModel<Theme>({ required: true })

const icons = { system: Monitor, light: Sun, dark: Moon }
</script>

<template>
  <div role="radiogroup" :aria-label="$t('theme.label')" class="inline-flex border border-line">
    <button
      v-for="theme in themes"
      :key="theme"
      type="button"
      role="radio"
      :aria-checked="model === theme"
      :aria-label="$t(`theme.${theme}`)"
      :title="$t(`theme.${theme}`)"
      class="grid size-8 cursor-pointer place-items-center text-muted transition-colors duration-150 not-first:border-l not-first:border-line hover:text-ink aria-checked:bg-[color-mix(in_srgb,var(--ink)_6%,var(--bg))] aria-checked:text-ink"
      @click="model = theme"
    >
      <component :is="icons[theme]" :size="16" />
    </button>
  </div>
</template>
