"use client";

import { useMemo } from "react";

import type { DashboardRole } from "@/lib/auth/types";

type ProductInteractionMode = "details" | "purchase" | "inventory";

const PRODUCT_MODE_OPTIONS: Array<{
  value: ProductInteractionMode;
  label: string;
}> = [
  { value: "details", label: "Normal" },
  { value: "purchase", label: "Purchase" },
  { value: "inventory", label: "Inventory" },
];

const buildDateInputValue = (): string => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today.toISOString().slice(0, 10);
};

const parseProductModeParam = (
  rawValue: string | null,
): ProductInteractionMode => {
  if (rawValue === "purchase" || rawValue === "inventory") {
    return rawValue;
  }
  return "details";
};

const serializeProductModeParam = (
  value: ProductInteractionMode,
): string | null => {
  return value === "details" ? null : value;
};

const parsePurchaseDateParam = (rawValue: string | null): string => {
  if (rawValue?.trim().length) {
    return rawValue;
  }
  return buildDateInputValue();
};

const serializePurchaseDateParam = (value: string): string | null => {
  return value?.trim().length ? value : null;
};

function ModeButtons({
  isAdmin,
  productInteractionMode,
  onChange,
}: {
  isAdmin: boolean;
  productInteractionMode: ProductInteractionMode;
  onChange: (mode: ProductInteractionMode) => void;
}) {
  const allowedModes = useMemo(
    () =>
      isAdmin
        ? PRODUCT_MODE_OPTIONS
        : PRODUCT_MODE_OPTIONS.filter((option) => option.value === "details"),
    [isAdmin],
  );

  return (
    <div className="flex flex-col items-center gap-2 lg:flex-1 lg:flex-row lg:items-center lg:justify-center">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
        Mode
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {allowedModes.map((option) => {
          const isActive = option.value === productInteractionMode;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              aria-pressed={isActive}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                isActive
                  ? "bg-neutral-900 text-white shadow"
                  : "border border-neutral-300 text-neutral-600 hover:border-neutral-900 hover:text-neutral-900"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PurchaseModeDefaults({
  isAdmin,
  productInteractionMode,
  purchaseDateOverride,
  setPurchaseDateOverride,
}: {
  isAdmin: boolean;
  productInteractionMode: ProductInteractionMode;
  purchaseDateOverride: string;
  setPurchaseDateOverride: (value: string) => void;
}) {
  if (!isAdmin || productInteractionMode !== "purchase") {
    return null;
  }
  return (
    <div className="rounded-3xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-4 text-sm text-neutral-700 shadow-inner">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Default purchase date
          </p>
          <p className="text-xs text-neutral-500">
            New purchase entries open with this date pre-filled so you can batch
            receipts for a given day.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            type="date"
            value={purchaseDateOverride ?? ""}
            onChange={(event) => {
              const value = event.target.value;
              setPurchaseDateOverride(value.trim().length ? value : "");
            }}
            className="rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
          />
          <button
            type="button"
            onClick={() => setPurchaseDateOverride(buildDateInputValue())}
            className="rounded-full border border-neutral-300 px-4 py-2 text-xs font-semibold text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
          >
            Use today
          </button>
        </div>
      </div>
    </div>
  );
}

export {
  ModeButtons,
  PurchaseModeDefaults,
  buildDateInputValue,
  parseProductModeParam,
  serializeProductModeParam,
  parsePurchaseDateParam,
  serializePurchaseDateParam,
  type ProductInteractionMode,
};
