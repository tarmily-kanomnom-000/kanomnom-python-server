"use client";

import { useCallback, useRef, useState } from "react";

export function useDirtyStringField(initialValue: string) {
  const [value, setValue] = useState(initialValue);
  const dirtyRef = useRef(false);

  const set = useCallback((nextValue: string) => {
    dirtyRef.current = true;
    setValue(nextValue);
  }, []);

  const hydrate = useCallback((nextValue: string) => {
    if (dirtyRef.current) {
      return;
    }
    setValue(nextValue);
  }, []);

  const reset = useCallback(
    (nextValue: string = initialValue) => {
      dirtyRef.current = false;
      setValue(nextValue);
    },
    [initialValue],
  );

  const forceSet = useCallback((nextValue: string) => {
    dirtyRef.current = false;
    setValue(nextValue);
  }, []);

  return {
    value,
    set,
    hydrate,
    reset,
    forceSet,
  };
}
