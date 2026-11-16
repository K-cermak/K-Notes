<script setup lang="ts">
import { computed } from 'vue'
import { Cloud, CloudAlert, CloudOff, RefreshCw } from '@lucide/vue'
import { useSyncStore } from '@/stores/sync'

const sync = useSyncStore()

const icon = computed(
  () =>
    ({
      idle: Cloud,
      synced: Cloud,
      syncing: RefreshCw,
      offline: CloudOff,
      error: CloudAlert,
      unauthorized: CloudAlert,
    })[sync.state],
)
</script>

<template>
  <div
    class="flex items-center gap-2 text-label text-muted"
    data-testid="sync-status"
    :data-state="sync.state"
  >
    <component
      :is="icon"
      :size="16"
      :class="sync.state === 'error' && 'text-danger'"
      aria-hidden="true"
    />
    <span>{{ $t(`sync.${sync.state}`) }}</span>
    <span v-if="sync.unsent > 0" class="font-mono text-meta tabular-nums" data-testid="unsent">
      {{ $t('sync.unsent', { count: sync.unsent }, sync.unsent) }}
    </span>
  </div>
</template>
