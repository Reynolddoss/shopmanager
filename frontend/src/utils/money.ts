/**
 * Money helpers — shop prices stay at two decimal places (paise).
 */

export const formatMoney = (value: string | number | null | undefined): string => {
  if (value === null || value === undefined || value === "") {
    return "0.00";
  }
  const n = typeof value === "number" ? value : Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(n)) {
    return "0.00";
  }
  return n.toFixed(2);
};

/** Format for UI when the value may be empty (show em dash instead of 0.00). */
export const formatMoneyOrDash = (value: string | number | null | undefined): string => {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const n = typeof value === "number" ? value : Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(n)) {
    return "—";
  }
  return n.toFixed(2);
};

/**
 * Keep typing friendly while capping fractional digits (default 2).
 * Allows "", "12", "12.", "12.3", "12.34" — never a third decimal.
 */
export const sanitizeDecimalInput = (raw: string, maxDecimals = 2): string => {
  const cleaned = raw.replace(/[^\d.]/g, "");
  if (!cleaned) {
    return "";
  }
  const firstDot = cleaned.indexOf(".");
  if (firstDot === -1) {
    return cleaned;
  }
  const whole = cleaned.slice(0, firstDot).replace(/\./g, "") || "0";
  const frac = cleaned
    .slice(firstDot + 1)
    .replace(/\./g, "")
    .slice(0, maxDecimals);
  return frac.length || cleaned.endsWith(".") ? `${whole}.${frac}` : whole;
};
