<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLucideProps } from '@lucide/vue'
import AppSnackbar from '@/components/AppSnackbar.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { registerServiceWorker, trackVisualViewport } from '@/pwa'
import { applyTheme, rememberTheme } from '@/theme'
import { useSessionStore } from '@/stores/session'
import { useSnackbarStore } from '@/stores/snackbar'
import { useSyncStore } from '@/stores/sync'

setLucideProps({ strokeWidth: 1.6, size: 18 })

const session = useSessionStore()
const sync = useSyncStore()
const snackbar = useSnackbarStore()
const { t } = useI18n()

onMounted(() => {
  trackVisualViewport()
  registerServiceWorker((reload) =>
    snackbar.pin(t('pwa.updateReady'), { label: t('pwa.reload'), run: reload }),
  )
})

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

// Theme follows the profile and is cached for the next start (SPEC 9, Visual design).
watch(
  () => session.user?.theme ?? 'system',
  (theme) => {
    applyTheme(theme)
    rememberTheme(theme)
  },
  { immediate: true },
)

// A profile change made offline goes out once sync works again.
watch(
  () => sync.state,
  (state) => {
    if (state === 'synced') void session.sendProfile()
  },
)
</script>

<template>
  <RouterView />
  <ConfirmDialog />
  <AppSnackbar />
</template>
