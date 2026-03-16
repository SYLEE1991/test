export async function loginApi(serverUrl, email, password) {
  // In production (Vercel), use proxy path. In dev, use server URL directly.
  const baseUrl = import.meta.env.PROD ? '' : serverUrl.replace(/\/+$/, '');
  const url = `${baseUrl}/api/auth/login`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(`Login failed: ${response.status}`);
  }

  return response.json();
}
