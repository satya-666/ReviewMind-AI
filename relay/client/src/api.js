export async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    credentials: "include",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The server is unavailable. Please retry.");
  }
  if (!response.ok)
    throw Object.assign(new Error(data.error || "Request failed"), {
      status: response.status,
    });
  return data;
}
