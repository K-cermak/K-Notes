<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, call } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import { useSessionStore } from '@/stores/session'
import AuthLayout from '@/components/AuthLayout.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const check = useSubmit()
const { pending, error, run } = useSubmit()

const token = String(route.params.token)
const email = ref<string | null>(null)
const checked = ref(false)
const password = ref('')
const attempted = ref(false)
const tooShort = computed(
  () => (attempted.value || password.value.length > 0) && password.value.length < 10,
)

onMounted(async () => {
  checked.value = await check.run(async () => {
    const info = await call(() =>
      api.POST('/api/v1/auth/password-reset/check', { body: { token } }),
    )
    email.value = info.email ?? null
  })
})

async function submit(): Promise<void> {
  attempted.value = true
  if (tooShort.value) {
    document.getElementById('reset-password')?.focus()
    return
  }
  const ok = await run(async () => {
    session.user = await call(() =>
      api.POST('/api/v1/auth/password-reset/complete', {
        body: { token, password: password.value },
      }),
    )
  })
  if (ok) await router.replace('/')
}
</script>

<template>
  <AuthLayout
    :title="$t('reset.title')"
    :description="checked && email ? $t('reset.description', { email }) : undefined"
  >
    <UiNotice v-if="check.error.value" tone="error">{{ check.error.value }}</UiNotice>
    <form v-else-if="checked" class="flex flex-col gap-5" novalidate @submit.prevent="submit">
      <input type="email" :value="email" autocomplete="username" hidden readonly />
      <UiField
        :label="$t('reset.newPassword')"
        for="reset-password"
        :hint="$t('account.passwordHint')"
        :error="tooShort ? $t('errors.password_too_short') : undefined"
      >
        <UiInput
          id="reset-password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          :invalid="tooShort"
          required
          autofocus
        />
      </UiField>
      <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
      <UiButton type="submit" variant="primary" :loading="pending">
        {{ $t('reset.submit') }}
      </UiButton>
    </form>
  </AuthLayout>
</template>
