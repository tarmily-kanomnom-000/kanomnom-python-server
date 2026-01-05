type StatusMessageProps = {
  status: {
    type: "success" | "error";
    text: string;
  } | null;
};

export function StatusMessage({ status }: StatusMessageProps) {
  if (!status) {
    return null;
  }
  return (
    <p
      className={`rounded-2xl px-4 py-3 text-sm ${
        status.type === "success"
          ? "bg-emerald-50 text-emerald-800"
          : "bg-rose-50 text-rose-700"
      }`}
    >
      {status.text}
    </p>
  );
}
