"use client";

import type { SortDirection, SortOption, SortRule } from "./types";

type SortMenuProps<Field extends string> = {
  sortOptions: SortOption<Field>[];
  sortState: SortRule<Field>[];
  reachedMaxSortLevels: boolean;
  onSortChange: (rules: SortRule<Field>[]) => void;
  onClose: () => void;
};

export function SortMenu<Field extends string>({
  sortOptions,
  sortState,
  reachedMaxSortLevels,
  onSortChange,
  onClose,
}: SortMenuProps<Field>) {
  const handleSortRuleChange = (
    index: number,
    update: Partial<SortRule<Field>>,
  ) => {
    if (!sortState[index]) {
      return;
    }
    const next = sortState.map((rule, i) =>
      i === index ? { ...rule, ...update } : rule,
    );
    onSortChange(next);
  };

  const moveSortRule = (from: number, to: number) => {
    if (from === to || to < 0 || to >= sortState.length) {
      return;
    }
    const next = [...sortState];
    const [rule] = next.splice(from, 1);
    next.splice(to, 0, rule);
    onSortChange(next);
  };

  const removeSortRule = (index: number) => {
    const next = sortState.filter((_, i) => i !== index);
    onSortChange(next);
  };

  const addSortRule = () => {
    if (!sortOptions.length || reachedMaxSortLevels) {
      return;
    }
    const nextField =
      sortOptions.find(
        (option) => !sortState.some((rule) => rule.field === option.value),
      )?.value ?? sortOptions[0].value;
    const next = [
      ...sortState,
      {
        field: nextField,
        direction: "asc" as SortDirection,
      },
    ];
    onSortChange(next);
  };

  return (
    <div className="absolute right-0 top-full z-20 mt-2 w-64 rounded-2xl border border-neutral-200 bg-white p-4 shadow-lg">
      <p className="text-xs font-semibold text-neutral-600">Sort by</p>
      <div className="mt-3 space-y-3 text-sm text-neutral-700">
        {sortState.length === 0 ? (
          <p className="text-xs text-neutral-500">
            No sort order selected. Add a sort level below.
          </p>
        ) : (
          sortState.map((rule, index) => (
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
                    disabled={index === sortState.length - 1}
                    className={`rounded-full border px-2 py-1 ${
                      index === sortState.length - 1
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
          onClick={() => onSortChange([])}
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
          onClick={onClose}
          className="rounded-full bg-neutral-900 px-3 py-1 text-xs font-semibold text-white"
        >
          Done
        </button>
      </div>
    </div>
  );
}
