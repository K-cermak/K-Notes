<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Archive, ArrowRight, Palette, Pin, Trash2 } from '@lucide/vue'
import { applyTheme, parseTheme, type Theme } from '@/theme'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const route = useRoute()
const router = useRouter()

// ?theme=dark makes side-by-side screenshots against the reference form easy.
const theme = ref<Theme>(parseTheme(route.query.theme) ?? 'system')
watch(
  theme,
  (value) => {
    applyTheme(value)
    void router.replace({ query: value === 'system' ? {} : { theme: value } })
  },
  { immediate: true },
)
onBeforeUnmount(() => applyTheme('system'))

const email = ref('')
const password = ref('short')
const displayName = ref('Alex')
const message = ref('')
const milk = ref(true)
const bread = ref(false)

const tokens = [
  'bg',
  'ink',
  'muted',
  'faint',
  'line',
  'line-hover',
  'accent',
  'accent-hover',
  'danger',
  'warning',
  'success',
]
const palette = [
  'default',
  'coral',
  'peach',
  'sand',
  'mint',
  'sage',
  'fog',
  'storm',
  'dusk',
  'blossom',
  'clay',
  'chalk',
]
</script>

<template>
  <main class="mx-auto flex max-w-[560px] flex-col gap-10 px-4 py-6 sm:px-0 sm:py-10">
    <header class="flex items-start justify-between gap-4">
      <div class="flex flex-col gap-1">
        <h1 class="text-xl leading-tight">{{ $t('showcase.title') }}</h1>
        <p class="text-muted">{{ $t('showcase.intro') }}</p>
      </div>
      <ThemeSwitch v-model="theme" />
    </header>

    <section class="flex flex-col gap-4">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.typography') }}
      </h2>
      <div class="flex flex-col gap-1 border border-line p-4">
        <p class="text-base font-semibold tracking-[-0.02em]">{{ $t('showcase.headingSample') }}</p>
        <p>{{ $t('showcase.bodySample') }}</p>
        <p class="font-mono text-meta text-muted tabular-nums">{{ $t('showcase.metaSample') }}</p>
      </div>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.buttons') }}
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <UiButton variant="primary">{{ $t('showcase.primary') }}</UiButton>
        <UiButton>{{ $t('showcase.secondary') }}</UiButton>
        <UiButton variant="ghost">{{ $t('showcase.ghost') }}</UiButton>
        <UiButton variant="danger">
          <Trash2 :size="16" />
          {{ $t('showcase.danger') }}
        </UiButton>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <UiButton variant="primary" disabled>{{ $t('showcase.disabled') }}</UiButton>
        <UiButton variant="primary" loading>{{ $t('showcase.loading') }}</UiButton>
        <UiButton variant="ghost" icon-only :aria-label="$t('showcase.iconButton')">
          <Archive />
        </UiButton>
        <UiButton variant="ghost" icon-only size="sm" :aria-label="$t('showcase.pin')"
          ><Pin :size="16"
        /></UiButton>
        <UiButton variant="ghost" icon-only size="sm" :aria-label="$t('showcase.colour')">
          <Palette :size="16" />
        </UiButton>
      </div>
      <UiButton variant="primary" class="h-13 w-60 justify-between! self-end px-5 text-base">
        {{ $t('showcase.primary') }}
        <ArrowRight :size="20" />
      </UiButton>
    </section>

    <section class="flex flex-col gap-5">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.inputs') }}
      </h2>
      <UiField :label="$t('showcase.email')" for="sc-email">
        <UiInput
          id="sc-email"
          v-model="email"
          type="email"
          :placeholder="$t('showcase.emailPlaceholder')"
        />
      </UiField>
      <UiField
        :label="$t('showcase.password')"
        for="sc-password"
        :error="password.length < 10 ? $t('showcase.passwordError') : undefined"
      >
        <UiInput
          id="sc-password"
          v-model="password"
          type="password"
          :invalid="password.length < 10"
          aria-describedby="sc-password-error"
        />
      </UiField>
      <UiField :label="$t('showcase.displayName')" for="sc-name">
        <template #aside>
          <span class="font-mono text-meta text-muted tabular-nums"
            >{{ displayName.length }} / 50</span
          >
        </template>
        <UiInput id="sc-name" v-model="displayName" maxlength="50" />
      </UiField>
      <UiField :label="$t('showcase.disabledInput')" for="sc-disabled">
        <UiInput id="sc-disabled" model-value="admin@example.com" disabled />
      </UiField>
      <UiField :label="$t('showcase.message')" for="sc-message">
        <UiInput
          id="sc-message"
          v-model="message"
          multiline
          :placeholder="$t('showcase.messagePlaceholder')"
        />
      </UiField>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.checkboxes') }}
      </h2>
      <label class="flex cursor-pointer items-center gap-3">
        <UiCheckbox v-model="milk" />
        <span :class="milk && 'text-muted line-through'">{{ $t('showcase.checkboxMilk') }}</span>
      </label>
      <label class="flex cursor-pointer items-center gap-3">
        <UiCheckbox v-model="bread" />
        <span :class="bread && 'text-muted line-through'">{{ $t('showcase.checkboxBread') }}</span>
      </label>
      <label class="flex items-center gap-3 text-faint">
        <UiCheckbox disabled />
        {{ $t('showcase.checkboxDisabled') }}
      </label>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.notices') }}
      </h2>
      <UiNotice>{{ $t('showcase.noticeNeutral') }}</UiNotice>
      <UiNotice tone="info">{{ $t('showcase.noticeInfo') }}</UiNotice>
      <UiNotice tone="warning">{{ $t('showcase.noticeWarning') }}</UiNotice>
      <UiNotice tone="error">{{ $t('showcase.noticeError') }}</UiNotice>
      <UiNotice tone="success">{{ $t('showcase.noticeSuccess') }}</UiNotice>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">{{ $t('showcase.tokens') }}</h2>
      <ul class="grid grid-cols-2 border-t border-l border-line sm:grid-cols-3">
        <li
          v-for="token in tokens"
          :key="token"
          class="flex items-center gap-2 border-r border-b border-line p-2"
        >
          <span
            class="size-5 shrink-0 border border-line"
            :style="{ background: `var(--${token})` }"
          />
          <span class="font-mono text-meta text-muted">{{ token }}</span>
        </li>
      </ul>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-label font-medium tracking-normal text-muted">
        {{ $t('showcase.palette') }}
      </h2>
      <ul class="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <li
          v-for="colour in palette"
          :key="colour"
          class="flex flex-col gap-1 border border-line p-3 text-ink"
          :style="{ background: `var(--note-${colour})` }"
        >
          <span class="font-semibold tracking-[-0.01em]">{{ $t('showcase.noteTitle') }}</span>
          <span class="text-sm">{{ $t('showcase.noteBody') }}</span>
          <span class="font-mono text-meta opacity-70">{{ colour }}</span>
        </li>
      </ul>
    </section>
  </main>
</template>
