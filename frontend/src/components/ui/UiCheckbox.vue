<script setup lang="ts">
import { CheckboxIndicator, CheckboxRoot } from 'reka-ui'
import { Check, Minus } from '@lucide/vue'

defineProps<{ disabled?: boolean; id?: string }>()

const model = defineModel<boolean | 'indeterminate'>({ default: false })
</script>

<template>
  <CheckboxRoot
    :id="id"
    v-model="model"
    :disabled="disabled"
    class="grid size-4.5 shrink-0 cursor-pointer place-items-center border border-[color-mix(in_srgb,var(--ink)_50%,transparent)] bg-transparent text-bg transition-colors duration-150 hover:border-ink disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-ink data-[state=checked]:bg-ink data-[state=indeterminate]:border-ink data-[state=indeterminate]:bg-ink"
  >
    <CheckboxIndicator>
      <Minus v-if="model === 'indeterminate'" :size="14" class="[stroke-width:2.2]" />
      <Check v-else :size="14" class="[stroke-width:2.2]" />
    </CheckboxIndicator>
  </CheckboxRoot>
</template>
