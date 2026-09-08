/**
 * Authoritative client-side calculation mirror for Recraftr pricing & custom refills.
 * Matches backend paymongo_service.py exactly.
 */

export function calculateCustomTopup(credits, currency = "PHP") {
  const count = Math.max(5, Math.min(500, Math.round(Number(credits) || 5)));
  const isUsd = (currency || "").toUpperCase() === "USD";

  let rate;
  if (count < 10) {
    rate = isUsd ? 0.40 : 7.80;
  } else if (count < 20) {
    rate = isUsd ? 0.35 : 6.90;
  } else if (count < 50) {
    rate = isUsd ? 0.30 : 5.95;
  } else {
    rate = isUsd ? 0.24 : 4.95;
  }

  const total = Number((count * rate).toFixed(2));
  const effective = isUsd ? `$${rate.toFixed(2)}/app` : `₱${rate.toFixed(2)}/app`;

  return {
    id: `custom_${count}`,
    name: `${count} Custom Applications`,
    credits: count,
    amount: total,
    rate: rate,
    currency: isUsd ? "USD" : "PHP",
    effective_price: effective,
    is_custom: true,
  };
}
