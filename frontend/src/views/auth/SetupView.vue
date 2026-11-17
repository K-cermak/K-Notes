<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import branding from '@branding'
import { api, call } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import { useInstanceStore } from '@/stores/instance'
import { useSessionStore } from '@/stores/session'
import AccountForm from '@/components/AccountForm.vue'
import AuthLayout from '@/components/AuthLayout.vue'
import OidcButton from '@/components/OidcButton.vue'

const router = useRouter()
const instance = useInstanceStore()
const session = useSessionStore()
const { pending, error, attempt } = useSubmit()

const email = ref('')
const displayName = ref('')
const password = ref('')

async function submit(): Promise<void> {
  const me = await attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/setup', {
        body: { email: email.value, display_name: displayName.value, password: password.value },
      }),
    ),
  )
  if (me && (await session.signedIn(me))) {
    await instance.load()
    await router.replace('/')
  }
}
</script>

<template>
  <AuthLayout
    :title="$t('setup.title', { name: branding.name })"
    :description="
      $t(
        instance.config?.password_login_enabled === false
          ? 'setup.ssoDescription'
          : 'setup.description',
      )
    "
  >
    <!-- With password sign-in off, the first person through single sign-on becomes the admin. -->
    <OidcButton v-if="instance.config?.password_login_enabled === false" />
    <AccountForm
      v-else
      v-model:email="email"
      v-model:display-name="displayName"
      v-model:password="password"
      :submit-label="$t('setup.submit')"
      :pending="pending"
      :error="error"
      @submit="submit"
    />
  </AuthLayout>
</template>
