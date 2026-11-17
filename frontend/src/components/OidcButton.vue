<script setup lang="ts">
import { ref } from 'vue'
import { KeyRound } from '@lucide/vue'
import { useInstanceStore } from '@/stores/instance'
import UiButton from '@/components/ui/UiButton.vue'

/**
 * Starts single sign-on. The server redirects to the identity provider and back, so this is a
 * full page navigation rather than an API call.
 */
const props = defineProps<{ next?: unknown; link?: boolean }>()

const instance = useInstanceStore()
const leaving = ref(false)

function start(): void {
  const params = new URLSearchParams()
  if (typeof props.next === 'string' && props.next.startsWith('/')) params.set('next', props.next)
  if (props.link) params.set('link', '1')
  leaving.value = true
  window.location.assign(`/api/v1/auth/oidc/login?${params}`)
}
</script>

<template>
  <UiButton :loading="leaving" data-testid="oidc-button" @click="start">
    <KeyRound :size="16" />
    {{ $t(link ? 'oidc.link' : 'oidc.signIn', { provider: instance.config?.oidc_provider_name }) }}
  </UiButton>
</template>
