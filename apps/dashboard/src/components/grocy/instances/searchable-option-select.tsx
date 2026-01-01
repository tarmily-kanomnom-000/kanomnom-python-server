"use client";

import { useCallback, useEffect, useId, useMemo, useState } from "react";

export type SearchableOption = {
  id: number;
  name: string;
};

type SearchableOptionSelectProps = {
  label: string;
  options: SearchableOption[];
  selectedId: number | null;
  onSelectedIdChange: (value: number | null) => void;
  defaultOptionId: number | null;
  defaultOptionLabel: string;
  placeholder?: string;
  helperText?: string;
  resetLabel?: string;
  onValidationChange?: (hasError: boolean) => void;
  errorMessage?: string;
  inputValue?: string | null;
  onInputValueChange?: (value: string) => void;
  allowCustomValue?: boolean;
};

export function SearchableOptionSelect({
  label,
  options,
  selectedId,
  onSelectedIdChange,
  defaultOptionId,
  defaultOptionLabel,
  placeholder = "Search…",
  helperText,
  resetLabel = "Use default",
  onValidationChange,
  errorMessage = "Select a value from the list to continue.",
  inputValue: inputValueProp = null,
  onInputValueChange,
  allowCustomValue = false,
}: SearchableOptionSelectProps) {
  const [uncontrolledInputValue, setUncontrolledInputValue] = useState(() => {
    if (inputValueProp !== null) {
      return inputValueProp;
    }
    if (selectedId !== null) {
      const matched = options.find((option) => option.id === selectedId);
      if (matched) {
        return matched.name;
      }
    }
    if (defaultOptionId !== null && defaultOptionLabel) {
      return defaultOptionLabel;
    }
    return "";
  });
  const [isDropdownOpen, setDropdownOpen] = useState(false);
  const dropdownId = useId();
  const inputValue =
    inputValueProp !== null ? inputValueProp : uncontrolledInputValue;
  const setInputValue = useCallback(
    (nextValue: string) => {
      if (inputValueProp === null) {
        setUncontrolledInputValue(nextValue);
      }
      onInputValueChange?.(nextValue);
    },
    [inputValueProp, onInputValueChange],
  );

  useEffect(() => {
    if (selectedId === null) {
      return;
    }
    const matched = options.find((option) => option.id === selectedId);
    if (matched) {
      setInputValue(matched.name);
    }
  }, [selectedId, options, setInputValue]);

  useEffect(() => {
    const normalized = inputValue.trim().toLowerCase();
    if (!normalized) {
      return;
    }
    const matched = options.find(
      (option) => option.name.trim().toLowerCase() === normalized,
    );
    if (!matched || matched.id === selectedId) {
      return;
    }
    onSelectedIdChange(matched.id);
    setInputValue(matched.name);
  }, [inputValue, options, onSelectedIdChange, selectedId, setInputValue]);

  const suggestions = useMemo(() => {
    const normalized = inputValue.trim().toLowerCase();
    if (!normalized) {
      return options.slice(0, 8);
    }
    return options
      .filter((option) => option.name.toLowerCase().includes(normalized))
      .slice(0, 8);
  }, [inputValue, options]);

  const hasError =
    inputValue.trim().length > 0 &&
    (selectedId === null || selectedId < 0) &&
    !allowCustomValue;
  useEffect(() => {
    onValidationChange?.(hasError);
  }, [hasError, onValidationChange]);

  const handleReset = () => {
    if (defaultOptionId !== null && defaultOptionLabel) {
      setInputValue(defaultOptionLabel);
      onSelectedIdChange(defaultOptionId);
    } else {
      setInputValue("");
      onSelectedIdChange(null);
    }
    if (inputValueProp !== null) {
      onInputValueChange?.(
        defaultOptionId !== null && defaultOptionLabel
          ? defaultOptionLabel
          : "",
      );
    }
  };

  const resetDisabled = defaultOptionId === null && !defaultOptionLabel;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          {label}
        </label>
        {!resetDisabled ? (
          <button
            type="button"
            onClick={handleReset}
            className="rounded-full border border-neutral-200 px-3 py-1 text-[11px] font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
          >
            {resetLabel}
          </button>
        ) : null}
      </div>
      <div className="relative flex gap-2">
        <input
          value={inputValue}
          onChange={(event) => {
            setInputValue(event.target.value);
            onSelectedIdChange(null);
          }}
          onFocus={() => setDropdownOpen(true)}
          onBlur={() => {
            setTimeout(() => setDropdownOpen(false), 120);
          }}
          className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:outline-none ${
            hasError
              ? "border-rose-400 focus:border-rose-500"
              : "border-neutral-200 focus:border-neutral-900"
          }`}
          placeholder={placeholder}
          aria-expanded={isDropdownOpen}
          aria-controls={dropdownId}
        />
        {isDropdownOpen && suggestions.length ? (
          <div
            id={dropdownId}
            className="absolute left-0 top-12 z-10 max-h-60 w-full overflow-y-auto rounded-2xl border border-neutral-200 bg-white shadow-lg"
          >
            {suggestions.map((option) => (
              <button
                key={option.id}
                type="button"
                className="block w-full px-4 py-2 text-left text-sm text-neutral-800 hover:bg-neutral-100"
                onMouseDown={(event) => {
                  event.preventDefault();
                  setInputValue(option.name);
                  onSelectedIdChange(option.id);
                  setDropdownOpen(false);
                }}
              >
                {option.name}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {hasError ? (
        <p className="text-xs text-rose-600">{errorMessage}</p>
      ) : helperText ? (
        <p className="text-xs text-neutral-500">{helperText}</p>
      ) : null}
    </div>
  );
}
