<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { api, call } from '@/api/client'
import type { components } from '@/api/schema'
import { useSubmit } from '@/composables/useSubmit'
import { useInstanceStore } from '@/stores/instance'
import { useSessionStore } from '@/stores/session'
import OidcButton from '@/components/OidcButton.vue'
import QrCode from '@/components/QrCode.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

type Schemas = components['schemas']

const i18n = useI18n()
const route = useRoute()
const session = useSessionStore()
const instance = useInstanceStore()
const user = computed(() => session.user)

// Password
const currentPassword = ref('')
const newPassword = ref('')
const passwordChanged = ref(false)
const password = useSubmit({ wrong_password: 'errors.wrong_password' })

async function changePassword(): Promise<void> {
  passwordChanged.value = false
  const ok = await password.run(() =>
    call(() =>
      api.POST('/api/v1/me/password', {
        body: { current_password: currentPassword.value, new_password: newPassword.value },
      }),
    ),
  )
  if (!ok) return
  currentPassword.value = newPassword.value = ''
  passwordChanged.value = true
}

// Two-step verification (SPEC 7, TOTP)
const totp = ref<Schemas['TotpStatus'] | null>(null)
const enrolment = ref<Schemas['TotpSetup'] | null>(null)
const recoveryCodes = ref<string[] | null>(null)
const code = ref('')
const disablePassword = ref('')
const turningOff = ref(false)
const renewing = ref(false)
const twoStep = useSubmit()

async function loadTotp(): Promise<void> {
  totp.value = await call(() => api.GET('/api/v1/me/totp'))
}

async function startEnrolment(): Promise<void> {
  await twoStep.run(async () => {
    enrolment.value = await call(() => api.POST('/api/v1/me/totp/setup'))
  })
}

async function confirmEnrolment(): Promise<void> {
  await twoStep.run(async () => {
    const result = await call(() =>
      api.POST('/api/v1/me/totp/enable', { body: { code: code.value } }),
    )
    recoveryCodes.value = result.codes
    enrolment.value = null
    code.value = ''
    await Promise.all([loadTotp(), session.load()])
  })
}

async function renewCodes(): Promise<void> {
  await twoStep.run(async () => {
    const result = await call(() =>
      api.POST('/api/v1/me/totp/recovery-codes', { body: { code: code.value } }),
    )
    recoveryCodes.value = result.codes
    renewing.value = false
    code.value = ''
    await loadTotp()
  })
}

async function turnOff(): Promise<void> {
  await twoStep.run(async () => {
    await call(() =>
      api.POST('/api/v1/me/totp/disable', {
        body: { password: disablePassword.value, code: code.value },
      }),
    )
    turningOff.value = false
    code.value = disablePassword.value = ''
    await Promise.all([loadTotp(), session.load()])
  })
}

function cancelTotp(): void {
  enrolment.value = null
  turningOff.value = renewing.value = false
  code.value = disablePassword.value = ''
  twoStep.error.value = null
}

// Single sign-on, with the outcome of a link attempt coming back as a query parameter.
const sso = useSubmit()
const ssoMessage = computed(() => {
  if (route.query.linked) return { tone: 'success' as const, text: i18n.t('settings.sso.linked') }
  const error = route.query.error
  if (typeof error !== 'string') return null
  const key = `errors.${error}`
  return { tone: 'error' as const, text: i18n.te(key) ? i18n.t(key) : i18n.t('errors.unknown') }
})

async function unlink(): Promise<void> {
  const ok = await sso.run(() => call(() => api.DELETE('/api/v1/me/oidc')))
  if (ok) await session.load()
}

// Sessions
const sessions = ref<Schemas['SessionInfo'][]>([])
const sessionAction = useSubmit()

async function loadSessions(): Promise<void> {
  sessions.value = await call(() => api.GET('/api/v1/me/sessions'))
}

async function revoke(id: string): Promise<void> {
  await sessionAction.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/me/sessions/{session_id}', { params: { path: { session_id: id } } }),
    )
    await loadSessions()
  })
}

async function revokeOthers(): Promise<void> {
  await sessionAction.run(async () => {
    await call(() => api.DELETE('/api/v1/me/sessions'))
    await loadSessions()
  })
}

function when(ms: number): string {
  return i18n.d(new Date(ms), 'dateTime')
}

