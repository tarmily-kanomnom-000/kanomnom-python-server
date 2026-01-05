import type { InventoryLossReason } from "@/lib/grocy/types";

export type LossOption = {
  value: InventoryLossReason;
  label: string;
};

export type LossEntry = { reason: InventoryLossReason; note: string };

type Props = {
  options: LossOption[];
  losses: LossEntry[];
  onChange: (next: LossEntry[]) => void;
};

export function LossTrackingSection({ options, losses, onChange }: Props) {
  const isLossReasonSelected = (reason: InventoryLossReason): boolean =>
    losses.some((entry) => entry.reason === reason);

  const handleLossReasonToggle = (reason: InventoryLossReason): void => {
    const exists = losses.find((entry) => entry.reason === reason);
    if (exists) {
      onChange(losses.filter((entry) => entry.reason !== reason));
      return;
    }
    onChange([...losses, { reason, note: "" }]);
  };

  const handleLossReasonNoteChange = (
    reason: InventoryLossReason,
    value: string,
  ): void => {
    onChange(
      losses.map((entry) =>
        entry.reason === reason ? { ...entry, note: value } : entry,
      ),
    );
  };

  return (
    <div className="rounded-2xl border border-neutral-100 bg-neutral-50">
      <details className="group">
        <summary className="flex cursor-pointer items-center justify-between px-4 py-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Loss tracking
            </p>
            <p className="mt-1 text-xs text-neutral-500">
              Select reasons that contributed to this adjustment.
            </p>
          </div>
          <span className="text-neutral-500 transition group-open:rotate-180">
            ▼
          </span>
        </summary>
        <div className="space-y-3 px-4 pb-4">
          {options.map((option) => {
            const selected = isLossReasonSelected(option.value);
            const currentEntry = losses.find(
              (entry) => entry.reason === option.value,
            );
            return (
              <div
                key={option.value}
                className="rounded-2xl border border-neutral-100 bg-white p-3"
              >
                <label className="flex items-center gap-2 text-sm text-neutral-800">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => handleLossReasonToggle(option.value)}
                  />
                  {option.label}
                </label>
                {selected ? (
                  <div className="mt-2">
                    <textarea
                      value={currentEntry?.note ?? ""}
                      onChange={(event) =>
                        handleLossReasonNoteChange(
                          option.value,
                          event.target.value,
                        )
                      }
                      rows={2}
                      className="w-full resize-none rounded-2xl border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-neutral-900 focus:outline-none"
                      placeholder="Notes about this loss (optional)"
                    />
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </details>
    </div>
  );
}
