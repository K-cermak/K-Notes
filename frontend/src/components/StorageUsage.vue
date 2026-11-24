<script setup lang="ts">
import { computed } from 'vue'
import { formatBytes } from '@/format'
import type { components } from '@/api/schema'

const props = defineProps<{ storage: components['schemas']['StorageStatus'] }>()

const share = computed(() => {
  const { used_bytes, limit_bytes } = props.storage
  return limit_bytes ? Math.min(1, used_bytes / limit_bytes) : 0
})
</script>

<template>
  <div class="flex flex-col gap-2" data-testid="storage-use">
    <span class="ui-numeric">
      {{
        storage.limit_bytes === null
          ? $t('storage.usedUnlimited', { used: formatBytes(storage.used_bytes) })
          : $t('storage.used', {
              used: formatBytes(storage.used_bytes),
              limit: formatBytes(storage.limit_bytes),
            })
      }}
    </span>
    <div
      v-if="storage.limit_bytes !== null"
      class="ui-meter"
      :class="storage.full && 'ui-meter--full'"
      role="meter"
      :aria-valuenow="Math.round(share * 100)"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="$t('storage.title')"
    >
      <div class="ui-meter__bar" :style="{ width: `${share * 100}%` }" />
    </div>
  </div>
</template>
