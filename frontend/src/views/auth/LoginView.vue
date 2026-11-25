<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, call, type Me } from '@/api/client'
import { useCaptcha } from '@/composables/useCaptcha'
import { useSubmit } from '@/composables/useSubmit'
import { afterSignIn } from '@/router'
import { useInstanceStore } from '@/stores/instance'
import { useSessionStore } from '@/stores/session'
import AuthLayout from '@/components/AuthLayout.vue'
import CaptchaFrame from '@/components/CaptchaFrame.vue'
import OidcButton from '@/components/OidcButton.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const route = useRoute()
const router = useRouter()
const i18n = useI18n()
const instance = useInstanceStore()
const session = useSessionStore()
const { pending, error, failure, attempt } = useSubmit({ unauthorized: 'login.invalid' })
const second = useSubmit({ unauthorized: 'login.invalidCode' })
const { config: captcha, token: captchaToken, afterFailure } = useCaptcha('login')

const email = ref('')
const password = ref('')
// With two-factor on, the password step returns a pending token for the code step (SPEC 7).
const pendingToken = ref<string | null>(null)
const code = ref('')
const codeField = ref<{ focus: () => void } | null>(null)

const passwordLogin = computed(() => instance.config?.password_login_enabled ?? true)
// An OIDC sign-in that failed comes back here with ?error=<code>.
const redirectError = computed(() => {
  const code = route.query.error
  if (typeof code !== 'string') return null
  return i18n.te(`errors.${code}`) ? i18n.t(`errors.${code}`) : i18n.t('errors.unknown')
})

async function finish(me: Me): Promise<void> {
  if (await session.signedIn(me)) await router.replace(afterSignIn(route.query.next))
}

async function submit(): Promise<void> {
  const result = await attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/login', {
        body: { email: email.value, password: password.value, captcha_token: captchaToken.value },
      }),
    ),
  )
  if (!result) {
    await afterFailure(failure.value)
    return
  }
  if ('pending_token' in result) {
    // The token is spent; going back to the password step shows a fresh captcha.
    captchaToken.value = null
    pendingToken.value = result.pending_token
    await nextTick()
    codeField.value?.focus()
    return
  }
  await finish(result)
}

async function submitCode(): Promise<void> {
  const token = pendingToken.value
  if (!token) return
  const me = await second.attempt(() =>
    call(() =>
      api.POST('/api/v1/auth/login/totp', { body: { pending_token: token, code: code.value } }),
    ),
  )
  if (me) await finish(me)
  else if (second.failure.value?.code === 'login_expired') pendingToken.value = null
}
</script>

<template>
  <AuthLayout :title="$t(pendingToken ? 'login.codeTitle' : 'login.title')">
    <UiNotice v-if="redirectError" tone="error">{{ redirectError }}</UiNotice>
    <form
      v-if="pendingToken"
      class="flex flex-col gap-5"
      novalidate
      data-testid="totp-step"
      @submit.prevent="submitCode"
    >
      <p class="text-muted">{{ $t('login.codeHint') }}</p>
      <UiField :label="$t('login.code')" for="login-code">
        <UiInput
          id="login-code"
          ref="codeField"
          v-model="code"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="32"
          required
        />
      </UiField>
      <UiNotice v-if="second.error.value" tone="error">{{ second.error.value }}</UiNotice>
      <UiButton type="submit" variant="primary" :loading="second.pending.value">
        {{ $t('login.verify') }}
      </UiButton>
      <button
        type="button"
        class="cursor-pointer self-start font-medium text-accent"
        @click="((pendingToken = null), (code = ''))"
      >
        {{ $t('common.back') }}
      </button>
    </form>
    <template v-else>
      <form v-if="passwordLogin" class="flex flex-col gap-5" novalidate @submit.prevent="submit">
        <UiField :label="$t('account.email')" for="login-email">
          <UiInput
            id="login-email"
            v-model="email"
            type="email"
            autocomplete="username"
            required
            autofocus
          />
        </UiField>
        <UiField :label="$t('account.password')" for="login-password">
          <UiInput
            id="login-password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
          />
        </UiField>
        <CaptchaFrame
          v-if="captcha"
          ref="captchaFrame"
          v-model="captchaToken"
          :provider="captcha.provider"
          :site-key="captcha.site_key"
        />
        <UiNotice v-if="error" tone="error">{{ error }}</UiNotice>
        <UiButton type="submit" variant="primary" :loading="pending">
          {{ $t('login.submit') }}
        </UiButton>
      </form>
      <OidcButton v-if="instance.config?.oidc_enabled" :next="route.query.next" />
      <div class="flex flex-col gap-2 text-muted">
        <p v-if="passwordLogin">{{ $t('login.forgot') }}</p>
        <p v-if="instance.config?.registration_open && passwordLogin">
          {{ $t('login.noAccount') }}
          <RouterLink to="/register" class="font-medium text-accent">
            {{ $t('register.submit') }}
          </RouterLink>
        </p>
      </div>
    </template>
  </AuthLayout>
</template>
