<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, call } from '@/api/client'
import { useSubmit } from '@/composables/useSubmit'
import { useSessionStore } from '@/stores/session'
import AccountForm from '@/components/AccountForm.vue'
import AuthLayout from '@/components/AuthLayout.vue'

const router = useRouter()
const session = useSessionStore()
const { pending, error, attempt } = useSubmit()

const email = ref('')
const displayName = ref('')
const password = ref('')

async function submit(): Promise<void> {
  const me = await attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/register', {
        body: { email: email.value, display_name: displayName.value, password: password.value },
      }),
    ),
  )
  if (me && (await session.signedIn(me))) {
    await router.replace('/')
  }
}
</script>

<template>
  <AuthLayout :title="$t('register.title')">
    <AccountForm
      v-model:email="email"
      v-model:display-name="displayName"
      v-model:password="password"
      :submit-label="$t('register.submit')"
      :pending="pending"
      :error="error"
      @submit="submit"
    />
    <p class="text-muted">
      {{ $t('register.haveAccount') }}
      <RouterLink to="/login" class="font-medium text-accent">{{ $t('login.submit') }}</RouterLink>
    </p>
  </AuthLayout>
</template>
