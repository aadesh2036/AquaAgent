/**
 * Unit conversions — TypeScript twin of shared/units.py (BACKBONE §5.2).
 * The frontend may only FORMAT values (e.g. L/s → L/min for display). It never derives
 * hydraulic quantities (BACKBONE P1, §7.15).
 */

export const FT_TO_M = 0.3048;
export const IN_TO_M = 0.0254;
export const US_GAL_TO_M3 = 3.785411784e-3;
export const GPM_TO_M3S = US_GAL_TO_M3 / 60;
export const SECONDS_PER_DAY = 86_400;

export const m3sToLps = (q: number): number => q * 1000;
export const lpsToM3s = (q: number): number => q / 1000;
export const lpsToLpm = (q: number): number => q * 60;
export const lpmToLps = (q: number): number => q / 60;
export const gpmToM3s = (q: number): number => q * GPM_TO_M3S;
export const gpmToLps = (q: number): number => m3sToLps(gpmToM3s(q));

export const ftToM = (x: number): number => x * FT_TO_M;
export const mToFt = (x: number): number => x / FT_TO_M;
export const inToM = (x: number): number => x * IN_TO_M;
export const mToMm = (x: number): number => x * 1000;
export const mmToM = (x: number): number => x / 1000;

export const m2ToCm2 = (a: number): number => a * 10_000;
export const cm2ToM2 = (a: number): number => a / 10_000;

export const fractionToPct = (x: number): number => x * 100;

export function timeOfDayS(simTimeS: number): number {
  return ((Math.trunc(simTimeS) % SECONDS_PER_DAY) + SECONDS_PER_DAY) % SECONDS_PER_DAY;
}

export function clockLabel(simTimeS: number): string {
  const tod = timeOfDayS(simTimeS);
  const hh = Math.floor(tod / 3600);
  const mm = Math.floor((tod % 3600) / 60);
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

/** Display formatting helper: fixed decimals with unit label. */
export function fmt(value: number | null | undefined, unit: string, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return `— ${unit}`;
  return `${value.toFixed(digits)} ${unit}`;
}
