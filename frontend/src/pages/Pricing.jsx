import React, { useState, useEffect } from "react";
import AppHeader from "@/components/app/AppHeader";
import { Button } from "@/components/ui/button";
import { Sparkles, CheckCircle2, Zap, ShieldCheck, ArrowRight, Loader2, Globe } from "lucide-react";
import axios from "axios";
import { API, useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { useLocation } from "react-router-dom";
import CustomTopupCard from "@/components/app/CustomTopupCard";

export default function Pricing() {
  const { authHeaders, user } = useAuth();
  const [currency, setCurrency] = useState(() => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      return tz.includes("Manila") ? "PHP" : "USD";
    } catch {
      return "PHP";
    }
  });
  const [topups, setTopups] = useState([]);
  const [loadingPkg, setLoadingPkg] = useState(null);
  const [fetching, setFetching] = useState(true);
  const location = useLocation();

  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (query.get("status") === "cancelled") {
      toast.info("Checkout was cancelled. No charges were made.");
    }
  }, [location]);

  useEffect(() => {
    async function loadTopups() {
      setFetching(true);
      try {
        const res = await axios.get(`${API}/payments/packages?category=topup&currency=${currency}`);
        if (res.data?.topups) {
          setTopups(res.data.topups);
        } else if (res.data?.packages) {
          setTopups(res.data.packages);
        }
      } catch (err) {
        toast.error("Could not load credit refill options. Please try again.");
      } finally {
        setFetching(false);
      }
    }
    loadTopups();
  }, [currency]);

  const handleCheckout = async (packageId, customCredits = null) => {
    setLoadingPkg(packageId);
    try {
      const payload = { package_id: packageId, currency: currency };
      if (customCredits) {
        payload.custom_credits = customCredits;
      }
      const res = await axios.post(
        `${API}/payments/checkout`,
        payload,
        { headers: authHeaders }
      );

      if (res.data?.checkout_url) {
        window.location.href = res.data.checkout_url;
      } else {
        toast.error("Failed to generate checkout URL.");
      }
    } catch (err) {
      const msg = err.response?.data?.detail || "Could not initiate payment. Please try again.";
      toast.error(msg);
    } finally {
      setLoadingPkg(null);
    }
  };

  const currSymbol = currency === "USD" ? "$" : "₱";
  const currLabel = currency === "USD" ? "USD" : "PHP";

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-[#F5F5F5]">
      <AppHeader />

      <main className="max-w-[1300px] mx-auto px-6 py-14">
        {/* Header Hero */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium mb-4">
            <Zap className="w-3.5 h-3.5" />
            Pay-As-You-Go AI Credit Refills
          </div>
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white mb-3">
            Top Up Your AI Credits
          </h1>
          <p className="text-neutral-400 text-sm sm:text-base leading-relaxed">
            One-time credit refills with zero recurring subscriptions. Choose a quick refill pack or specify exact applications needed with our custom calculator.
          </p>
          {user && (
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-1.5 rounded-lg bg-[#171717] border border-[#262626] text-xs text-neutral-300">
              Current balance: <span className="font-semibold text-blue-400">{user.credits || 0} credits</span>
            </div>
          )}
        </div>

        {/* Currency Switcher */}
        <div className="flex flex-col items-center justify-center mb-10">
          <div className="inline-flex items-center p-1 rounded-xl bg-[#141414] border border-[#262626] shadow-lg">
            <button
              type="button"
              onClick={() => setCurrency("PHP")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                currency === "PHP"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              <span>🇵🇭</span>
              <span>Philippines (PHP ₱)</span>
            </button>
            <button
              type="button"
              onClick={() => setCurrency("USD")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                currency === "USD"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              <span>🌎</span>
              <span>International (USD $)</span>
            </button>
          </div>
          <div className="text-[11px] text-neutral-500 mt-2 flex items-center gap-1.5">
            <Globe className="w-3 h-3" />
            {currency === "PHP"
              ? "Accepts GCash, Maya, QR Ph, and local/international cards"
              : "Billed securely in USD via international credit & debit cards"}
          </div>
        </div>

        {/* Pricing Cards Grid */}
        {fetching ? (
          <div className="flex justify-center items-center py-20 text-neutral-500">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500 mr-3" />
            Loading credit options...
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 items-stretch mb-10">
            {topups.map((pkg) => {
              const isPopular = pkg.popular;
              return (
                <div
                  key={pkg.id}
                  className={`relative flex flex-col rounded-2xl p-6 transition-all duration-200 ${
                    isPopular
                      ? "bg-gradient-to-b from-[#1E293B]/70 to-[#0F172A]/50 border-2 border-blue-500 shadow-xl shadow-blue-500/10"
                      : "bg-[#121212] border border-[#262626] hover:border-[#383838]"
                  }`}
                >
                  {pkg.badge && (
                    <div
                      className={`absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider ${
                        isPopular
                          ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                          : "bg-neutral-800 text-neutral-300 border border-neutral-700"
                      }`}
                    >
                      {pkg.badge}
                    </div>
                  )}

                  <div className="mb-5 pt-2">
                    <h3 className="text-lg font-semibold text-white">{pkg.name}</h3>
                    <p className="text-xs text-neutral-400 mt-1 min-h-[34px] leading-relaxed">{pkg.description}</p>
                  </div>

                  {/* Price & Rate */}
                  <div className="mb-5 pb-5 border-b border-[#262626]">
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-bold text-white tracking-tight">
                        {currSymbol}{pkg.amount}
                      </span>
                      <span className="text-xs text-neutral-400">{currLabel} / refill</span>
                    </div>
                    <div className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-md">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>{pkg.credits} {pkg.credits === 1 ? "Application" : "Applications"}</span>
                      <span className="text-neutral-500">•</span>
                      <span>{pkg.effective_price}</span>
                    </div>
                  </div>

                  {/* Features checklist */}
                  <div className="space-y-2.5 flex-1 mb-6 text-xs text-neutral-300">
                    <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-2">
                      Included with this pack:
                    </div>
                    <ul className="space-y-2">
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                        <span>
                          <strong className="text-white">{pkg.credits}</strong> {pkg.credits === 1 ? "Targeted ATS Application" : "Targeted ATS Applications"}
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                        <span>Real-Time SSE Streaming AI Engine</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                        <span>Instant ATS Score & Gap Breakdown</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                        <span>Custom Cover Letter Generator</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                        <span>Never expire — use anytime</span>
                      </li>
                    </ul>
                  </div>

                  {/* Purchase Button */}
                  <Button
                    onClick={() => handleCheckout(pkg.id)}
                    disabled={loadingPkg !== null}
                    className={`w-full py-5 font-medium flex items-center justify-center gap-2 ${
                      isPopular
                        ? "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/25"
                        : "bg-[#1F1F1F] hover:bg-[#2A2A2A] text-white border border-[#333]"
                    }`}
                  >
                    {loadingPkg === pkg.id ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Preparing Checkout...
                      </>
                    ) : (
                      <>
                        <span>Add {pkg.credits} Credits</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
        )}

        {/* Custom Refill Interactive Section */}
        <div className="mt-8">
          <CustomTopupCard
            currency={currency}
            onCheckout={handleCheckout}
            loading={loadingPkg === "custom"}
          />
        </div>

        {/* Security & Payment methods footer */}
        <div className="mt-16 pt-10 border-t border-[#262626] flex flex-col md:flex-row items-center justify-between gap-6 text-xs text-neutral-400">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <div className="text-white font-medium">Secured by PayMongo</div>
              <div>End-to-end 256-bit encrypted checkout. PCI-DSS compliant.</div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-neutral-500 mr-1">Accepted Payment Methods:</span>
            {currency === "PHP" && (
              <>
                <span className="px-2.5 py-1 rounded bg-[#171717] border border-[#262626] font-medium text-neutral-300">
                  GCash
                </span>
                <span className="px-2.5 py-1 rounded bg-[#171717] border border-[#262626] font-medium text-neutral-300">
                  Maya
                </span>
                <span className="px-2.5 py-1 rounded bg-[#171717] border border-[#262626] font-medium text-neutral-300">
                  QR Ph
                </span>
              </>
            )}
            <span className="px-2.5 py-1 rounded bg-[#171717] border border-[#262626] font-medium text-neutral-300">
              Visa / Mastercard
            </span>
            <span className="px-2.5 py-1 rounded bg-[#171717] border border-[#262626] font-medium text-neutral-300">
              Debit Cards
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
