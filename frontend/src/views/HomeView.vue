<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowRight, LogOut } from '@lucide/vue'
import branding from '@branding'
import { useSubmit } from '@/composables/useSubmit'
import { useInstanceStore } from '@/stores/instance'
import { useSessionStore } from '@/stores/session'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

// Placeholder until the notes interface in phase 4.
const router = useRouter()
const instance = useInstanceStore()
const session = useSessionStore()
const signOut = useSubmit()

async function logout(): Promise<void> {
  if (await signOut.run(() => session.logout())) await router.replace('/login')
}
</script>

<template>
  <main class="mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center gap-6 px-4 py-10">
    <div class="flex flex-col gap-2">
      <h1 class="text-2xl leading-tight">{{ branding.name }}</h1>
      <p v-if="session.user" class="text-muted" data-testid="signed-in-as">
        {{ $t('home.signedInAs', { name: session.user.display_name, email: session.user.email }) }}
      </p>
      <p v-else class="text-muted">{{ $t('home.tagline') }}</p>
    </div>
    <p
      v-if="instance.config"
      class="font-mono text-meta text-faint tabular-nums"
      data-testid="version"
    >
      {{ $t('home.version', { version: instance.config.version }) }}
    </p>
    <UiNotice v-else-if="instance.failed" tone="error">{{ $t('home.error') }}</UiNotice>
    <nav class="flex flex-col items-start gap-3">
      <RouterLink
        v-if="session.user?.is_admin"
        to="/admin"
        class="group inline-flex items-center gap-2 font-medium text-accent"
      >
        {{ $t('admin.title') }}
        <ArrowRight
          :size="16"
          class="transition-transform duration-150 ease-out group-hover:translate-x-[3px]"
        />
      </RouterLink>
      <RouterLink
        to="/showcase"
        class="group inline-flex items-center gap-2 font-medium text-accent"
      >
        {{ $t('home.showcase') }}
        <ArrowRight
          :size="16"
          class="transition-transform duration-150 ease-out group-hover:translate-x-[3px]"
        />
      </RouterLink>
    </nav>
    <UiNotice v-if="signOut.error.value" tone="error">{{ signOut.error.value }}</UiNotice>
    <UiButton
      v-if="session.user"
      class="self-start"
      :loading="signOut.pending.value"
      @click="logout"
    >
      <LogOut :size="16" />
      {{ $t('home.signOut') }}
    </UiButton>
  </main>
</template>
