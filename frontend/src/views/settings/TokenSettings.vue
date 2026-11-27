<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, Copy } from '@lucide/vue'
import { api, call } from '@/api/client'
import type { components } from '@/api/schema'
import { useSubmit } from '@/composables/useSubmit'
import { useConfirmStore } from '@/stores/confirm'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

type Token = components['schemas']['ApiTokenInfo']

const i18n = useI18n()
const confirm = useConfirmStore()
const tokens = ref<Token[]>([])
const name = ref('')
const scope = ref<'read' | 'write'>('read')
const expiry = ref<number | null>(90)
const created = ref<string | null>(null)
const copied = ref(false)
const action = useSubmit()

const EXPIRIES = [30, 90, 365, null] as const

async function load(): Promise<void> {
  tokens.value = await call(() => api.GET('/api/v1/me/tokens'))
}

async function create(): Promise<void> {
  copied.value = false
  await action.run(async () => {
    const token = await call(() =>
      api.POST('/api/v1/me/tokens', {
        body: { name: name.value.trim(), scope: scope.value, expires_in_days: expiry.value },
      }),
    )
    created.value = token.token
    name.value = ''
    await load()
  })
}

async function copy(): Promise<void> {
  if (!created.value) return
  await navigator.clipboard.writeText(created.value)
  copied.value = true
}

async function revoke(token: Token): Promise<void> {
  const sure = await confirm.ask({
    title: i18n.t('settings.tokens.revokeTitle', { name: token.name }),
    message: i18n.t('settings.tokens.revokeMessage'),
    confirmLabel: i18n.t('settings.tokens.revoke'),
    danger: true,
  })
  if (!sure) return
  await action.run(async () => {
    await call(() =>
      api.DELETE('/api/v1/me/tokens/{token_id}', { params: { path: { token_id: token.id } } }),
    )
    await load()
  })
}

function date(ms: number | null): string {
  return ms === null ? i18n.t('settings.tokens.never') : i18n.d(new Date(ms), 'date')
}

onMounted(load)
</script>

<template>
  <section class="flex flex-col gap-4">
    <h2 class="ui-section-title">{{ $t('settings.tokens.title') }}</h2>
    <p class="text-muted">
      {{ $t('settings.tokens.intro') }}
      <a
        href="/api/v1/docs"
        target="_blank"
        rel="noopener"
        class="font-medium text-ink underline underline-offset-2"
        data-testid="api-docs"
        >{{ $t('settings.tokens.docs') }}</a
      >
    </p>
    <form class="flex flex-col gap-4" @submit.prevent="create">
      <UiField :label="$t('settings.tokens.name')" for="token-name">
        <UiInput id="token-name" v-model="name" maxlength="100" autocomplete="off" />
      </UiField>
      <div class="flex flex-col gap-4 sm:flex-row">
        <fieldset class="flex flex-col gap-2">
          <legend class="ui-label mb-2">
            {{ $t('settings.tokens.scope') }}
          </legend>
          <label
            v-for="value in ['read', 'write'] as const"
            :key="value"
            class="flex cursor-pointer items-center gap-2"
          >
            <input
              v-model="scope"
              type="radio"
              name="token-scope"
              :value="value"
              class="ui-radio"
            />
            {{ $t(`settings.tokens.${value}`) }}
          </label>
        </fieldset>
        <UiField :label="$t('settings.tokens.expiry')" for="token-expiry">
          <select id="token-expiry" v-model="expiry" class="ui-select">
            <option v-for="days in EXPIRIES" :key="String(days)" :value="days">
              {{ days ? $t('settings.tokens.days', { count: days }) : $t('settings.tokens.never') }}
            </option>
          </select>
        </UiField>
      </div>
      <UiButton type="submit" variant="primary" class="self-start" :disabled="!name.trim()">
        {{ $t('settings.tokens.create') }}
      </UiButton>
    </form>
    <div v-if="created" class="flex flex-col gap-2" data-testid="new-token">
      <UiNotice tone="warning">{{ $t('settings.tokens.once') }}</UiNotice>
      <div class="flex gap-2">
        <UiInput :model-value="created" readonly class="ui-code" />
        <UiButton :aria-label="$t('admin.invite.copy')" icon-only @click="copy">
          <Check v-if="copied" class="text-success" />
          <Copy v-else />
        </UiButton>
      </div>
    </div>
    <UiNotice v-if="action.error.value" tone="error">{{ action.error.value }}</UiNotice>
    <ul v-if="tokens.length" class="border border-line" data-testid="tokens">
      <li
        v-for="token in tokens"
        :key="token.id"
        class="flex items-center gap-3 px-3 py-2.5 not-first:border-t not-first:border-line"
      >
        <div class="flex min-w-0 flex-1 flex-col">
          <span class="truncate">
            {{ token.name }}
            <span class="ui-badge ml-1">{{ $t(`settings.tokens.${token.scope}`) }}</span>
          </span>
          <span class="ui-meta">
            {{ token.prefix }}… ·
            {{ $t('settings.tokens.expires', { date: date(token.expires_at) }) }} ·
            {{
              token.last_used_at
                ? $t('settings.tokens.used', { date: date(token.last_used_at) })
                : $t('settings.tokens.unused')
            }}
          </span>
        </div>
        <UiButton size="sm" variant="ghost" @click="revoke(token)">
          {{ $t('settings.tokens.revoke') }}
        </UiButton>
      </li>
    </ul>
  </section>
</template>
