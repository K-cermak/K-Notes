<script setup lang="ts" generic="T extends string">
import type { Component } from 'vue'

/** A choice among a few options (.ui-segmented), shown as text or, with icons, as icons only. */
defineProps<{
  options: readonly { value: T; label: string; icon?: Component }[]
  label: string
}>()
const model = defineModel<T>({ required: true })
</script>

<template>
  <div role="radiogroup" :aria-label="label" class="ui-segmented">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="model === option.value"
      :aria-label="option.icon ? option.label : undefined"
      :title="option.icon ? option.label : undefined"
      class="ui-segmented__option"
      :class="option.icon && 'ui-segmented__option--icon'"
      @click="model = option.value"
    >
      <component :is="option.icon" v-if="option.icon" :size="16" />
      <template v-else>{{ option.label }}</template>
    </button>
  </div>
</template>
