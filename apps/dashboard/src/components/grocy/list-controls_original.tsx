"use client";

import {
  type InputHTMLAttributes,
  type ReactNode,
  useEffect,
  useState,
} from "react";

export type SortDirection = "asc" | "desc";

type SortOption<Field extends string> = {
  label: string;
  value: Field;
};

export type SortRule<Field extends string> = {
  field: Field;
  direction: SortDirection;
};

export type NumericRange = {
  mode: "exact" | "lt" | "gt" | "between";
  min?: number | null;
  max?: number | null;
};

export type DateRange = {
  mode: "on" | "before" | "after" | "between";
  start?: string | null;
  end?: string | null;
};

type FilterFieldBase = {
  id: string;
  label: string;
  onClear: () => void;
};

type TextFilterFieldConfig = FilterFieldBase & {
  type: "text";
  values: string[];
  selectedValues: string[];
  onToggle: (value: string) => void;
};

type NumberFilterFieldConfig = FilterFieldBase & {
  type: "number";
  range: NumericRange | null;
  onRangeChange: (range: NumericRange | null) => void;
};

type DateFilterFieldConfig = FilterFieldBase & {
  type: "date";
  range: DateRange | null;
  onRangeChange: (range: DateRange | null) => void;
};

type FilterFieldConfig =
  | TextFilterFieldConfig
  | NumberFilterFieldConfig
  | DateFilterFieldConfig;

type FilterConfig = {
  fields: FilterFieldConfig[];
  buttonLabel?: string;
  disabled?: boolean;
  onVisibilityChange?: (isVisible: boolean) => void;
};

type ListControlsProps<Field extends string> = {
  searchLabel: string;
  searchPlaceholder: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchInputClassName?: string;
  searchInputProps?: Omit<
    InputHTMLAttributes<HTMLInputElement>,
    "type" | "value" | "onChange" | "placeholder"
  >;
  searchResults?: ReactNode;
  filters?: FilterConfig;
  sortOptions?: SortOption<Field>[];
  sortState?: SortRule<Field>[];
  onSortChange?: (rules: SortRule<Field>[]) => void;
  maxSortLevels?: number;
  className?: string;
};

