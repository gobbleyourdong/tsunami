// Vitest test setup. Extends jsdom with the browser APIs the scaffold
// components expect — IntersectionObserver (AnimatedCounter, ScrollReveal),
// ResizeObserver (various), matchMedia (useMediaQuery hook).
import "@testing-library/jest-dom"
import { vi } from "vitest"

// IntersectionObserver polyfill — jsdom doesn't ship it.
class MockIntersectionObserver {
  root = null
  rootMargin = ""
  thresholds = []
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
  takeRecords = vi.fn(() => [])
}
// @ts-ignore — global overwrite for test env
globalThis.IntersectionObserver = MockIntersectionObserver as any

// ResizeObserver polyfill
class MockResizeObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
// @ts-ignore
globalThis.ResizeObserver = MockResizeObserver as any

// matchMedia polyfill — useMediaQuery + useMobile depend on this.
if (!globalThis.matchMedia) {
  // @ts-ignore
  globalThis.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })
}

// scrollTo no-op — some components call this on mount.
if (!globalThis.scrollTo) {
  // @ts-ignore
  globalThis.scrollTo = vi.fn()
}
