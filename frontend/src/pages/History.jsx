import React, { useEffect, useState } from "react";
import AppHeader from "@/components/app/AppHeader";
import { API, useAuth } from "@/context/AuthContext";
import axios from "axios";
import { RESUME } from "@/constants/testIds";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Trash2, FileText, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

function scoreCls(s) {
  if ((s ?? 0) >= 80) return "text-[#4ADE80] border-[#16A34A]/40 bg-[#0B2818]";
  if ((s ?? 0) >= 60) return "text-[#FBBF24] border-[#D97706]/40 bg-[#2A1B05]";
  return "text-[#F87171] border-[#DC2626]/40 bg-[#2A0B0B]";
}

export default function History() {
  const { authHeaders } = useAuth();
  const nav = useNavigate();
  const [items, setItems] = useState(null);

  const load = async () => {
    try {
      const res = await axios.get(`${API}/history`, { headers: authHeaders });
      setItems(res.data.items || []);
    } catch (e) {
      toast.error("Failed to load history");
      setItems([]);
    }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  const open = async (id) => {
    try {
      const res = await axios.get(`${API}/history/${id}`, { headers: authHeaders });
      nav("/", { state: { loadedAnalysis: res.data } });
    } catch { toast.error("Could not open analysis"); }
  };

  const remove = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this analysis?")) return;
    try {
      await axios.delete(`${API}/history/${id}`, { headers: authHeaders });
      setItems(items.filter((it) => it.id !== id));
      toast.success("Deleted");
    } catch { toast.error("Delete failed"); }
  };

  return (
    <>
      <AppHeader />
      <main className="max-w-[1200px] mx-auto px-6 lg:px-12 py-12">
        <div className="mb-10">
          <div className="label-caps mb-3">History</div>
          <h1 className="font-display text-4xl sm:text-5xl font-medium tracking-tighter text-[#F5F5F5]">
            Your past analyses
          </h1>
          <p className="text-neutral-400 mt-3 max-w-xl">
            Every analysis and optimization you&apos;ve run is saved here. Open any to review or continue.
          </p>
        </div>

        {items === null ? (
          <div className="text-neutral-500">Loading...</div>
        ) : items.length === 0 ? (
          <div className="card-solid p-12 text-center">
            <FileText className="w-8 h-8 text-neutral-600 mx-auto mb-4" strokeWidth={1.5} />
            <div className="font-display text-xl text-[#F5F5F5] mb-2">No analyses yet</div>
            <div className="text-sm text-neutral-500 mb-6">Run your first resume analysis to see it here.</div>
            <Button onClick={() => nav("/")} className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full">
              Start analyzing
            </Button>
          </div>
        ) : (
          <div data-testid={RESUME.historyList} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {items.map((it) => (
              <button
                key={it.id}
                data-testid={RESUME.historyItem}
                onClick={() => open(it.id)}
                className="card-solid p-6 text-left hover:bg-[#1A1A1A] transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="label-caps mb-2">{new Date(it.created_at).toLocaleString()}</div>
                    <div className="font-display text-lg text-[#F5F5F5] truncate">{it.job_title || "Untitled role"}</div>
                    <div className="text-xs text-neutral-500 truncate mt-1">{it.resume_filename}</div>
                  </div>
                  <div className={`text-xs px-2 py-1 rounded-md border ${scoreCls(it.ats_score)}`}>
                    ATS {it.ats_score ?? "—"}
                  </div>
                </div>
                <div className="flex items-center justify-between mt-4">
                  <div className="flex items-center gap-2 text-xs text-neutral-500">
                    {it.optimized ? (
                      <span className="inline-flex items-center gap-1 text-[#93C5FD]"><Sparkles className="w-3 h-3" /> Optimized</span>
                    ) : (
                      <span>Analyzed</span>
                    )}
                  </div>
                  <Button
                    variant="ghost" size="icon"
                    className="text-neutral-500 hover:text-[#F87171] hover:bg-[#2A0B0B]"
                    onClick={(e) => remove(it.id, e)}
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
