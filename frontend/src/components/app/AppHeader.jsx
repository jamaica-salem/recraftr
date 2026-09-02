import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { History as HistoryIcon, LogOut, Layers, Sparkles } from "lucide-react";
import { RESUME } from "@/constants/testIds";

export default function AppHeader() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();

  return (
    <header
      data-testid={RESUME.header}
      className="sticky top-0 z-40 bg-[#0A0A0A] border-b border-[#262626]"
    >
      <div className="max-w-[1400px] mx-auto flex items-center justify-between px-6 lg:px-12 py-4">
        <Link
          to="/"
          data-testid={RESUME.headerBrand}
          className="flex items-center gap-3 group"
        >
          <div className="w-8 h-8 rounded-md bg-[#2563EB] flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" strokeWidth={2} />
          </div>
          <div className="leading-tight">
            <div className="font-display text-lg font-medium text-[#F5F5F5]">Recraftr</div>
            <div className="text-[11px] text-neutral-500 tracking-wide">Optimize your resume for any job in seconds</div>
          </div>
        </Link>

        <div className="flex items-center gap-1">
          <Button
            data-testid={RESUME.headerCompare}
            variant="ghost"
            className={`hover:bg-[#1F1F1F] ${loc.pathname === "/compare" ? "text-white bg-[#1F1F1F]" : "text-neutral-300 hover:text-white"}`}
            onClick={() => nav("/compare")}
          >
            <Layers className="w-4 h-4 mr-2" />
            Compare
          </Button>
          <Button
            data-testid={RESUME.headerHistory}
            variant="ghost"
            className={`hover:bg-[#1F1F1F] ${loc.pathname === "/history" ? "text-white bg-[#1F1F1F]" : "text-neutral-300 hover:text-white"}`}
            onClick={() => nav("/history")}
          >
            <HistoryIcon className="w-4 h-4 mr-2" />
            History
          </Button>

          <div className="hidden md:flex items-center gap-2 pl-3 ml-1 border-l border-[#262626]">
            <div className="w-7 h-7 rounded-full bg-[#1F1F1F] border border-[#262626] flex items-center justify-center text-xs font-medium text-neutral-300">
              {(user?.name || "?").slice(0, 1).toUpperCase()}
            </div>
            <span className="text-sm text-neutral-300 max-w-[160px] truncate">{user?.name}</span>
          </div>
          <Button
            data-testid={RESUME.headerLogout}
            variant="ghost"
            size="icon"
            className="text-neutral-400 hover:text-white hover:bg-[#1F1F1F]"
            onClick={logout}
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
