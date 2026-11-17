<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ icon: Component; text: string }>()
</script>

<template>
  <div
    class="flex animate-rise flex-col items-center gap-4 px-4 pt-[12vh] text-center motion-reduce:animate-fade"
    data-testid="empty-state"
  >
    <component
      :is="icon"
      :size="96"
      class="[stroke-width:1] text-[color-mix(in_srgb,var(--ink)_14%,var(--bg))]"
      aria-hidden="true"
    />
    <p class="text-lg text-muted">{{ text }}</p>
  </div>
</template>
