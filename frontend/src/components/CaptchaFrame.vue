<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { isCaptchaMessage, type CaptchaProvider } from '@/captcha/protocol'
import { useMediaQuery } from '@/composables/useMediaQuery'
import UiNotice from '@/components/ui/UiNotice.vue'

/** The captcha widget, in the frame at /captcha.html; the solved token arrives through v-model. */
const props = defineProps<{ provider: CaptchaProvider; siteKey: string }>()
const token = defineModel<string | null>({ default: null })

const i18n = useI18n()
const frame = ref<HTMLIFrameElement | null>(null)
// Remounting the frame is the one reset that works the same for every provider.
const generation = ref(0)
const height = ref(props.provider === 'altcha' ? 80 : 78)
const failed = ref(false)
const systemDark = useMediaQuery('(prefers-color-scheme: dark)')

const src = computed(() => {
  const explicit = document.documentElement.dataset.theme
  const theme = explicit ?? (systemDark.value ? 'dark' : 'light')
  const query = new URLSearchParams({
    provider: props.provider,
    sitekey: props.siteKey,
    theme,
    lang: i18n.locale.value,
  })
  return `/captcha.html?${query}`
})

function onMessage(event: MessageEvent): void {
  if (event.origin !== location.origin || event.source !== frame.value?.contentWindow) return
  const message: unknown = event.data
  if (!isCaptchaMessage(message)) return
  if (message.type === 'token') {
    token.value = message.token
    failed.value = false
  } else if (message.type === 'size') {
    if (message.height > 0) height.value = message.height
  } else {
    token.value = null
    failed.value = true
  }
}

function reset(): void {
  token.value = null
  failed.value = false
  generation.value++
}

onMounted(() => window.addEventListener('message', onMessage))
onUnmounted(() => window.removeEventListener('message', onMessage))

defineExpose({ reset })
</script>

<template>
  <div class="flex flex-col gap-2">
    <iframe
      :key="`${generation}-${src}`"
      ref="frame"
      :src="src"
      :title="$t('captcha.title')"
      class="block w-full border-0"
      :style="{ height: `${height}px` }"
      data-testid="captcha-frame"
    />
    <UiNotice v-if="failed" tone="error">
      {{ $t('captcha.failed') }}
      <button type="button" class="cursor-pointer font-medium text-accent" @click="reset">
        {{ $t('captcha.retry') }}
      </button>
    </UiNotice>
  </div>
</template>
