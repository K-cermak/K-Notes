<script setup lang="ts">
import { watch } from 'vue'
import { setLucideProps } from '@lucide/vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useSessionStore } from '@/stores/session'
import { useSyncStore } from '@/stores/sync'

setLucideProps({ strokeWidth: 1.6, size: 18 })

const session = useSessionStore()
const sync = useSyncStore()

watch(
  () => [session.user?.id, session.expired] as const,
  ([userId, expired], previous) => {
    if (!userId) {
      sync.stop()
    } else if (userId !== previous?.[0]) {
      sync.stop()
      void sync.start()
    } else if (!expired && previous?.[1]) {
      void sync.resume()
    }
  },
  { immediate: true },
)
</script>

<template>
  <RouterView />
  <ConfirmDialog />
</template>
