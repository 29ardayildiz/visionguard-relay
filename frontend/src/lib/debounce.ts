// Slider'larda kullanılan basit debounce yardımcı fonksiyonu (CLAUDE.md §2.4:
// en az 300ms debounce). `.flush()` bırakma anında (pointerup) bekleyen
// çağrıyı hemen tetiklemek için kullanılır.

export interface Debounced<Args extends unknown[]> {
  (...args: Args): void
  flush: (...args: Args) => void
  cancel: () => void
}

export function debounce<Args extends unknown[]>(fn: (...args: Args) => void, delayMs: number): Debounced<Args> {
  let timer: ReturnType<typeof setTimeout> | null = null

  const debounced = ((...args: Args) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, delayMs)
  }) as Debounced<Args>

  debounced.flush = (...args: Args) => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    fn(...args)
  }

  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return debounced
}
