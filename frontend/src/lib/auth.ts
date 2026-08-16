// Backend /login endpoint'i (Faz 7 cutover'a kadar) hâlâ form-encoded POST
// bekleyip 303 redirect dönüyor (JSON API değil — CLAUDE.md: cutover'dan önce
// eski Jinja2 route'ları bozulmamalı). fetch() redirect'leri otomatik takip
// ettiği için başarı/hata ayrımını nihai response.url'den çıkarıyoruz:
// başarılıysa "/" ile, hatalıysa "/login?error=1" ile biter.

export async function login(username: string, password: string): Promise<boolean> {
  const body = new URLSearchParams({ username, password })
  const response = await fetch('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  return !response.url.includes('error=1')
}

// /health, JWT cookie doğrulaması gerektiren en hafif endpoint — mevcut
// oturumun geçerli olup olmadığını kontrol etmek için kullanılır.
export async function isAuthenticated(): Promise<boolean> {
  try {
    const response = await fetch('/health')
    return response.status !== 401
  } catch {
    return false
  }
}
