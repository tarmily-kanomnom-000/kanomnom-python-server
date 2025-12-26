export type PurchaseCurrencyOption = {
  value: string;
  label: string;
};

const DEFAULT_PURCHASE_CURRENCIES: PurchaseCurrencyOption[] = [
  { value: "USD", label: "USD (United States Dollar)" },
  { value: "THB", label: "THB (Thai Baht)" },
];

export const purchaseCurrencyOptions: PurchaseCurrencyOption[] =
  DEFAULT_PURCHASE_CURRENCIES;

export const defaultPurchaseCurrency: string =
  purchaseCurrencyOptions[0]?.value ?? "USD";
