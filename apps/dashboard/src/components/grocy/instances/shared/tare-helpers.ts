export function toGross(net: number, tareWeight: number): number {
  return net + tareWeight;
}

export function toNet(gross: number, tareWeight: number): number {
  return Math.max(gross - tareWeight, 0);
}

export const TARE_HELPER_COPY = {
  grossLabel: "Gross includes tare",
  netLabel: "Net excludes tare",
};
