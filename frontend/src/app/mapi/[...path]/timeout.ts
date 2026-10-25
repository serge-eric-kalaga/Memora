/** Server-only deadline policy. Longer chat never means silently truncating its sources. */
export function proxyTimeoutMs(
  method: string,
  parts: string[],
  configured?: string,
) {
  const chat =
    method === "POST" &&
    parts.length === 3 &&
    parts[0] === "meetings" &&
    parts[2] === "chat";
  if (!chat) return 120_000;
  const value = configured?.trim() ? Number(configured) : Number.NaN;
  return Number.isFinite(value)
    ? Math.min(1_800_000, Math.max(1_000, Math.trunc(value)))
    : 600_000;
}
