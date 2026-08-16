// Ortak fetch wrapper — backend 401 döndürdüğünde otomatik /login'e yönlendirir
// (CLAUDE.md §6.2: 401 alındığında kullanıcı sessizce /login'e aktarılmalı).

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response | null> {
  const response = await fetch(input, init)
  if (response.status === 401) {
    window.location.href = '/login'
    return null
  }
  return response
}
