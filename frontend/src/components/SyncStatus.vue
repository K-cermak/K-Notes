<script setup lang="ts">
import { computed } from 'vue'
import { Cloud, CloudAlert, CloudCheck, CloudOff, RefreshCw } from '@lucide/vue'
import { useSyncStore } from '@/stores/sync'

const sync = useSyncStore()

const icon = computed(
  () =>
    ({
      idle: Cloud,
      synced: CloudCheck,
      syncing: RefreshCw,
      offline: CloudOff,
      error: CloudAlert,
      unauthorized: CloudAlert,
    })[sync.state],
)
</script>

<template>
  <div
    class="flex h-9 items-center gap-1.5 px-1.5 text-muted"
    :title="$t(`sync.${sync.state}`)"
    data-testid="sync-status"
    :data-state="sync.state"
  >
    <component
      :is="icon"
      :size="18"
      :class="[
        sync.state === 'error' && 'text-danger',
        sync.state === 'syncing' &&
          'animate-spin [animation-duration:1.5s] motion-reduce:animate-none',
      ]"
      aria-hidden="true"
    />
    <span class="sr-only">{{ $t(`sync.${sync.state}`) }}</span>
    <span
      v-if="sync.unsent > 0"
      class="ui-meta"
      data-testid="unsent"
      :aria-label="$t('sync.unsent', { count: sync.unsent }, sync.unsent)"
    >
      {{ sync.unsent }}
    </span>
  </div>
</template>
