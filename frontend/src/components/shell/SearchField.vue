<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, X } from '@lucide/vue'
import { iconButton } from '@/components/ui/menu'

// Search runs locally as you type; the query lives in the URL, so Back leaves the results. The
// search view opens with the first character, not on focus: tabbing through the field must not
// take a keyboard user away from their notes.
const route = useRoute()
const router = useRouter()
const input = ref<HTMLInputElement | null>(null)

function query(): string {
  return route.name === 'search' ? String(route.query.q ?? '') : ''
}

function onInput(event: Event): void {
  const q = (event.target as HTMLInputElement).value
  if (route.name === 'search') void router.replace({ name: 'search', query: q ? { q } : {} })
  else void router.push({ name: 'search', query: q ? { q } : {} })
}

function close(): void {
  input.value?.blur()
  if (route.name !== 'search') return
  if (window.history.state?.back) router.back()
  else void router.replace('/')
}

defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <div
    role="search"
    class="flex h-11 min-w-0 flex-1 items-center border border-transparent bg-[color-mix(in_srgb,var(--ink)_5%,var(--bg))] transition-colors duration-150 focus-within:border-line focus-within:bg-bg sm:max-w-[720px]"
  >
    <span class="grid size-11 shrink-0 place-items-center text-muted"><Search :size="18" /></span>
    <input
      ref="input"
      :value="query()"
      type="search"
      class="h-full min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted [&::-webkit-search-cancel-button]:hidden"
      :placeholder="$t('search.placeholder')"
      :aria-label="$t('search.placeholder')"
      data-testid="search"
      @input="onInput"
      @keydown.escape="close"
    />
    <button
      v-if="route.name === 'search'"
      type="button"
      :class="iconButton"
      :aria-label="$t('search.close')"
      :title="$t('search.close')"
      @click="close"
    >
      <X :size="18" />
    </button>
  </div>
</template>
