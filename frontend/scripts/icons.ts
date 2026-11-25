// Renders the PNG icons in public/ from public/icon.svg with the Playwright Chromium the project
// already uses for tests, so no image library is needed. Run with `just icons`.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const publicDir = fileURLToPath(new URL('../public/', import.meta.url))
const svg = readFileSync(`${publicDir}icon.svg`, 'utf8')
const BACKGROUND = '#171717'

// The plain icons keep the logo's own shape. A maskable icon is cropped to a circle by some
// launchers, so the logo keeps to the inner 80 %; iOS fills a transparent touch icon with black.
const icons: { file: string; size: number; padding: number; background: string }[] = [
  { file: 'pwa-64x64.png', size: 64, padding: 0.02, background: 'transparent' },
  { file: 'pwa-192x192.png', size: 192, padding: 0.02, background: 'transparent' },
  { file: 'pwa-512x512.png', size: 512, padding: 0.02, background: 'transparent' },
  { file: 'maskable-icon-512x512.png', size: 512, padding: 0.2, background: BACKGROUND },
  { file: 'apple-touch-icon-180x180.png', size: 180, padding: 0.16, background: BACKGROUND },
]

const browser = await chromium.launch()
const page = await browser.newPage()
for (const { file, size, padding, background } of icons) {
  const inset = Math.round(size * padding)
  await page.setViewportSize({ width: size, height: size })
  await page.setContent(
    `<body style="margin:0;background:${background}">
      <div style="position:absolute;inset:${inset}px">${svg.replace('<svg ', '<svg width="100%" height="100%" ')}</div>
    </body>`,
  )
  await page.screenshot({
    path: `${publicDir}${file}`,
    clip: { x: 0, y: 0, width: size, height: size },
    omitBackground: background === 'transparent',
  })
}
await browser.close()
