import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { AUTHZ } from "@/constants/testIds";
import { Sparkles } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await login(email, password);
      nav("/");
    } catch (e) {
      setErr(e?.response?.data?.detail || "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-5 bg-[#0A0A0A]">
      <div className="lg:col-span-3 hidden lg:block relative border-r border-[#262626]">
        <img
          src="https://images.pexels.com/photos/30986854/pexels-photo-30986854.jpeg"
          alt="Dark workspace"
          className="absolute inset-0 w-full h-full object-cover opacity-30"
        />
        <div className="absolute inset-0 bg-[#0A0A0A]/60" />
        <div className="relative h-full p-12 flex flex-col justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-[#2563EB] flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" strokeWidth={2} />
            </div>
            <div className="font-display text-xl font-medium text-white">Recraftr</div>
          </div>
          <div className="max-w-md">
            <div className="label-caps mb-4 text-neutral-400">Built for candidates who want to win</div>
            <h2 className="font-display text-4xl font-medium leading-tight text-white tracking-tighter">
              A rewritten resume, tailored to the exact job — in under a minute.
            </h2>
            <p className="text-neutral-400 mt-6 leading-relaxed">
              Real ATS scoring, honest gap analysis, and a rewrite that stays true to your experience. No keyword stuffing. No fluff.
            </p>
          </div>
          <div className="text-xs text-neutral-600">© {new Date().getFullYear()} Recraftr</div>
        </div>
      </div>

      <div className="lg:col-span-2 flex items-center justify-center p-8 lg:p-16">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="label-caps mb-3">Sign in</div>
          <h1 className="font-display text-3xl font-medium text-[#F5F5F5] tracking-tighter mb-8">
            Welcome back.
          </h1>

          <div className="space-y-5">
            <div>
              <Label className="text-xs text-neutral-400 mb-2 block">Email</Label>
              <Input
                data-testid={AUTHZ.loginEmail}
                type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="bg-[#0A0A0A] border-[#262626] focus-visible:border-[#2563EB] focus-visible:ring-0 h-11"
              />
            </div>
            <div>
              <Label className="text-xs text-neutral-400 mb-2 block">Password</Label>
              <Input
                data-testid={AUTHZ.loginPassword}
                type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                className="bg-[#0A0A0A] border-[#262626] focus-visible:border-[#2563EB] focus-visible:ring-0 h-11"
              />
            </div>
            {err && (
              <div data-testid={AUTHZ.authError} className="text-sm text-[#F87171] bg-[#2A0B0B] border border-[#DC2626]/40 rounded-md px-3 py-2">
                {err}
              </div>
            )}
            <Button
              data-testid={AUTHZ.loginSubmit}
              type="submit" disabled={busy}
              className="w-full bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-11 rounded-full"
            >
              {busy ? "Signing in..." : "Sign in"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setEmail("test@resumematch.ai");
                setPassword("testpass123");
              }}
              className="w-full border-[#262626] bg-[#141414] hover:bg-[#1F1F1F] text-neutral-300 hover:text-white h-10 rounded-full text-xs font-normal"
            >
              ⚡ Quick Fill Demo Account
            </Button>
          </div>

          <div className="mt-8 text-sm text-neutral-500">
            No account?{" "}
            <Link data-testid={AUTHZ.loginSwitch} to="/signup" className="text-[#93C5FD] hover:text-white">
              Create one
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
