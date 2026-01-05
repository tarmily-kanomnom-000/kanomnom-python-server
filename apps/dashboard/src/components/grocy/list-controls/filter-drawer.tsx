"use client";

import { useMemo } from "react";

import { DateFilterEditor, NumericFilterEditor } from "./filter-editors";
import type {
  DateRange,
  FilterConfig,
  FilterFieldConfig,
  NumericRange,
} from "./types";

type FilterDrawerProps = {
  filters: FilterConfig;
  activeFieldId: string | null;
  onActiveFieldChange: (id: string | null) => void;
  searchValue: string;
  onSearchValueChange: (value: string) => void;
  numericDraft: NumericRange | null;
  onNumericDraftChange: (range: NumericRange | null) => void;
  dateDraft: DateRange | null;
  onDateDraftChange: (range: DateRange | null) => void;
  onClose: () => void;
};

export function FilterDrawer({
  filters,
  activeFieldId,
  onActiveFieldChange,
  searchValue,
  onSearchValueChange,
  numericDraft,
  onNumericDraftChange,
  dateDraft,
  onDateDraftChange,
  onClose,
}: FilterDrawerProps) {
  const activeField: FilterFieldConfig | null = useMemo(() => {
    return (
      filters.fields.find((field) => field.id === activeFieldId) ??
      filters.fields[0] ??
      null
    );
  }, [filters.fields, activeFieldId]);

  const normalizedSearch = searchValue.trim().toLowerCase();
  const visibleValues =
    activeField?.type === "text"
      ? activeField.values.filter((value) =>
          value.toLowerCase().includes(normalizedSearch),
        )
      : [];

  if (!activeField) {
    return null;
  }

  return (
    <div className="absolute right-0 top-full z-20 mt-2 w-[26rem] rounded-2xl border border-neutral-200 bg-white p-4 shadow-lg">
      <div className="flex flex-col gap-4 text-sm text-neutral-700 sm:flex-row">
        <div className="sm:w-40">
          <p className="text-xs font-semibold text-neutral-500">Field</p>
          <select
            value={activeField.id}
            onChange={(event) => {
              onActiveFieldChange(event.target.value);
              onSearchValueChange("");
            }}
            className="mt-1 w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 focus:border-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-900/20"
          >
            {filters.fields.map((field) => (
              <option key={field.id} value={field.id}>
                {field.label}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs text-neutral-500">
            Select a field to browse its values.
          </p>
        </div>

        <div className="flex-1">
          <p className="text-xs font-semibold text-neutral-500">
            {activeField.label}
          </p>
          {activeField.type === "text" ? (
            <>
              <input
                type="search"
                value={searchValue}
                onChange={(event) => onSearchValueChange(event.target.value)}
                placeholder={`Search ${activeField.label.toLowerCase()}…`}
                className="mt-1 w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20"
              />
              <div className="mt-3 max-h-48 space-y-2 overflow-y-auto rounded-xl border border-dashed border-neutral-200 p-2">
                {visibleValues.length > 0 ? (
                  visibleValues.map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => activeField.onToggle(value)}
                      className={`w-full rounded-lg border px-3 py-2 text-left text-xs font-medium transition ${
                        activeField.selectedValues.includes(value)
                          ? "border-neutral-900 bg-neutral-900 text-white"
                          : "border-neutral-200 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
                      }`}
                    >
                      {value}
                    </button>
                  ))
                ) : (
                  <p className="px-2 py-1 text-xs text-neutral-500">
                    No matches for “{searchValue}”.
                  </p>
                )}
              </div>
            </>
          ) : null}
          {activeField.type === "number" ? (
            <NumericFilterEditor
              fieldLabel={activeField.label}
              value={numericDraft ?? activeField.range ?? null}
              onChange={(next) => {
                onNumericDraftChange(next);
                activeField.onRangeChange(next);
              }}
            />
          ) : null}
          {activeField.type === "date" ? (
            <DateFilterEditor
              fieldLabel={activeField.label}
              value={dateDraft ?? activeField.range ?? null}
              onChange={(next) => {
                onDateDraftChange(next);
                activeField.onRangeChange(next);
              }}
            />
          ) : null}
        </div>
      </div>

      <div className="mt-3 flex justify-end gap-3 text-xs font-medium">
        <button
          type="button"
          onClick={() => {
            activeField.onClear();
            onSearchValueChange("");
            onNumericDraftChange(null);
            onDateDraftChange(null);
          }}
          className="text-neutral-500 underline-offset-2 hover:underline"
        >
          Clear field
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full bg-neutral-900 px-3 py-1 text-white"
        >
          Done
        </button>
      </div>
    </div>
  );
}
