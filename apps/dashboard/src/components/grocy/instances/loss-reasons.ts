import type { InventoryLossReason } from "@/lib/grocy/types";

export const LOSS_REASON_OPTIONS: Array<{
  value: InventoryLossReason;
  label: string;
}> = [
  { value: "spoilage", label: "Spoilage / expired" },
  { value: "breakage", label: "Breakage / damaged" },
  { value: "overportion", label: "Over-portioning / overuse" },
  { value: "theft", label: "Missing / suspected theft" },
  { value: "quality_reject", label: "Quality rejection" },
  { value: "process_error", label: "Process / production error" },
  { value: "other", label: "Other / misc." },
];

export const LOSS_REASON_LABELS = LOSS_REASON_OPTIONS.reduce<
  Record<string, string>
>((acc, option) => {
  acc[option.value] = option.label;
  return acc;
}, {});
