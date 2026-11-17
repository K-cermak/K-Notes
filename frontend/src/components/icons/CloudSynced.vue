<script setup lang="ts">
/**
 * A cloud with a check inside it, drawn in Lucide's style. Lucide's cloud-check lets the check
 * cross the outline, which at 18 px reads as a smudge, and its one-humped cloud reads poorly at
 * that size too; this cloud has two humps, built from circles so the curves meet smoothly.
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
    <path
      d="M5.5 19A3.5 3.5 0 0 1 5.23 12.01A5 5 0 0 1 14.27 7.89A4 4 0 0 1 19.95 12.13A3.5 3.5 0 0 1 19 19Z"
    />
    <path d="m9.75 13 2 2 3.75-3.75" />
  </svg>
</template>
