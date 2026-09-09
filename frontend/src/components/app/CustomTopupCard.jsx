import React, { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Sparkles, Sliders, Plus, Minus, ArrowRight, Loader2, Info } from "lucide-react";
import axios from "axios";
import { API } from "@/context/AuthContext";
import { calculateCustomTopup } from "@/lib/pricing";

export default function CustomTopupCard({
  currency = "PHP",
  onCheckout,
  loading = false,
  compact = false,
}) {
  const [credits, setCredits] = useState(15);
  const [serverQuote, setServerQuote] = useState(null);
  const [isQuoting, setIsQuoting] = useState(false);

  const currSymbol = currency === "USD" ? "$" : "₱";
  const currLabel = currency === "USD" ? "USD" : "PHP";

  // Instant local estimate for zero UI lag
  const localQuote = useMemo(() => {
    return calculateCustomTopup(credits, currency);
  }, [credits, currency]);

  // Sync with authoritative backend API
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      try {
        setIsQuoting(true);
        const res = await axios.get(
          `${API}/payments/custom-quote?credits=${credits}&currency=${currency}`
        );
        if (active && res.data) {
          setServerQuote(res.data);
        }
      } catch (err) {
        // Fall back gracefully to client calculation
      } finally {
        if (active) setIsQuoting(false);
      }
    }, 200);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [credits, currency]);

  const activeQuote = serverQuote && serverQuote.credits === credits ? serverQuote : localQuote;

  const handleSliderChange = (e) => {
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val)) {
      setCredits(Math.max(5, Math.min(500, val)));
    }
  };

  const handleInputChange = (e) => {
    const val = parseInt(e.target.value, 10);
    if (isNaN(val)) {
      setCredits(5);
    } else {
      setCredits(Math.max(5, Math.min(500, val)));
    }
  };

  const increment = (step = 1) => {
    setCredits((prev) => Math.min(500, prev + step));
  };

  const decrement = (step = 1) => {
    setCredits((prev) => Math.max(5, prev - step));
  };

  const setPreset = (amount) => {
    setCredits(amount);
  };

  return (
    <div
      className={`relative rounded-2xl bg-gradient-to-b from-[#161B26] to-[#0E131F] border-2 border-blue-500/70 p-5 sm:p-6 shadow-xl shadow-blue-500/10 text-white ${
        compact ? "my-2" : "my-6"
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-300 text-xs font-medium mb-1.5">
            <Sliders className="w-3.5 h-3.5" />
            <span>Interactive Custom Calculator</span>
          </div>
          <h3 className="text-lg font-bold text-white tracking-tight">
            Choose Exact Applications Needed
          </h3>
          <p className="text-xs text-neutral-400 mt-0.5">
            Refill anywhere between 5 to 500 applications. Pay only for what you need right now.
          </p>
        </div>

        {/* Quick Rate Badge */}
        <div className="flex flex-col sm:items-end">
          <span className="text-[11px] text-neutral-400">Convenience Rate</span>
          <span className="text-sm font-semibold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md border border-emerald-500/20">
            {activeQuote.effective_price}
          </span>
        </div>
      </div>

      {/* Stepper + Input */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center bg-[#0B0F19] border border-[#222E46] rounded-xl p-4 mb-4">
        <div className="md:col-span-7 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-neutral-300">
              Applications to Refill:
            </label>
            <span className="text-xs text-blue-400 font-mono font-medium">
              {credits} {credits === 1 ? "application" : "applications"}
            </span>
          </div>

          {/* Slider */}
          <div className="relative py-1">
            <input
              type="range"
              min="5"
              max="100"
              step="1"
              value={Math.min(credits, 100)}
              onChange={handleSliderChange}
              className="w-full h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-blue-500 focus:outline-none"
            />
            <div className="flex justify-between text-[10px] text-neutral-500 mt-1 font-mono">
              <span>5 apps</span>
              <span>25 apps</span>
              <span>50 apps</span>
              <span>100 apps</span>
            </div>
          </div>

          {/* Quick preset chips */}
          <div className="flex items-center gap-2 pt-1 flex-wrap">
            <span className="text-[11px] text-neutral-400 mr-1">Quick Select:</span>
            {[5, 10, 15, 25, 50, 75, 100].map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setPreset(preset)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                  credits === preset
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-[#161D2E] text-neutral-300 hover:bg-[#1E283F] border border-[#263554]"
                }`}
              >
                {preset}
              </button>
            ))}
          </div>
        </div>

        {/* Counter controls + Price summary */}
        <div className="md:col-span-5 flex flex-col justify-between border-t md:border-t-0 md:border-l border-[#222E46] pt-4 md:pt-0 md:pl-5">
          <div className="flex items-center justify-center gap-3 mb-3">
            <button
              type="button"
              onClick={() => decrement(credits > 20 ? 5 : 1)}
              disabled={credits <= 5}
              className="w-9 h-9 rounded-lg bg-[#161D2E] border border-[#263554] flex items-center justify-center text-white hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <Minus className="w-4 h-4" />
            </button>
            <div className="relative">
              <input
                type="number"
                min="5"
                max="500"
                value={credits}
                onChange={handleInputChange}
                className="w-24 text-center py-1.5 text-xl font-bold bg-[#0D121F] border border-blue-500/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 font-mono"
              />
            </div>
            <button
              type="button"
              onClick={() => increment(credits >= 20 ? 5 : 1)}
              disabled={credits >= 500}
              className="w-9 h-9 rounded-lg bg-[#161D2E] border border-[#263554] flex items-center justify-center text-white hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>

          <div className="text-center">
            <div className="text-[11px] text-neutral-400">Total Calculated Price</div>
            <div className="flex items-baseline justify-center gap-1 my-0.5">
              <span className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                {currSymbol}{activeQuote.amount.toFixed(2)}
              </span>
              <span className="text-xs text-neutral-400 font-medium">{currLabel}</span>
              {isQuoting && <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400 ml-1 inline" />}
            </div>
            <div className="text-[11px] text-neutral-400">
              ({credits} credits • {activeQuote.effective_price})
            </div>
          </div>
        </div>
      </div>

      {/* Convenience rate transparent notice */}
      <div className="flex items-start gap-2 text-[11px] text-neutral-400 bg-blue-950/20 border border-blue-900/30 rounded-lg p-2.5 mb-4">
        <Info className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
        <div>
          <span>Top-ups provide on-demand flexibility. Select a preset refill pack above or use the interactive slider to refill your exact target number of credits.</span>
        </div>
      </div>

      {/* CTA Button */}
      <Button
        onClick={() => onCheckout("custom", credits)}
        disabled={loading}
        className="w-full py-5 text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-xl shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2 transition-all"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Redirecting to PayMongo...</span>
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            <span>
              Top Up {credits} Applications for {currSymbol}{activeQuote.amount.toFixed(2)} {currLabel}
            </span>
            <ArrowRight className="w-4 h-4 ml-1" />
          </>
        )}
      </Button>
    </div>
  );
}
