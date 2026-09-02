// SSE streaming client: POST with Bearer token, parses `data: {...}\n\n` events.
export async function streamPost(url, body, headers, onEvent, signal) {
  const res = await fetch(url, {
    method: "POST",
    signal,
    headers: { ...(headers || {}), "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      msg = j?.detail || msg;
    } catch {
      // non-JSON body
    }
    throw new Error(msg);
  }
  if (!res.body) throw new Error("No stream body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = chunk.replace(/^data:\s*/, "").trim();
      if (!line) continue;
      try {
        onEvent(JSON.parse(line));
      } catch {
        // ignore malformed lines
      }
    }
  }
}
