/** Shared look of floating panels: menus and popovers get a hairline plus the one float shadow. */
export const floatingPanel =
  'z-50 border border-line bg-bg shadow-float animate-rise motion-reduce:animate-fade outline-none'

export const menuPanel = `${floatingPanel} min-w-[200px] py-1`

export const menuItem =
  'flex h-10 cursor-pointer items-center gap-3 px-3 text-sm text-ink outline-none select-none data-[highlighted]:bg-[color-mix(in_srgb,var(--ink)_6%,var(--bg))] data-[disabled]:cursor-not-allowed data-[disabled]:text-faint'

export const iconButton =
  'grid size-9 shrink-0 cursor-pointer place-items-center text-muted transition-colors duration-150 hover:bg-[color-mix(in_srgb,var(--ink)_6%,transparent)] hover:text-ink disabled:cursor-not-allowed disabled:text-faint pointer-coarse:size-11'
