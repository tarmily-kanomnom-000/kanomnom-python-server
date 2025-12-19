export function parseOptionalNonNegativeNumber(
  value: unknown,
  field: string,
): number | null {
  if (value == null || value === "") {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${field} must be a finite number.`);
  }
  if (parsed < 0) {
    throw new Error(`${field} cannot be negative.`);
  }
  return parsed;
}
