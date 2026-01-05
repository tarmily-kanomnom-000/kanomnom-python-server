"use client";

import type { InputHTMLAttributes, ReactNode } from "react";

export type SortDirection = "asc" | "desc";

export type SortOption<Field extends string> = {
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

export type FilterFieldBase = {
  id: string;
  label: string;
  onClear: () => void;
};

export type TextFilterFieldConfig = FilterFieldBase & {
  type: "text";
  values: string[];
  selectedValues: string[];
  onToggle: (value: string) => void;
};

export type NumberFilterFieldConfig = FilterFieldBase & {
  type: "number";
  range: NumericRange | null;
  onRangeChange: (range: NumericRange | null) => void;
};

export type DateFilterFieldConfig = FilterFieldBase & {
  type: "date";
  range: DateRange | null;
  onRangeChange: (range: DateRange | null) => void;
};

export type FilterFieldConfig =
  | TextFilterFieldConfig
  | NumberFilterFieldConfig
  | DateFilterFieldConfig;

export type FilterConfig = {
  fields: FilterFieldConfig[];
  buttonLabel?: string;
  disabled?: boolean;
  onVisibilityChange?: (isVisible: boolean) => void;
};

export type ListControlsProps<Field extends string> = {
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
