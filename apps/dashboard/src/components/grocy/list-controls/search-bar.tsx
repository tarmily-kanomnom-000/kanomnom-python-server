"use client";

import type { InputHTMLAttributes, ReactNode } from "react";

type SearchBarProps = {
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  inputProps?: Omit<
    InputHTMLAttributes<HTMLInputElement>,
    "type" | "value" | "onChange" | "placeholder"
  >;
  results?: ReactNode;
};

export function SearchBar({
  label,
  placeholder,
  value,
  onChange,
  className,
  inputProps,
  results,
}: SearchBarProps) {
  return (
    <div className="relative flex-1">
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={label}
        className={`w-full rounded-2xl border border-neutral-300 bg-white px-4 py-3 text-sm text-neutral-900 outline-none shadow-sm transition focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/20 ${
          className ?? ""
        }`}
        {...inputProps}
      />
      {results}
    </div>
  );
}
