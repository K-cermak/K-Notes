<script setup lang="ts">
import { computed } from 'vue'
import { encode } from 'uqr'

/** A QR code as one SVG path, for the authenticator app to scan. */
const props = defineProps<{ value: string; label: string }>()

const qr = computed(() => {
  const { data, size } = encode(props.value, { border: 2 })
  let path = ''
  data.forEach((row, y) => {
    row.forEach((dark, x) => {
      if (dark) path += `M${x} ${y}h1v1h-1z`
    })
  })
  return { path, size }
})
</script>

<template>
  <!-- Always dark on light, whatever the theme: scanners read that most reliably. -->
  <svg
    :viewBox="`0 0 ${qr.size} ${qr.size}`"
    role="img"
    :aria-label="label"
    class="block size-48 bg-bg text-ink scheme-light"
    shape-rendering="crispEdges"
  >
    <path :d="qr.path" fill="currentColor" />
  </svg>
</template>
