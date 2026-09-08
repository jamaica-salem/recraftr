import React, { useEffect, useState } from "react";
import AppHeader from "@/components/app/AppHeader";
import { Button } from "@/components/ui/button";
import { CheckCircle, Sparkles, ArrowRight, Loader2 } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { API, useAuth } from "@/context/AuthContext";
import axios from "axios";
import { toast } from "sonner";

export default function CheckoutSuccess() {
  const location = useLocation();
  const nav = useNavigate();
  const { authHeaders, refreshProfile, user } = useAuth();
  const [processing, setProcessing] = useState(true);
  const [confirmedCredits, setConfirmedCredits] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sessionId = params.get("session_id");
    const isMock = params.get("mock") === "true";
    const packageId = params.get("pkg") || "pro";

    async function fulfillPayment() {
      try {
        if (isMock) {
          // Local development / mock simulation mode
          const res = await axios.post(
            `${API}/payments/mock-complete`,
            { session_id: sessionId, package_id: packageId },
            { headers: authHeaders }
          );
          if (res.data?.credits_granted) {
            setConfirmedCredits(res.data.credits_granted);
          }
        }
        // Refresh authenticated profile in context so navbar credits update immediately
        if (refreshProfile) {
          await refreshProfile();
        }
        toast.success("Payment completed! Your AI credits have been added.");
      } catch (err) {
        console.error("Error confirming payment fulfillment:", err);
      } finally {
        setProcessing(false);
      }
    }

    fulfillPayment();
  }, [location, authHeaders, refreshProfile]);

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-[#F5F5F5]">
      <AppHeader />

      <main className="max-w-xl mx-auto px-6 py-20">
        <div className="bg-[#121212] border border-[#262626] rounded-2xl p-8 text-center shadow-2xl relative overflow-hidden">
          {/* Subtle background glow */}
          <div className="absolute -top-24 -left-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center mb-6">
            <CheckCircle className="w-8 h-8" />
          </div>

          <h1 className="text-2xl sm:text-3xl font-semibold text-white mb-2">
            Payment Confirmed!
          </h1>
          <p className="text-neutral-400 text-sm mb-8">
            Thank you for your purchase. Your account has been credited and is ready to optimize resumes.
          </p>

          {processing ? (
            <div className="flex items-center justify-center gap-2 py-6 text-neutral-400 text-sm">
              <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
              Verifying and updating credit balance...
            </div>
          ) : (
            <div className="bg-[#171717] border border-[#262626] rounded-xl p-5 mb-8 text-left space-y-3">
              <div className="flex items-center justify-between text-xs text-neutral-400">
                <span>Payment Status</span>
                <span className="text-emerald-400 font-medium uppercase tracking-wider">Paid / Verified</span>
              </div>
              <div className="flex items-center justify-between text-xs text-neutral-400">
                <span>Credits Added</span>
                <span className="text-white font-semibold flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                  +{confirmedCredits || "Granted"} Credits
                </span>
              </div>
              <div className="flex items-center justify-between text-xs text-neutral-400 pt-2 border-t border-[#262626]">
                <span>Total Available Balance</span>
                <span className="text-blue-400 font-bold text-sm">
                  {user?.credits !== undefined ? `${user.credits} Credits` : "Updated"}
                </span>
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              onClick={() => nav("/")}
              className="bg-blue-600 hover:bg-blue-500 text-white font-medium flex items-center justify-center gap-2 py-5"
            >
              Start Optimizing
              <ArrowRight className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              onClick={() => nav("/pricing")}
              className="border-[#262626] bg-[#171717] hover:bg-[#222] text-neutral-300 py-5"
            >
              View Packages
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
