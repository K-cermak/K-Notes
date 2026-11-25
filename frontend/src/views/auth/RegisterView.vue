<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, call } from '@/api/client'
import { useCaptcha } from '@/composables/useCaptcha'
import { useSubmit } from '@/composables/useSubmit'
import { useSessionStore } from '@/stores/session'
import AccountForm from '@/components/AccountForm.vue'
import AuthLayout from '@/components/AuthLayout.vue'
import CaptchaFrame from '@/components/CaptchaFrame.vue'

const router = useRouter()
const session = useSessionStore()
const { pending, error, failure, attempt } = useSubmit()
const { config: captcha, token: captchaToken, afterFailure } = useCaptcha('registration')

const email = ref('')
const displayName = ref('')
const password = ref('')

async function submit(): Promise<void> {
  const me = await attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/register', {
        body: {
          email: email.value,
          display_name: displayName.value,
          password: password.value,
          captcha_token: captchaToken.value,
        },
      }),
    ),
  )
  if (!me) await afterFailure(failure.value)
  else if (await session.signedIn(me)) await router.replace('/')
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
    >
      <CaptchaFrame
        v-if="captcha"
        ref="captchaFrame"
        v-model="captchaToken"
        :provider="captcha.provider"
        :site-key="captcha.site_key"
      />
    </AccountForm>
    <p class="text-muted">
      {{ $t('register.haveAccount') }}
      <RouterLink to="/login" class="font-medium text-accent">{{ $t('login.submit') }}</RouterLink>
    </p>
  </AuthLayout>
</template>
