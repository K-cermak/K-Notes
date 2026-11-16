/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite'

const brandingPath = fileURLToPath(new URL('../branding.json', import.meta.url))
const branding = JSON.parse(readFileSync(brandingPath, 'utf8')) as Record<string, string>

function escapeHtml(value: string): string {
  return value.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`)
}

// index.html uses %BRANDING_NAME% and friends, so the name stays in branding.json only.
function brandingHtml(): Plugin {
  return {
    name: 'branding-html',
    transformIndexHtml: (html) =>
      html.replace(/%BRANDING_(\w+)%/g, (_, key: string) =>
        escapeHtml(branding[key.toLowerCase()] ?? ''),
      ),
  }
}

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    VueI18nPlugin({ include: [fileURLToPath(new URL('./src/locales/*.json', import.meta.url))] }),
    brandingHtml(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@branding': brandingPath,
    },
  },
  server: {
    fs: { allow: ['..'] },
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
})
