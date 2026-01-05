import { useMemo, useState } from "react";
import { buildSearchableOptions } from "../form-utils";

type UseLocationSelectionArgs = {
  locationNamesById: Record<number, string>;
  defaultLocationId: number | null;
};

export function useLocationSelection({
  locationNamesById,
  defaultLocationId,
}: UseLocationSelectionArgs) {
  const defaultLocationName =
    (defaultLocationId && locationNamesById[defaultLocationId]) || "";
  const [locationId, setLocationId] = useState<number | null>(
    defaultLocationId,
  );
  const [locationError, setLocationError] = useState(false);
  const locationOptions = useMemo(
    () => buildSearchableOptions(locationNamesById),
    [locationNamesById],
  );
  return {
    locationId,
    setLocationId,
    locationError,
    setLocationError,
    locationOptions,
    defaultLocationName,
  };
}
