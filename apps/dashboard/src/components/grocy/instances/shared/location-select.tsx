import type { SearchableOption } from "../searchable-option-select";
import { SearchableOptionSelect } from "../searchable-option-select";

type Props = {
  label?: string;
  options: SearchableOption[];
  selectedId: number | null;
  onSelectedIdChange: (id: number | null) => void;
  defaultOptionId: number | null;
  defaultOptionLabel: string;
  placeholder?: string;
  resetLabel?: string;
  onValidationChange: (hasError: boolean) => void;
  errorMessage: string;
  helperText?: string;
  allowCustomValue?: boolean;
  inputValue?: string;
  onInputValueChange?: (value: string) => void;
};

export function LocationSelect({
  label = "Location",
  options,
  selectedId,
  onSelectedIdChange,
  defaultOptionId,
  defaultOptionLabel,
  placeholder = "Search locations…",
  resetLabel = "Use default",
  onValidationChange,
  errorMessage,
  helperText,
  allowCustomValue = false,
  inputValue,
  onInputValueChange,
}: Props) {
  return (
    <SearchableOptionSelect
      label={label}
      options={options}
      selectedId={selectedId}
      onSelectedIdChange={onSelectedIdChange}
      defaultOptionId={defaultOptionId}
      defaultOptionLabel={defaultOptionLabel}
      placeholder={placeholder}
      resetLabel={resetLabel}
      onValidationChange={onValidationChange}
      errorMessage={errorMessage}
      helperText={helperText}
      allowCustomValue={allowCustomValue}
      inputValue={inputValue}
      onInputValueChange={onInputValueChange}
    />
  );
}
