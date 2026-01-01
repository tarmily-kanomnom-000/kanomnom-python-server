import { useRef } from "react";

export function useLatest<T>(value: T): { readonly current: T } {
  const ref = useRef<T>(value);
  ref.current = value;
  return ref;
}
