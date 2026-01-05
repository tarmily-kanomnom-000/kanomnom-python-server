"use client";

import { useEffect, useRef, useState } from "react";

import { FilterDrawer } from "./filter-drawer";
import { SearchBar } from "./search-bar";
import { SortMenu } from "./sort-menu";
import {
  hasDateSelection,
  hasNumericSelection,
} from "./filter-editors";
import type {
  DateRange,
  ListControlsProps,
  NumericRange,
  SortRule,
} from "./types";

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
  const filterContainerRef = useRef<HTMLDivElement | null>(null);
  const sortContainerRef = useRef<HTMLDivElement | null>(null);

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

  useEffect(() => {
    if (!isFilterOpen) {
      return;
    }
    const handleClickOutside = (event: MouseEvent | TouchEvent) => {
      if (
        filterContainerRef.current &&
        event.target instanceof Node &&
        !filterContainerRef.current.contains(event.target)
      ) {
        setFilterOpen(false);
        filters?.onVisibilityChange?.(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [filters, isFilterOpen]);

  useEffect(() => {
    if (!isSortOpen) {
      return;
    }
    const handleClickOutside = (event: MouseEvent | TouchEvent) => {
      if (
        sortContainerRef.current &&
        event.target instanceof Node &&
        !sortContainerRef.current.contains(event.target)
      ) {
        setSortOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [isSortOpen]);

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
      <SearchBar
        label={searchLabel}
        placeholder={searchPlaceholder}
        value={searchValue}
        onChange={onSearchChange}
        className={searchInputClassName}
        inputProps={searchInputProps}
        results={searchResults}
      />
      {hasFilters ? (
        <div className="relative" ref={filterContainerRef}>
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
          {isFilterOpen ? (
            <FilterDrawer
              filters={filters}
              activeFieldId={activeFilterFieldId}
              onActiveFieldChange={setActiveFilterFieldId}
              searchValue={filterSearchValue}
              onSearchValueChange={setFilterSearchValue}
              numericDraft={numericDraft}
              onNumericDraftChange={setNumericDraft}
              dateDraft={dateDraft}
              onDateDraftChange={setDateDraft}
              onClose={() => {
                setFilterOpen(false);
                filters.onVisibilityChange?.(false);
              }}
            />
          ) : null}
        </div>
      ) : null}
      {hasSort ? (
        <div className="relative" ref={sortContainerRef}>
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
          {isSortOpen && sortOptions ? (
            <SortMenu
              sortOptions={sortOptions}
              sortState={effectiveSortState}
              reachedMaxSortLevels={reachedMaxSortLevels}
              onSortChange={(rules: SortRule<Field>[]) =>
                onSortChange?.(rules)
              }
              onClose={() => setSortOpen(false)}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
