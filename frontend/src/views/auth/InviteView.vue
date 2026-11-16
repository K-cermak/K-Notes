<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, call } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import { useSessionStore } from '@/stores/session'
import AccountForm from '@/components/AccountForm.vue'
import AuthLayout from '@/components/AuthLayout.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const check = useSubmit()
const { pending, error, attempt } = useSubmit()

const token = String(route.params.token)
const checked = ref(false)
const fixedEmail = ref<string | null>(null)
const email = ref('')
const displayName = ref('')
const password = ref('')

onMounted(async () => {
  const ok = await check.run(async () => {
    const info = await call(() => api.POST('/api/v1/auth/invite/check', { body: { token } }))
    fixedEmail.value = info.email ?? null
  })
  checked.value = ok
})

async function submit(): Promise<void> {
  const me = await attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/invite/accept', {
        body: {
          token,
          email: fixedEmail.value ?? email.value,
          display_name: displayName.value,
          password: password.value,
        },
      }),
    ),
  )
  if (me && (await session.signedIn(me))) {
    await router.replace('/')
  }
}
</script>

<template>
  <AuthLayout
    :title="$t('invite.title')"
    :description="checked ? $t('invite.description') : undefined"
  >
    <UiNotice v-if="check.error.value" tone="error">{{ check.error.value }}</UiNotice>
    <AccountForm
      v-else-if="checked"
      v-model:email="email"
      v-model:display-name="displayName"
      v-model:password="password"
      :fixed-email="fixedEmail"
      :submit-label="$t('invite.submit')"
      :pending="pending"
      :error="error"
      @submit="submit"
    />
  </AuthLayout>
</template>