export function ListControls<Field extends string>({
  searchLabel,
  searchPlaceholder,
  searchValue,
  onSearchChange,
  searchInputClassName,
  searchInputProps,
  searchResults,
  filters,
  sortOptions,
  sortState,
  onSortChange,
  maxSortLevels,
  className = "flex items-start gap-3",
}: ListControlsProps<Field>) {
  const [isFilterOpen, setFilterOpen] = useState(false);
  const [isSortOpen, setSortOpen] = useState(false);
  const [activeFilterFieldId, setActiveFilterFieldId] = useState<string | null>(
    filters?.fields[0]?.id ?? null,
  );
  const [filterSearchValue, setFilterSearchValue] = useState("");
  const [numericDraft, setNumericDraft] = useState<NumericRange | null>(null);
  const [dateDraft, setDateDraft] = useState<DateRange | null>(null);

  const hasFilters = Boolean(filters && filters.fields.length > 0);
  const filterDisabled = Boolean(filters?.disabled) || !hasFilters;
  const hasSort = Boolean(
    sortOptions && sortOptions.length > 0 && onSortChange,
  );
  const effectiveSortState = sortState ?? [];
  const reachedMaxSortLevels =
    typeof maxSortLevels === "number" &&
    effectiveSortState.length >= maxSortLevels;

  useEffect(() => {
    if (filterDisabled) {
      setFilterOpen(false);
      filters?.onVisibilityChange?.(false);
    }
    if (filters?.fields?.length) {
      const nextActiveId =
        filters.fields.find((field) => field.id === activeFilterFieldId)?.id ??
        filters.fields[0]?.id ??
        null;
      if (nextActiveId !== activeFilterFieldId) {
        setActiveFilterFieldId(nextActiveId);
      }
    } else if (activeFilterFieldId) {
      setActiveFilterFieldId(null);
    }
    setFilterSearchValue("");
    setNumericDraft(null);
    setDateDraft(null);
  }, [filterDisabled, filters, activeFilterFieldId]);

  useEffect(() => {
    if (!hasSort) {
      setSortOpen(false);
    }
  }, [hasSort]);

  const renderFilterPopover = () => {
    if (!filters || filterDisabled || !isFilterOpen) {
      return null;
    }
    const activeField =
      filters.fields.find((field) => field.id === activeFilterFieldId) ??
      filters.fields[0] ??
      null;
    if (!activeField) {
      return null;
    }
    const normalizedSearch = filterSearchValue.trim().toLowerCase();
    const visibleValues =
      activeField.type === "text"
        ? activeField.values.filter((value) =>
            value.toLowerCase().includes(normalizedSearch),
          )
        : [];

    return (
      <div className="absolute right-0 top-full z-20 mt-2 w-[26rem] rounded-2xl border border-neutral-200 bg-white p-4 shadow-lg">
        <div className="flex flex-col gap-4 text-sm text-neutral-700 sm:flex-row">
          <div className="sm:w-40">
            <p className="text-xs font-semibold text-neutral-500">Field</p>
            <select
              value={activeField.id}
              onChange={(event) => {
                setActiveFilterFieldId(event.target.value);
                setFilterSearchValue("");
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
                  value={filterSearchValue}
                  onChange={(event) => setFilterSearchValue(event.target.value)}
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
                      No matches for “{filterSearchValue}”.
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
                  setNumericDraft(next);
                  activeField.onRangeChange(next);
                }}
              />
            ) : null}
            {activeField.type === "date" ? (
              <DateFilterEditor
                fieldLabel={activeField.label}
                value={dateDraft ?? activeField.range ?? null}
                onChange={(next) => {
                  setDateDraft(next);
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
              setFilterSearchValue("");
              setNumericDraft(null);
              setDateDraft(null);
            }}
            className="text-neutral-500 underline-offset-2 hover:underline"
          >
            Clear field
          </button>
          <button
            type="button"
            onClick={() => {
              setFilterOpen(false);
              filters.onVisibilityChange?.(false);
            }}
            className="rounded-full bg-neutral-900 px-3 py-1 text-white"
          >
            Done
          </button>
        </div>
      </div>
    );
  };

  const handleSortRuleChange = (
    index: number,
    update: Partial<SortRule<Field>>,
  ) => {
    if (!onSortChange || !effectiveSortState[index]) {
      return;
    }
    const next = effectiveSortState.map((rule, i) =>
      i === index ? { ...rule, ...update } : rule,
    );
    onSortChange(next);
  };

  const moveSortRule = (from: number, to: number) => {
    if (!onSortChange || from === to) {
      return;
    }
    if (to < 0 || to >= effectiveSortState.length) {
      return;
    }
    const next = [...effectiveSortState];
    const [rule] = next.splice(from, 1);
    next.splice(to, 0, rule);
    onSortChange(next);
  };

  const removeSortRule = (index: number) => {
    if (!onSortChange) {
      return;
    }
    const next = effectiveSortState.filter((_, i) => i !== index);
    onSortChange(next);
  };

  const addSortRule = () => {
    if (!onSortChange || !sortOptions?.length || reachedMaxSortLevels) {
      return;
    }
    const nextField =
      sortOptions.find(
        (option) =>
          !effectiveSortState.some((rule) => rule.field === option.value),
      )?.value ?? sortOptions[0].value;
    const next = [
      ...effectiveSortState,
      {
        field: nextField,
        direction: "asc" as SortDirection,
      },
    ];
    onSortChange(next);
  };

  const renderSortPopover = () => {
    if (!hasSort || !isSortOpen || !sortOptions) {
      return null;
    }
    return (
      <div className="absolute right-0 top-full z-20 mt-2 w-64 rounded-2xl border border-neutral-200 bg-white p-4 shadow-lg">
        <p className="text-xs font-semibold text-neutral-600">Sort by</p>
        <div className="mt-3 space-y-3 text-sm text-neutral-700">
          {effectiveSortState.length === 0 ? (
            <p className="text-xs text-neutral-500">
              No sort order selected. Add a sort level below.
            </p>
          ) : (
            effectiveSortState.map((rule, index) => (
              <div
                key={`${rule.field}-${index}`}
                className="rounded-xl border border-neutral-200 p-3"
              >
                <p className="text-xs font-semibold text-neutral-500">
                  Level {index + 1}
                </p>
                <div className="mt-2 flex items-center gap-2 overflow-visible">
                  <select
                    value={rule.field}
                    onChange={(event) =>
                      handleSortRuleChange(index, {
                        field: event.target.value as Field,
                      })
                    }
                    className="flex-1 rounded-xl border border-neutral-300 px-2 py-1 text-sm text-neutral-800 focus:border-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-900/20"
                  >
                    {sortOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() =>
                      handleSortRuleChange(index, {
                        direction:
                          rule.direction === "asc"
                            ? ("desc" as SortDirection)
                            : ("asc" as SortDirection),
                      })
                    }
                    className="inline-flex min-w-[3.5rem] items-center justify-center rounded-full border border-neutral-300 px-3 py-1 text-xs font-semibold text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
                  >
                    {rule.direction === "asc" ? "Asc" : "Desc"}
                  </button>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-neutral-500">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => moveSortRule(index, index - 1)}
                      disabled={index === 0}
                      className={`rounded-full border px-2 py-1 ${
                        index === 0
                          ? "cursor-not-allowed border-neutral-200 text-neutral-300"
                          : "border-neutral-300 text-neutral-600 hover:border-neutral-900 hover:text-neutral-900"
                      }`}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={() => moveSortRule(index, index + 1)}
                      disabled={index === effectiveSortState.length - 1}
                      className={`rounded-full border px-2 py-1 ${
                        index === effectiveSortState.length - 1
                          ? "cursor-not-allowed border-neutral-200 text-neutral-300"
                          : "border-neutral-300 text-neutral-600 hover:border-neutral-900 hover:text-neutral-900"
                      }`}
                    >
                      ↓
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeSortRule(index)}
                    className="text-neutral-500 underline-offset-2 hover:underline"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="mt-4 flex flex-col gap-2 text-xs font-medium">
          <button
            type="button"
            onClick={() => onSortChange?.([])}
            className="text-left text-neutral-500 underline-offset-2 hover:underline"
          >
            Clear all sorts
          </button>
          <button
            type="button"
            onClick={addSortRule}
            disabled={reachedMaxSortLevels}
            className={`rounded-full border px-3 py-1 ${
              reachedMaxSortLevels
                ? "cursor-not-allowed border-neutral-200 text-neutral-300"
                : "border-neutral-900 text-neutral-900"
            }`}
          >
            Add sort level
          </button>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={() => setSortOpen(false)}
            className="rounded-full bg-neutral-900 px-3 py-1 text-xs font-semibold text-white"
          >
            Done
          </button>
        </div>
      </div>
    );
  };

  const primarySortLabel = effectiveSortState[0]
    ? `${
        sortOptions?.find(
          (option) => option.value === effectiveSortState[0].field,
        )?.label ?? effectiveSortState[0].field
      } ${effectiveSortState[0].direction === "asc" ? "↑" : "↓"}${
        effectiveSortState.length > 1
          ? ` +${effectiveSortState.length - 1}`
          : ""
      }`
    : "Choose";
  const activeFiltersCount = filters
    ? filters.fields.reduce((count, field) => {
        if (field.type === "text") {
          return count + field.selectedValues.length;
        }
        if (field.type === "number") {
          return count + (hasNumericSelection(field.range) ? 1 : 0);
        }
        return count + (hasDateSelection(field.range) ? 1 : 0);
      }, 0)
    : 0;

  return (
    <div className={className}>
      <div className="relative flex-1">
        <input
          type="search"
          value={searchValue}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={searchPlaceholder}
          aria-label={searchLabel}
          className={`w-full rounded-2xl border border-neutral-300 bg-white px-4 py-3 text-sm text-neutral-900 outline-none shadow-sm transition focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20 ${
            searchInputClassName ?? ""
          }`}
          {...searchInputProps}
        />
        {searchResults}
      </div>
      {hasFilters ? (
        <div className="relative">
          <button
            type="button"
            disabled={filterDisabled}
            onClick={() => {
              if (filterDisabled) {
                return;
              }
              setFilterOpen((open) => {
                const next = !open;
                filters?.onVisibilityChange?.(next);
                return next;
              });
              setSortOpen(false);
            }}
            className={`rounded-full border px-3 py-2 text-xs font-medium transition ${
              filterDisabled
                ? "cursor-not-allowed border-neutral-200 text-neutral-300"
                : "border-neutral-300 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
            }`}
          >
            {activeFiltersCount > 0
              ? `Filters (${activeFiltersCount})`
              : (filters?.buttonLabel ?? "Filters +")}
          </button>
          {renderFilterPopover()}
        </div>
      ) : null}
      {hasSort ? (
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setSortOpen((open) => !open);
              setFilterOpen(false);
            }}
            className="rounded-full border border-neutral-300 px-3 py-2 text-xs font-medium text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
          >
            Sort: {primarySortLabel}
          </button>
          {renderSortPopover()}
        </div>
      ) : null}
    </div>
  );
}

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

function NumericFilterEditor({
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
              ? `Less than…`
              : current.mode === "gt"
                ? `Greater than…`
                : `Equal to…`
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

function DateFilterEditor({
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

function hasNumericSelection(range: NumericRange | null): boolean {
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

function hasDateSelection(range: DateRange | null): boolean {
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
