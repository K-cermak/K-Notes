<script setup lang="ts">
import { CheckboxIndicator, CheckboxRoot } from 'reka-ui'
import { Check, Minus } from '@lucide/vue'

defineProps<{ disabled?: boolean; id?: string }>()

const model = defineModel<boolean | 'indeterminate'>({ default: false })
</script>

<template>
  <CheckboxRoot :id="id" v-model="model" :disabled="disabled" class="ui-checkbox">
    <CheckboxIndicator>
      <Minus v-if="model === 'indeterminate'" :size="14" />
      <Check v-else :size="14" />
    </CheckboxIndicator>
  </CheckboxRoot>
</template>
