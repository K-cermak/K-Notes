<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatBytes } from '@/format'
import { LOCALES } from '@/i18n'
import type { components } from '@/api/schema'
import { useSessionStore } from '@/stores/session'
import { useSnackbarStore } from '@/stores/snackbar'
import { useSyncStore } from '@/stores/sync'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

type ProfileUpdate = components['schemas']['ProfileUpdate']

const { t } = useI18n()
const session = useSessionStore()
const sync = useSyncStore()
const snackbar = useSnackbarStore()
const storage = computed(() => sync.storage)
const share = computed(() => {
  const s = storage.value
  return s?.limit_bytes ? Math.min(1, s.used_bytes / Math.max(s.limit_bytes, 1)) : 0
})
onMounted(() => sync.syncNow())
const name = ref(session.user?.display_name ?? '')

const views = computed(() => [
  { value: 'grid' as const, label: t('settings.profile.grid') },
  { value: 'list' as const, label: t('settings.profile.list') },
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
    <div v-if="storage" class="flex flex-col gap-2" data-testid="storage-use">
      <span class="ui-label">{{ $t('storage.title') }}</span>
      <span class="ui-numeric">
        {{
          storage.limit_bytes === null
            ? $t('storage.usedUnlimited', { used: formatBytes(storage.used_bytes) })
            : $t('storage.used', {
                used: formatBytes(storage.used_bytes),
                limit: formatBytes(storage.limit_bytes),
              })
        }}
      </span>
      <div
        v-if="storage.limit_bytes !== null"
        class="ui-meter"
        :class="storage.full && 'ui-meter--full'"
        role="meter"
        :aria-valuenow="Math.round(share * 100)"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="$t('storage.title')"
      >
        <div class="ui-meter__bar" :style="{ width: `${share * 100}%` }" />
      </div>
      <p v-if="storage.full" class="text-label text-danger">{{ $t('storage.fullNotice') }}</p>
    </div>
  </section>
</template>