function device(agent: string | null): string {
  if (!agent) return i18n.t('settings.sessions.unknown')
  const browser = /Firefox|Edg|Chrome|Safari/.exec(agent)?.[0]?.replace('Edg', 'Edge')
  const system = /Android|iPhone|iPad|Mac OS X|Windows|Linux/
    .exec(agent)?.[0]
    ?.replace('Mac OS X', 'macOS')
  return [browser, system].filter(Boolean).join(', ') || agent.slice(0, 60)
}

onMounted(async () => {
  await Promise.all([loadTotp(), loadSessions()])
})
</script>

<template>
  <section v-if="user?.has_password" class="flex flex-col gap-4">
    <h2 class="ui-section-title">{{ $t('settings.password.title') }}</h2>
    <form class="flex flex-col gap-4" novalidate @submit.prevent="changePassword">
      <UiField :label="$t('settings.password.current')" for="password-current">
        <UiInput
          id="password-current"
          v-model="currentPassword"
          type="password"
          autocomplete="current-password"
        />
      </UiField>
      <UiField
        :label="$t('settings.password.new')"
        for="password-new"
        :hint="$t('account.passwordHint')"
      >
        <UiInput
          id="password-new"
          v-model="newPassword"
          type="password"
          autocomplete="new-password"
        />
      </UiField>
      <UiNotice v-if="password.error.value" tone="error">{{ password.error.value }}</UiNotice>
      <UiNotice v-if="passwordChanged" tone="success">{{
        $t('settings.password.changed')
      }}</UiNotice>
      <UiButton
        type="submit"
        class="self-start"
        :loading="password.pending.value"
        :disabled="!currentPassword || !newPassword"
      >
        {{ $t('settings.password.submit') }}
      </UiButton>
    </form>
  </section>

  <section v-if="user?.has_password" class="flex flex-col gap-4" data-testid="totp-settings">
    <h2 class="ui-section-title">{{ $t('settings.totp.title') }}</h2>
    <p class="text-muted">{{ $t('settings.totp.intro') }}</p>

    <div v-if="recoveryCodes" class="flex flex-col gap-3" data-testid="recovery-codes">
      <UiNotice tone="warning">{{ $t('settings.totp.saveCodes') }}</UiNotice>
      <ul class="ui-code grid grid-cols-2 gap-x-6 gap-y-1 border border-line p-4">
        <li v-for="item in recoveryCodes" :key="item">{{ item }}</li>
      </ul>
      <UiButton class="self-start" @click="recoveryCodes = null">{{ $t('common.done') }}</UiButton>
    </div>

    <template v-else-if="enrolment">
      <ol class="flex list-decimal flex-col gap-4 pl-5">
        <li>
          {{ $t('settings.totp.scan') }}
          <div class="mt-3 flex flex-col gap-2">
            <QrCode :value="enrolment.uri" :label="$t('settings.totp.qr')" />
            <p class="ui-meta">{{ $t('settings.totp.manual') }}</p>
            <code class="ui-code break-all" data-testid="totp-secret">{{ enrolment.secret }}</code>
          </div>
        </li>
        <li>
          <form class="flex flex-col gap-3" @submit.prevent="confirmEnrolment">
            <UiField :label="$t('settings.totp.enterCode')" for="totp-code">
              <UiInput
                id="totp-code"
                v-model="code"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="6"
                class="sm:w-40"
              />
            </UiField>
            <div class="flex gap-2">
              <UiButton type="submit" variant="primary" :loading="twoStep.pending.value">
                {{ $t('settings.totp.confirm') }}
              </UiButton>
              <UiButton variant="ghost" @click="cancelTotp">{{ $t('common.cancel') }}</UiButton>
            </div>
          </form>
        </li>
      </ol>
    </template>

    <template v-else-if="totp?.enabled">
      <p class="flex items-center gap-2">
        <span class="ui-badge ui-badge--success">{{ $t('settings.totp.on') }}</span>
        <span class="text-label text-muted">{{
          $t(
            'settings.totp.codesLeft',
            { count: totp.recovery_codes_left },
            totp.recovery_codes_left,
          )
        }}</span>
      </p>
      <form
        v-if="turningOff || renewing"
        class="flex flex-col gap-3"
        @submit.prevent="turningOff ? turnOff() : renewCodes()"
      >
        <UiField v-if="turningOff" :label="$t('account.password')" for="totp-password">
          <UiInput
            id="totp-password"
            v-model="disablePassword"
            type="password"
            autocomplete="current-password"
          />
        </UiField>
        <UiField :label="$t('settings.totp.codeOrRecovery')" for="totp-current">
          <UiInput id="totp-current" v-model="code" autocomplete="one-time-code" class="sm:w-60" />
        </UiField>
        <div class="flex gap-2">
          <UiButton
            type="submit"
            :variant="turningOff ? 'danger' : 'primary'"
            :loading="twoStep.pending.value"
          >
            {{ $t(turningOff ? 'settings.totp.turnOff' : 'settings.totp.renew') }}
          </UiButton>
          <UiButton variant="ghost" @click="cancelTotp">{{ $t('common.cancel') }}</UiButton>
        </div>
      </form>
      <div v-else class="flex flex-wrap gap-2">
        <UiButton @click="renewing = true">{{ $t('settings.totp.renew') }}</UiButton>
        <UiButton variant="danger" @click="turningOff = true">
          {{ $t('settings.totp.turnOff') }}
        </UiButton>
      </div>
    </template>

    <UiButton
      v-else
      class="self-start"
      :loading="twoStep.pending.value"
      data-testid="totp-start"
      @click="startEnrolment"
    >
      {{ $t('settings.totp.setUp') }}
    </UiButton>
    <UiNotice v-if="twoStep.error.value" tone="error">{{ twoStep.error.value }}</UiNotice>
  </section>

  <section v-if="instance.config?.oidc_enabled" class="flex flex-col gap-4">
    <h2 class="ui-section-title">
      {{ $t('settings.sso.title', { provider: instance.config.oidc_provider_name }) }}
    </h2>
    <UiNotice v-if="ssoMessage" :tone="ssoMessage.tone">{{ ssoMessage.text }}</UiNotice>
    <template v-if="user?.oidc_linked">
      <p class="text-muted">
        {{ $t('settings.sso.isLinked', { provider: instance.config.oidc_provider_name }) }}
      </p>
      <UiButton
        class="self-start"
        :disabled="!user.has_password || !instance.config.password_login_enabled"
        :loading="sso.pending.value"
        @click="unlink"
      >
        {{ $t('settings.sso.unlink') }}
      </UiButton>
      <p
        v-if="!user.has_password || !instance.config.password_login_enabled"
        class="text-label text-muted"
      >
        {{ $t('settings.sso.onlyWay') }}
      </p>
    </template>
    <template v-else>
      <p class="text-muted">
        {{ $t('settings.sso.notLinked', { provider: instance.config.oidc_provider_name }) }}
      </p>
      <OidcButton link class="self-start" />
    </template>
    <UiNotice v-if="sso.error.value" tone="error">{{ sso.error.value }}</UiNotice>
  </section>

  <section class="flex flex-col gap-4">
    <div class="flex items-center justify-between gap-4">
      <h2 class="ui-section-title">{{ $t('settings.sessions.title') }}</h2>
      <UiButton v-if="sessions.length > 1" size="sm" @click="revokeOthers">
        {{ $t('settings.sessions.signOutOthers') }}
      </UiButton>
    </div>
    <ul class="border border-line" data-testid="sessions">
      <li
        v-for="item in sessions"
        :key="item.id"
        class="flex items-center gap-3 px-3 py-2.5 not-first:border-t not-first:border-line"
      >
        <div class="flex min-w-0 flex-1 flex-col">
          <span class="truncate">
            {{ device(item.user_agent) }}
            <span v-if="item.current" class="ml-1 text-label text-success">{{
              $t('settings.sessions.current')
            }}</span>
          </span>
          <span class="ui-meta">
            {{ $t('settings.sessions.lastUsed', { time: when(item.last_used_at) }) }}
            <template v-if="item.ip"> · {{ item.ip }}</template>
            <template v-if="item.auth_method === 'oidc'"> · SSO</template>
          </span>
        </div>
        <UiButton v-if="!item.current" size="sm" variant="ghost" @click="revoke(item.id)">
          {{ $t('settings.sessions.signOut') }}
        </UiButton>
      </li>
    </ul>
    <UiNotice v-if="sessionAction.error.value" tone="error">{{
      sessionAction.error.value
    }}</UiNotice>
  </section>
</template>
