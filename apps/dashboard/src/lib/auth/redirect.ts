export function resolveCallbackPath(
  rawValue: string | string[] | null | undefined,
): string | null {
  const value = Array.isArray(rawValue) ? rawValue[0] : rawValue;
  const trimmed = value?.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const parsed = new URL(trimmed, "http://localhost");
    if (parsed.origin === "http://localhost") {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    // Fall through to the safe prefix check.
  }

  if (trimmed.startsWith("/")) {
    return trimmed;
  }

  return null;
}
