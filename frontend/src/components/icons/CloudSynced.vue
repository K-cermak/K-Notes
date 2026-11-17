<script setup lang="ts">
/**
 * Lucide's cloud with a check inside it. Lucide's own cloud-check lets the check cross the cloud's
 * outline, which at 18 px reads as a smudge rather than a check.
 */
withDefaults(defineProps<{ size?: number }>(), { size: 18 })
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    class="lucide"
  >
    <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
    <path d="m9 14.5 2.5 2.5 4.5-4.5" />
  </svg>
</template>
