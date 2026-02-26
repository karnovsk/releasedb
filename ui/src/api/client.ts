const token = import.meta.env.VITE_API_TOKEN as string;

if (!token) {
  console.warn(
    'VITE_API_TOKEN is not set. Copy ui/.env.local.example to ui/.env.local and set your token.'
  );
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}
