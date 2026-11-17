// Renders the PNG icons in public/ from public/icon.svg with the Playwright Chromium the project
// already uses for tests, so no image library is needed. Run with `just icons`.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const publicDir = fileURLToPath(new URL('../public/', import.meta.url))
const svg = readFileSync(`${publicDir}icon.svg`, 'utf8')
const BACKGROUND = '#171717'

// A maskable icon is cropped to a circle by some launchers, so the glyph keeps to the inner 80 %.
const icons: { file: string; size: number; padding: number }[] = [
  { file: 'pwa-64x64.png', size: 64, padding: 0 },
  { file: 'pwa-192x192.png', size: 192, padding: 0 },
  { file: 'pwa-512x512.png', size: 512, padding: 0 },
  { file: 'maskable-icon-512x512.png', size: 512, padding: 0.1 },
  { file: 'apple-touch-icon-180x180.png', size: 180, padding: 0.05 },
]

const browser = await chromium.launch()
const page = await browser.newPage()
for (const { file, size, padding } of icons) {
  const inset = Math.round(size * padding)
  await page.setViewportSize({ width: size, height: size })
  await page.setContent(
    `<body style="margin:0;background:${BACKGROUND}">
      <div style="position:absolute;inset:${inset}px">${svg.replace('<svg ', '<svg width="100%" height="100%" ')}</div>
    </body>`,
  )
  await page.screenshot({
    path: `${publicDir}${file}`,
    clip: { x: 0, y: 0, width: size, height: size },
  })
}
await browser.close()
