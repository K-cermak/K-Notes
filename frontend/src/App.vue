<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { setLucideProps } from '@lucide/vue'
import AppSnackbar from '@/components/AppSnackbar.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { applyLocale, applyTimeFormat } from '@/i18n'
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
const route = useRoute()
const router = useRouter()

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

// The session is checked in the background after an offline-first start; if it ends up signed
// out, the page the user was on can no longer be shown.
watch(
  () => session.user,
  (user, previous) => {
    if (!user && previous && !route.meta.public) void router.replace({ name: 'login' })
  },
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

watch(() => session.user?.locale, applyLocale, { immediate: true })
watch(() => session.user?.time_format, applyTimeFormat, { immediate: true })

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
