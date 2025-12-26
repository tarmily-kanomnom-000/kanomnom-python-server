"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useState,
} from "react";

import { useBrowserSearchParams } from "@/hooks/use-browser-search-params";
import { useQueryParamUpdater } from "@/hooks/use-query-param-updater";

type UseSyncedQueryStateOptions<T> = {
  key: string;
  parse: (rawValue: string | null) => T;
  serialize: (value: T) => string | null;
  isEqual?: (a: T, b: T) => boolean;
};

export function useSyncedQueryState<T>(
  options: UseSyncedQueryStateOptions<T>,
): [T, Dispatch<SetStateAction<T>>] {
  const { key, parse, serialize, isEqual = Object.is } = options;
  const searchParams = useBrowserSearchParams();
  const updateQueryParams = useQueryParamUpdater();

  const [value, setValue] = useState<T>(() => parse(searchParams.get(key)));

  useEffect(() => {
    const next = parse(searchParams.get(key));
    setValue((current) => (isEqual(current, next) ? current : next));
  }, [searchParams, key, parse, isEqual]);

  const setSyncedValue: Dispatch<SetStateAction<T>> = useCallback(
    (nextValue) => {
      setValue((current) => {
        const resolvedValue =
          typeof nextValue === "function"
            ? (nextValue as (previous: T) => T)(current)
            : nextValue;
        if (isEqual(current, resolvedValue)) {
          return current;
        }
        updateQueryParams({ [key]: serialize(resolvedValue) });
        return resolvedValue;
      });
    },
    [key, serialize, updateQueryParams, isEqual],
  );

  return [value, setSyncedValue];
}
