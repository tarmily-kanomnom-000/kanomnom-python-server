type DateFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onUseDefault: () => void;
};

export function DateField({
  label,
  value,
  onChange,
  onUseDefault,
}: DateFieldProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          {label}
        </label>
        <button
          type="button"
          onClick={onUseDefault}
          className="rounded-full border border-neutral-200 px-3 py-1 text-[11px] font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
        >
          Use default
        </button>
      </div>
      <div className="flex gap-2">
        <input
          type="date"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
        />
      </div>
    </div>
  );
}
