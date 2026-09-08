import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Sparkles, Zap, ShieldCheck, ArrowRight, Loader2, Globe, Sliders } from "lucide-react";
import axios from "axios";
import { API, useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import CustomTopupCard from "./CustomTopupCard";

export default function TopUpModal({ open, onOpenChange }) {
  const { authHeaders, user } = useAuth();
  const [currency, setCurrency] = useState(() => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      return tz.includes("Manila") ? "PHP" : "USD";
    } catch {
      return "PHP";
    }
  });
  const [mode, setMode] = useState("presets"); // "presets" | "custom"
  const [topups, setTopups] = useState([]);
  const [loadingPkg, setLoadingPkg] = useState(null);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    if (!open) return;

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
        toast.error("Could not load credit refill packs.");
      } finally {
        setFetching(false);
      }
    }
    loadTopups();
  }, [open, currency]);

  const handleCheckout = async (packageId, customCredits = null) => {
    setLoadingPkg(packageId);
    try {
      const payload = {
        package_id: packageId,
        currency: currency,
        success_url: `${window.location.origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${window.location.href}`,
      };
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
      const msg = err.response?.data?.detail || "Could not initiate top-up. Please try again.";
      toast.error(msg);
    } finally {
      setLoadingPkg(null);
    }
  };

  const currSymbol = currency === "USD" ? "$" : "₱";
  const currLabel = currency === "USD" ? "USD" : "PHP";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-[#0F0F0F] border border-[#262626] text-white p-6 sm:p-8 rounded-2xl shadow-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader className="text-left space-y-2 mb-3">
          <div className="flex items-center justify-between">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium">
              <Zap className="w-3.5 h-3.5" />
              In-App Credit Refill
            </div>
            {user && (
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-[#171717] border border-[#262626] text-xs text-neutral-300">
                <span>Balance:</span>
                <span className="font-semibold text-blue-400">{user.credits || 0} credits</span>
              </div>
            )}
          </div>
          <DialogTitle className="text-2xl font-bold tracking-tight text-white">
            Top Up Your AI Credits
          </DialogTitle>
          <DialogDescription className="text-neutral-400 text-xs sm:text-sm">
            Need more applications? Refill anytime at convenience top-up rates. Credits never expire and apply across all resume optimization and cover letter tools.
          </DialogDescription>
        </DialogHeader>

        {/* Currency Switcher & Mode Switcher Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1 pb-3 border-b border-[#222]">
          {/* Mode Switcher */}
          <div className="inline-flex items-center p-0.5 rounded-lg bg-[#171717] border border-[#262626]">
            <button
              type="button"
              onClick={() => setMode("presets")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                mode === "presets"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              📦 Preset Packs
            </button>
            <button
              type="button"
              onClick={() => setMode("custom")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                mode === "custom"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              <Sliders className="w-3 h-3" />
              <span>Custom Quantity</span>
            </button>
          </div>

          {/* Currency Switcher */}
          <div className="inline-flex items-center p-0.5 rounded-lg bg-[#171717] border border-[#262626] self-start sm:self-auto">
            <button
              type="button"
              onClick={() => setCurrency("PHP")}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                currency === "PHP"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              🇵🇭 PHP (₱)
            </button>
            <button
              type="button"
              onClick={() => setCurrency("USD")}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                currency === "USD"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              🌎 USD ($)
            </button>
          </div>
        </div>

        {/* Content depending on Mode */}
        {mode === "custom" ? (
          <div className="pt-2">
            <CustomTopupCard
              compact={true}
              currency={currency}
              onCheckout={handleCheckout}
              loading={loadingPkg === "custom"}
            />
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => setMode("presets")}
                className="text-xs text-neutral-400 hover:text-blue-400 underline transition-colors"
              >
                ← Back to standard refill packs
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Top-up Cards Grid */}
            {fetching ? (
              <div className="flex justify-center items-center py-16 text-neutral-500 text-sm">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-2" />
                Loading refill packs...
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-3">
                {topups.map((pkg) => {
                  const isPopular = pkg.popular;
                  return (
                    <div
                      key={pkg.id}
                      className={`relative flex flex-col justify-between rounded-xl p-4 transition-all duration-150 ${
                        isPopular
                          ? "bg-gradient-to-b from-[#1E293B]/60 to-[#0F172A]/40 border-2 border-blue-500/80 shadow-lg shadow-blue-500/10"
                          : "bg-[#141414] border border-[#262626] hover:border-[#383838]"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                          <span className="text-sm font-semibold text-white">{pkg.name}</span>
                          {pkg.badge && (
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                                isPopular
                                  ? "bg-blue-600 text-white"
                                  : "bg-[#222] text-neutral-300 border border-neutral-700"
                              }`}
                            >
                              {pkg.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-neutral-400 line-clamp-1 mb-3">
                          {pkg.description}
                        </p>

                        <div className="flex items-baseline justify-between mb-3 pb-3 border-b border-[#222]">
                          <div>
                            <span className="text-xl font-bold text-white tracking-tight">
                              {currSymbol}{pkg.amount}
                            </span>
                            <span className="text-[11px] text-neutral-500 ml-1">{currLabel}</span>
                          </div>
                          <div className="text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-medium">
                            {pkg.effective_price}
                          </div>
                        </div>
                      </div>

                      <Button
                        onClick={() => handleCheckout(pkg.id)}
                        disabled={loadingPkg !== null}
                        size="sm"
                        className={`w-full py-4 text-xs font-medium flex items-center justify-center gap-1.5 ${
                          isPopular
                            ? "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/30"
                            : "bg-[#202020] hover:bg-[#282828] text-neutral-200 border border-[#333]"
                        }`}
                      >
                        {loadingPkg === pkg.id ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Redirecting...
                          </>
                        ) : (
                          <>
                            <span>Add {pkg.credits} Credits</span>
                            <ArrowRight className="w-3.5 h-3.5" />
                          </>
                        )}
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Switch to custom shortcut banner */}
            <div className="mt-3 p-3 rounded-xl bg-[#141414] border border-[#222] flex items-center justify-between">
              <div className="text-xs text-neutral-300">
                <span className="font-semibold text-white">Need a specific number of applications?</span>
                <span className="text-neutral-500 block text-[11px]">Customize from 5 to 500 applications</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setMode("custom")}
                className="text-xs border-blue-500/40 text-blue-400 hover:bg-blue-500/10"
              >
                <Sliders className="w-3.5 h-3.5 mr-1" />
                Customize
              </Button>
            </div>
          </>
        )}

        {/* Footer info */}
        <div className="mt-4 pt-3 border-t border-[#222] flex items-center justify-between text-[11px] text-neutral-500">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>PayMongo encrypted checkout (GCash, Maya, Cards)</span>
          </div>
          <span className="text-neutral-500">1 credit = 1 application run</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
