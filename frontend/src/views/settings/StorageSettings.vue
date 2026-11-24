<script setup lang="ts">
import { onMounted } from 'vue'
import { useSyncStore } from '@/stores/sync'
import StorageUsage from '@/components/StorageUsage.vue'

const sync = useSyncStore()
// The usage arrives with a sync cycle, so one is started to show a fresh figure.
onMounted(() => sync.syncNow())
</script>

<template>
  <section class="flex flex-col gap-5">
    <h2 class="ui-section-title">{{ $t('settings.storage.title') }}</h2>
    <p class="text-muted">{{ $t('settings.storage.intro') }}</p>
    <template v-if="sync.storage">
      <StorageUsage :storage="sync.storage" />
      <p v-if="sync.storage.full" class="text-label text-danger">
        {{ $t('storage.fullNotice') }}
      </p>
    </template>
  </section>
</template>
