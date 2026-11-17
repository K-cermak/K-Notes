<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { formatBytes } from '@/format'
import { LOCALES } from '@/i18n'
import { useSessionStore } from '@/stores/session'
import { useSyncStore } from '@/stores/sync'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const session = useSessionStore()
const sync = useSyncStore()
const storage = computed(() => sync.storage)
const share = computed(() => {
  const s = storage.value
  return s?.limit_bytes ? Math.min(1, s.used_bytes / Math.max(s.limit_bytes, 1)) : 0
})
onMounted(() => sync.syncNow())
const name = ref(session.user?.display_name ?? '')
const saved = ref(false)
watch(name, () => (saved.value = false))

async function saveName(): Promise<void> {
  const trimmed = name.value.trim()
  if (!trimmed) return
  await session.updateProfile({ display_name: trimmed })
  saved.value = true
}
</script>

<template>
  <section class="flex flex-col gap-5">
    <h2 class="text-base">{{ $t('settings.profile.title') }}</h2>
    <form class="flex flex-col gap-3 sm:flex-row sm:items-end" @submit.prevent="saveName">
      <UiField :label="$t('account.displayName')" for="profile-name" class="flex-1">
        <UiInput id="profile-name" v-model="name" maxlength="100" autocomplete="name" />
      </UiField>
      <UiButton
        type="submit"
        :disabled="!name.trim() || name.trim() === session.user?.display_name"
      >
        {{ $t('common.save') }}
      </UiButton>
    </form>
    <UiNotice v-if="saved" tone="success">{{ $t('settings.profile.saved') }}</UiNotice>
    <UiField :label="$t('account.email')" for="profile-email">
      <UiInput id="profile-email" :model-value="session.user?.email" disabled />
    </UiField>
    <UiField :label="$t('settings.profile.language')" for="profile-language">
      <select
        id="profile-language"
        class="h-10 w-full cursor-pointer border border-line bg-bg px-3 text-sm text-ink hover:border-line-hover focus:border-ink focus:outline-none sm:w-60"
        :value="session.user?.locale"
        @change="session.updateProfile({ locale: ($event.target as HTMLSelectElement).value })"
      >
        <option v-for="(label, code) in LOCALES" :key="code" :value="code">{{ label }}</option>
      </select>
    </UiField>
    <div class="flex flex-col gap-2">
      <span class="text-label font-medium text-muted">{{ $t('theme.label') }}</span>
      <ThemeSwitch
        :model-value="session.user?.theme ?? 'system'"
        @update:model-value="(theme) => session.updateProfile({ theme })"
      />
    </div>
    <div v-if="storage" class="flex flex-col gap-2" data-testid="storage-use">
      <span class="text-label font-medium text-muted">{{ $t('storage.title') }}</span>
      <span class="font-mono text-meta tabular-nums">
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
        class="h-1 w-full max-w-80 bg-line"
        role="meter"
        :aria-valuenow="Math.round(share * 100)"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="$t('storage.title')"
      >
        <div
          class="h-full"
          :class="storage.full ? 'bg-danger' : 'bg-ink'"
          :style="{ width: `${share * 100}%` }"
        />
      </div>
      <p v-if="storage.full" class="text-label text-danger">{{ $t('storage.fullNotice') }}</p>
    </div>
    <div class="flex flex-col gap-2">
      <span class="text-label font-medium text-muted">{{ $t('settings.profile.view') }}</span>
      <div role="radiogroup" class="inline-flex self-start border border-line">
        <button
          v-for="view in ['grid', 'list'] as const"
          :key="view"
          type="button"
          role="radio"
          :aria-checked="session.user?.default_view === view"
          class="h-8 cursor-pointer px-3 text-muted not-first:border-l not-first:border-line hover:text-ink aria-checked:bg-[color-mix(in_srgb,var(--ink)_6%,var(--bg))] aria-checked:text-ink"
          @click="session.updateProfile({ default_view: view })"
        >
          {{ $t(view === 'grid' ? 'settings.profile.grid' : 'settings.profile.list') }}
        </button>
      </div>
    </div>
  </section>
</template>
