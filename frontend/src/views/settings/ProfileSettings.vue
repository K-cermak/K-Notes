<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LOCALES } from '@/i18n'
import type { components } from '@/api/schema'
import { useSessionStore } from '@/stores/session'
import { useSnackbarStore } from '@/stores/snackbar'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

type ProfileUpdate = components['schemas']['ProfileUpdate']

const { t } = useI18n()
const session = useSessionStore()
const snackbar = useSnackbarStore()
const name = ref(session.user?.display_name ?? '')

const views = computed(() => [
  { value: 'grid' as const, label: t('settings.profile.grid') },
  { value: 'list' as const, label: t('settings.profile.list') },
])

const timeFormats = computed(() => [
  { value: '24h' as const, label: t('settings.profile.hours24') },
  { value: '12h' as const, label: t('settings.profile.hours12') },
])

// Applied at once and kept on this device until the server has it, so it counts as saved offline too.
async function update(patch: ProfileUpdate): Promise<void> {
  await session.updateProfile(patch)
  snackbar.show(t('common.saved'))
}

async function saveName(): Promise<void> {
  const trimmed = name.value.trim()
  if (trimmed) await update({ display_name: trimmed })
}
</script>

<template>
  <section class="flex flex-col gap-5">
    <h2 class="ui-section-title">{{ $t('settings.profile.title') }}</h2>
    <form @submit.prevent="saveName">
      <UiField :label="$t('account.displayName')" for="profile-name">
        <div class="ui-input-row">
          <UiInput id="profile-name" v-model="name" maxlength="100" autocomplete="name" />
          <UiButton
            type="submit"
            :disabled="!name.trim() || name.trim() === session.user?.display_name"
          >
            {{ $t('common.save') }}
          </UiButton>
        </div>
      </UiField>
    </form>
    <UiField :label="$t('account.email')" for="profile-email">
      <UiInput id="profile-email" :model-value="session.user?.email" disabled />
    </UiField>
    <UiField :label="$t('settings.profile.language')" for="profile-language">
      <select
        id="profile-language"
        class="ui-select"
        :value="session.user?.locale"
        @change="update({ locale: ($event.target as HTMLSelectElement).value })"
      >
        <option v-for="(label, code) in LOCALES" :key="code" :value="code">{{ label }}</option>
      </select>
    </UiField>
    <div class="flex flex-col gap-2">
      <span class="ui-label">{{ $t('theme.label') }}</span>
      <ThemeSwitch
        :model-value="session.user?.theme ?? 'system'"
        @update:model-value="(theme) => update({ theme })"
      />
    </div>
    <div class="flex flex-col gap-2">
      <span class="ui-label">{{ $t('settings.profile.view') }}</span>
      <UiSegmented
        :model-value="session.user?.default_view ?? 'grid'"
        :options="views"
        :label="$t('settings.profile.view')"
        @update:model-value="(view) => update({ default_view: view })"
      />
    </div>
    <div class="flex flex-col gap-2">
      <span class="ui-label">{{ $t('settings.profile.timeFormat') }}</span>
      <UiSegmented
        :model-value="session.user?.time_format ?? '24h'"
        :options="timeFormats"
        :label="$t('settings.profile.timeFormat')"
        @update:model-value="(format) => update({ time_format: format })"
      />
    </div>
  </section>
</template>
