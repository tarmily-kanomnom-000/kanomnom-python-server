"use client";

import type { DateRange, NumericRange } from "./types";

type NumericFilterEditorProps = {
  fieldLabel: string;
  value: NumericRange | null;
  onChange: (range: NumericRange) => void;
};

const NUMERIC_MODE_OPTIONS: Array<{
  mode: NumericRange["mode"];
  label: string;
}> = [
  { mode: "lt", label: "<" },
  { mode: "exact", label: "=" },
  { mode: "gt", label: ">" },
  { mode: "between", label: "Range" },
];

export function NumericFilterEditor({
  fieldLabel,
  value,
  onChange,
}: NumericFilterEditorProps) {
  const current: NumericRange = value ?? {
    mode: "exact",
    min: null,
    max: null,
  };

  const setMode = (mode: NumericRange["mode"]) => {
    if (mode === current.mode) {
      return;
    }
    if (mode === "between") {
      onChange({
        mode,
        min: current.min ?? null,
        max: current.max ?? null,
      });
      return;
    }
    if (mode === "lt") {
      onChange({
        mode,
        max: current.max ?? current.min ?? null,
        min: null,
      });
      return;
    }
    if (mode === "gt") {
      onChange({
        mode,
        min: current.min ?? current.max ?? null,
        max: null,
      });
      return;
    }
    onChange({
      mode,
      min: current.min ?? current.max ?? null,
      max: null,
    });
  };

  const handleValueChange = (key: "min" | "max", raw: string) => {
    const parsed = raw === "" ? null : Number(raw);
    if (parsed === null || Number.isFinite(parsed)) {
      onChange({
        ...current,
        [key]: parsed,
      });
    }
  };

  const singleValue =
    current.mode === "lt"
      ? (current.max ?? "")
      : current.mode === "gt" || current.mode === "exact"
        ? (current.min ?? "")
        : "";

  return (
    <div className="mt-2 rounded-2xl border border-neutral-200 p-3">
      <p className="text-xs text-neutral-500">
        Filter {fieldLabel.toLowerCase()}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {NUMERIC_MODE_OPTIONS.map((option) => (
          <button
            key={option.mode}
            type="button"
            onClick={() => setMode(option.mode)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
              current.mode === option.mode
                ? "border-neutral-900 bg-neutral-900 text-white"
                : "border-neutral-200 text-neutral-600 hover:border-neutral-900 hover:text-neutral-900"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {current.mode === "between" ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <input
            type="number"
            value={current.min ?? ""}
            onChange={(event) => handleValueChange("min", event.target.value)}
            placeholder="Min"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20"
          />
          <input
            type="number"
            value={current.max ?? ""}
            onChange={(event) => handleValueChange("max", event.target.value)}
            placeholder="Max"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20"
          />
        </div>
      ) : (
        <input
          type="number"
          value={singleValue}
          onChange={(event) => {
            if (current.mode === "lt") {
              handleValueChange("max", event.target.value);
            } else {
              handleValueChange("min", event.target.value);
            }
          }}
          placeholder={
            current.mode === "lt"
              ? "Less than…"
              : current.mode === "gt"
                ? "Greater than…"
                : "Equal to…"
          }
          className="mt-3 w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20"
        />
      )}
    </div>
  );
}

type DateFilterEditorProps = {
  fieldLabel: string;
  value: DateRange | null;
  onChange: (range: DateRange) => void;
};

const DATE_MODE_OPTIONS: Array<{ mode: DateRange["mode"]; label: string }> = [
  { mode: "before", label: "Before" },
  { mode: "on", label: "On" },
  { mode: "after", label: "After" },
  { mode: "between", label: "Between" },
];

export function DateFilterEditor({
  fieldLabel,
  value,
  onChange,
}: DateFilterEditorProps) {
  const current: DateRange = value ?? {
    mode: "on",
    start: null,
    end: null,
  };

  const setMode = (mode: DateRange["mode"]) => {
    if (mode === current.mode) {
      return;
    }
    if (mode === "between") {
      onChange({
        mode,
        start: current.start ?? null,
        end: current.end ?? null,
      });
      return;
    }
    if (mode === "before") {
      onChange({
        mode,
        start: null,
        end: current.end ?? current.start ?? null,
      });
      return;
    }
    onChange({
      mode,
      start: current.start ?? current.end ?? null,
      end: null,
    });
  };

  const handleDateChange = (key: "start" | "end", raw: string) => {
    const value = raw === "" ? null : raw;
    onChange({
      ...current,
      [key]: value,
    });
  };

  return (
    <div className="mt-2 rounded-2xl border border-neutral-200 p-3">
      <p className="text-xs text-neutral-500">
        Filter {fieldLabel.toLowerCase()}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {DATE_MODE_OPTIONS.map((option) => (
          <button
            key={option.mode}
            type="button"
            onClick={() => setMode(option.mode)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
              current.mode === option.mode
                ? "border-neutral-900 bg-neutral-900 text-white"
                : "border-neutral-200 text-neutral-600 hover:border-neutral-900 hover:text-neutral-900"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      {current.mode === "between" ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <input
            type="date"
            value={current.start ?? ""}
            onChange={(event) => handleDateChange("start", event.target.value)}
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20"
          />
          <input
            type="date"
            value={current.end ?? ""}
            onChange={(event) => handleDateChange("end", event.target.value)}
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20"
          />
        </div>
      ) : (
        <input
          type="date"
          value={
            current.mode === "before"
              ? (current.end ?? "")
              : (current.start ?? "")
          }
          onChange={(event) => {
            if (current.mode === "before") {
              handleDateChange("end", event.target.value);
            } else {
              handleDateChange("start", event.target.value);
            }
          }}
          className="mt-3 w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm text-neutral-800 outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20"
        />
      )}
    </div>
  );
}

export function hasNumericSelection(range: NumericRange | null): boolean {
  if (!range) {
    return false;
  }
  if (range.mode === "between") {
    return (
      typeof range.min === "number" &&
      typeof range.max === "number" &&
      !Number.isNaN(range.min) &&
      !Number.isNaN(range.max)
    );
  }
  if (range.mode === "lt") {
    return typeof range.max === "number" && !Number.isNaN(range.max);
  }
  return typeof range.min === "number" && !Number.isNaN(range.min);
}

export function hasDateSelection(range: DateRange | null): boolean {
  if (!range) {
    return false;
  }
  if (range.mode === "between") {
    return Boolean(range.start && range.end);
  }
  if (range.mode === "before") {
    return Boolean(range.end);
  }
  return Boolean(range.start);
}
