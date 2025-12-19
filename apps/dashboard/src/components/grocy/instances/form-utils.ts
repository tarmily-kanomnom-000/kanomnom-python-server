"use client";

import type { SearchableOption } from "./searchable-option-select";

export function computeDefaultBestBeforeDate(days: number): string {
  if (!Number.isFinite(days) || days <= 0) {
    return "";
  }
  const reference = new Date();
  reference.setHours(0, 0, 0, 0);
  reference.setDate(reference.getDate() + days);
  return reference.toISOString().slice(0, 10);
}

export function buildSearchableOptions(
  records: Record<number, string>,
): SearchableOption[] {
  return Object.entries(records)
    .map(([id, name]) => ({ id: Number(id), name }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function roundToSixDecimals(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}
