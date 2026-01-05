import type { SearchableOption } from "../searchable-option-select";
import { LocationSelect } from "./location-select";

type PurchaseLocationSectionProps = {
  shoppingLocationOptions: SearchableOption[];
  shoppingLocationId: number | null;
  shoppingLocationName: string;
  defaultShoppingLocationId: number | null;
  defaultShoppingLocationName: string;
  onShoppingLocationIdChange: (id: number | null) => void;
  onShoppingLocationNameChange: (value: string) => void;
  setShoppingLocationError: (hasError: boolean) => void;
  locationOptions: SearchableOption[];
  locationId: number | null;
  defaultLocationId: number | null;
  defaultLocationName: string;
  onLocationIdChange: (id: number | null) => void;
  setLocationError: (hasError: boolean) => void;
};

export function PurchaseLocationSection({
  shoppingLocationOptions,
  shoppingLocationId,
  shoppingLocationName,
  defaultShoppingLocationId,
  defaultShoppingLocationName,
  onShoppingLocationIdChange,
  onShoppingLocationNameChange,
  setShoppingLocationError,
  locationOptions,
  locationId,
  defaultLocationId,
  defaultLocationName,
  onLocationIdChange,
  setLocationError,
}: PurchaseLocationSectionProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <LocationSelect
        label="Shopping location"
        options={shoppingLocationOptions}
        selectedId={shoppingLocationId}
        onSelectedIdChange={onShoppingLocationIdChange}
        defaultOptionId={defaultShoppingLocationId}
        defaultOptionLabel={defaultShoppingLocationName}
        placeholder="Search shopping locations…"
        resetLabel="Use default"
        onValidationChange={setShoppingLocationError}
        errorMessage="Select or enter a shopping location to continue."
        helperText="Type a new name to create it when you record the purchase."
        allowCustomValue
        inputValue={shoppingLocationName}
        onInputValueChange={onShoppingLocationNameChange}
      />
      <LocationSelect
        label="Location"
        options={locationOptions}
        selectedId={locationId}
        onSelectedIdChange={onLocationIdChange}
        defaultOptionId={defaultLocationId}
        defaultOptionLabel={defaultLocationName}
        placeholder="Search locations…"
        resetLabel="Use default"
        onValidationChange={setLocationError}
        errorMessage="Select a location from the list to continue."
      />
    </div>
  );
}
