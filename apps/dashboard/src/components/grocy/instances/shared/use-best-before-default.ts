import { useMemo, useState } from "react";
import { computeDefaultBestBeforeDate } from "../form-utils";

export function useBestBeforeDefault(defaultDays: number) {
  const defaultValue = useMemo(
    () => computeDefaultBestBeforeDate(defaultDays),
    [defaultDays],
  );
  const [value, setValue] = useState(defaultValue);
  const reset = () => setValue(defaultValue);
  return { value, setValue, reset, defaultValue };
}
