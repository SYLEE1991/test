export async function verifyStore(serverUrl, token, storeCode) {
  const baseUrl = import.meta.env.PROD ? '' : serverUrl.replace(/\/+$/, '');
  const url = `${baseUrl}/api/config/store/${encodeURIComponent(storeCode)}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Access-Token': token,
    },
  });

  if (response.ok) {
    return response.json();
  }

  if (response.status === 404) {
    throw new Error('STORE_NOT_FOUND');
  }
  if (response.status === 401 || response.status === 403) {
    throw new Error('STORE_NO_PERMISSION');
  }
  throw new Error('STORE_FETCH_FAILED');
}
