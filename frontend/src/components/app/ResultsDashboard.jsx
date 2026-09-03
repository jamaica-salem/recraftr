import React, { useMemo, useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RESUME } from "@/constants/testIds";
import { API, useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Copy, Download, Sparkles, CheckCircle2, Circle, AlertCircle, Mail, Code, Sparkle, Kanban, BookmarkPlus, BarChart2, Zap } from "lucide-react";
import ExportModal from "@/components/ExportModal";
import InteractiveBulletEditor from "@/components/app/InteractiveBulletEditor";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

function scoreColor(score) {
  if (score >= 80) return { hex: "#16A34A", label: "Strong", ring: "text-[#22C55E]" };
  if (score >= 60) return { hex: "#D97706", label: "Fair", ring: "text-[#F59E0B]" };
  return { hex: "#DC2626", label: "Weak", ring: "text-[#EF4444]" };
}

function ScoreRing({ value }) {
  const c = scoreColor(value || 0);
  const size = 168;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (Math.max(0, Math.min(100, value || 0)) / 100) * circ;
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#1F1F1F" strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={c.hex} strokeWidth={stroke} fill="none"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 800ms ease-out" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div data-testid={RESUME.atsScore} className="font-display text-5xl font-medium text-[#F5F5F5]">{value ?? 0}</div>
        <div data-testid={RESUME.atsStatus} className={`text-xs mt-1 label-caps ${c.ring}`}>{c.label}</div>
      </div>
    </div>
  );
}

function BreakdownCard({ label, value, testId }) {
  const c = scoreColor(value);
  return (
    <div data-testid={testId} className="card-solid p-5">
      <div className="label-caps mb-3">{label}</div>
      <div className="flex items-end justify-between">
        <div className="font-display text-3xl text-[#F5F5F5]">{value ?? 0}</div>
        <div className="text-xs text-neutral-500">/ 100</div>
      </div>
      <div className="mt-3 h-1.5 bg-[#1F1F1F] rounded-full overflow-hidden">
        <div style={{ width: `${value || 0}%`, background: c.hex, transition: "width 700ms ease-out" }} className="h-full" />
      </div>
    </div>
  );
}

function MatchBadge({ match }) {
  const cfg = {
    Exact: { icon: CheckCircle2, cls: "bg-[#0B2818] text-[#4ADE80] border-[#16A34A]/40" },
    Semantic: { icon: CheckCircle2, cls: "bg-[#0F1B2E] text-[#60A5FA] border-[#2563EB]/40" },
    Partial: { icon: AlertCircle, cls: "bg-[#2A1B05] text-[#FBBF24] border-[#D97706]/40" },
    Missing: { icon: Circle, cls: "bg-[#2A0B0B] text-[#F87171] border-[#DC2626]/40" },
  };
  const c = cfg[match] || cfg.Missing;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border font-medium ${c.cls}`}>
      <Icon className="w-3.5 h-3.5" strokeWidth={2} />{match}
    </span>
  );
}

function SimpleDiff({ before, after }) {
  const { left, right } = useMemo(() => {
    const a = (before || "").split("\n");
    const b = (after || "").split("\n");
    const setA = new Set(a.map((s) => s.trim()));
    const setB = new Set(b.map((s) => s.trim()));
    return {
      left: a.map((line) => ({ text: line, tag: setB.has(line.trim()) ? "eq" : "del" })),
      right: b.map((line) => ({ text: line, tag: setA.has(line.trim()) ? "eq" : "add" })),
    };
  }, [before, after]);

  return (
    <div data-testid={RESUME.diffView} className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="card-solid p-4">
        <div className="label-caps mb-3">Before</div>
        <pre className="text-xs font-mono whitespace-pre-wrap leading-relaxed">
          {left.map((r, i) => (
            <div key={i} className={r.tag === "del" ? "diff-del" : "diff-eq"}>{r.text || "\u00A0"}</div>
          ))}
        </pre>
      </div>
      <div className="card-solid p-4">
        <div className="label-caps mb-3">After</div>
        <pre className="text-xs font-mono whitespace-pre-wrap leading-relaxed">
          {right.map((r, i) => (
            <div key={i} className={r.tag === "add" ? "diff-add" : "diff-eq"}>{r.text || "\u00A0"}</div>
          ))}
        </pre>
      </div>
    </div>
  );
}



export default function ResultsDashboard({
  analysis, optimization, originalResumeText, coverLetter, jobTitle, jobDesc,
  onOptimize, onAutoOptimize, onGenerateCoverLetter, onReEvaluateATS,
  optimizing, autoOptimizing, coverLoading, reEvaluating,
}) {
  const { token, user } = useAuth();
  const [tab, setTab] = useState("overview");
  const [exportModal, setExportModal] = useState({ open: false, type: "resume" });
  const [editorMode, setEditorMode] = useState("interactive");
  const [currentResumeText, setCurrentResumeText] = useState("");

  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveForm, setSaveForm] = useState({
    company_name: "",
    job_title: "",
    status: "applied",
  });
  const [savingToTracker, setSavingToTracker] = useState(false);

  React.useEffect(() => {
    if (optimization?.optimized_resume) {
      setCurrentResumeText(optimization.optimized_resume);
      setTab("optimized");
    }
  }, [optimization?.optimized_resume]);

  const activeResumeText = currentResumeText || optimization?.optimized_resume || "";

  const missing = analysis?.missing_skills || {};
  const gap = analysis?.gap_analysis || [];
  const improvements = analysis?.improvements || [];
  const breakdown = analysis?.breakdown || {};

  const copyText = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text || "");
      toast.success(`${label} copied`);
    } catch { toast.error("Copy failed"); }
  };

  const openSaveModal = () => {
    const initialTitle = jobTitle || analysis?.job_title || "Target Role";
    setSaveForm({
      company_name: "",
      job_title: initialTitle,
      status: "applied",
    });
    setSaveModalOpen(true);
  };

  const submitSaveToTracker = async (e) => {
    if (e) e.preventDefault();
    if (!saveForm.company_name.trim()) {
      toast.error("Please enter a company name");
      return;
    }
    if (!saveForm.job_title.trim()) {
      toast.error("Please enter a job title");
      return;
    }
    try {
      setSavingToTracker(true);
      const targetJobTitle = saveForm.job_title.trim();
      const targetCompany = saveForm.company_name.trim();
      const targetJobDesc = analysis?.job_description || jobDesc || "";
      const payload = {
        job_title: targetJobTitle,
        company_name: targetCompany,
        status: saveForm.status || "applied",
        ats_score: optimization?.predicted_ats_score || analysis?.ats_score || 0,
        job_description: targetJobDesc,
        optimized_resume: activeResumeText,
        cover_letter: coverLetter || "",
      };
      const res = await fetch(`${API}/applications`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to save application");
      toast.success(`Saved application for ${targetCompany} to Job Tracker!`);
      setSaveModalOpen(false);
    } catch (err) {
      toast.error(err?.message || "Could not save to tracker");
    } finally {
      setSavingToTracker(false);
    }
  };

  const downloadResumePdf = () => {
    if (!optimization?.optimized_resume) return;
    setExportModal({ open: true, type: "resume" });
  };

  const downloadCoverPdf = () => {
    if (!coverLetter) return;
    setExportModal({ open: true, type: "cover_letter" });
  };

  return (
    <div className="mt-10 rm-fade-up">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-transparent p-0 h-auto border-b border-[#262626] w-full justify-start rounded-none gap-1 overflow-x-auto">
          {[
            ["overview", "Overview", RESUME.tabOverview],
            ["gap", "Gap Analysis", RESUME.tabGap],
            ["missing", "Missing Skills", RESUME.tabMissing],
            ["improvements", "Improvements", RESUME.tabImprovements],
            ["optimized", "Optimized Resume", RESUME.tabOptimized],
            ["cover", "Cover Letter", RESUME.tabCoverLetter],
            ["diff", "Before vs After", RESUME.tabDiff],
          ].map(([v, label, tid]) => (
            <TabsTrigger
              key={v} value={v} data-testid={tid}
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#2563EB] data-[state=active]:bg-transparent data-[state=active]:text-white text-neutral-500 hover:text-neutral-200 px-4 py-3 transition-colors"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-8 space-y-6">
          <div className="card-solid p-8 flex flex-col md:flex-row gap-8 items-start">
            <ScoreRing value={analysis?.ats_score} />
            <div className="flex-1 w-full">
              <div className="flex items-center gap-3 mb-2">
                <div className="label-caps">ATS Match Score</div>
                {analysis?.score_category && (
                  <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${analysis.score_category === "Strong" ? "bg-[#0B2818] text-[#4ADE80] border-[#16A34A]/40"
                    : analysis.score_category === "Moderate" ? "bg-[#2A1B05] text-[#FBBF24] border-[#D97706]/40"
                      : "bg-[#2A0B0B] text-[#F87171] border-[#DC2626]/40"
                    }`}>
                    {analysis.score_category} Match
                  </span>
                )}
              </div>
              <div className="font-display text-2xl text-[#F5F5F5] mb-1">
                {(analysis?.ats_score ?? 0) >= 85 ? "Strong alignment with the role."
                  : (analysis?.ats_score ?? 0) >= 60 ? "Moderate match — targeted optimization will lift this to 90+."
                    : "Weak match — optimization will make the biggest difference here."}
              </div>
              <p className="text-sm text-neutral-400 max-w-xl">
                Evaluated with weighted scoring rules (required must-haves = weight 3, preferred = weight 1, standard = weight 2).
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
                <BreakdownCard label="Keyword Match" value={breakdown.keyword_match} testId={RESUME.breakdownKeyword} />
                <BreakdownCard label="Skills Match" value={breakdown.skills_match} testId={RESUME.breakdownSkills} />
                <BreakdownCard label="Experience" value={breakdown.experience_match} testId={RESUME.breakdownExperience} />
              </div>

              <div className="mt-8 p-5 border border-[#262626] rounded-lg bg-[#0F0F0F] flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <div className="label-caps mb-1">Next step</div>
                  <div className="text-[#F5F5F5] font-medium">Iterative AI Optimization targeting 90+ ATS score</div>
                  <div className="text-xs text-neutral-500 mt-1">Multi-pass keyword injection and bullet refinement strictly preserving resume facts.</div>
                </div>
                <div className="flex gap-2.5 flex-wrap">
                  <Button onClick={onOptimize} disabled={optimizing || autoOptimizing}
                    className="bg-[#2563EB] text-white hover:bg-[#1D4ED8] rounded-lg text-xs font-medium px-4 h-9 cursor-pointer">
                    <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                    {optimizing ? "Optimizing..." : "Standard Rewrite"}
                  </Button>
                  <Button onClick={onAutoOptimize} disabled={optimizing || autoOptimizing}
                    className="bg-[#1E293B] hover:bg-[#334155] border border-[#334155] text-blue-300 hover:text-white rounded-lg text-xs font-medium px-4 h-9 cursor-pointer flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-blue-400" />
                    <span>{autoOptimizing ? "Boosting to 90+..." : "Boost to 90+ ATS"}</span>
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Top ATS Keywords to Add & Interview Talking Points */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {analysis?.ats_keywords_to_add && analysis.ats_keywords_to_add.length > 0 && (
              <div className="card-solid p-6">
                <div className="label-caps mb-3 text-amber-400">Top ATS Keywords to Add (Top 20)</div>
                <div className="flex flex-wrap gap-1.5">
                  {analysis.ats_keywords_to_add.map((kw, i) => (
                    <Badge key={i} className="bg-[#1F190B] text-amber-300 border border-amber-500/30 text-xs px-2.5 py-1 font-normal">
                      {kw}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {analysis?.interview_talking_points && analysis.interview_talking_points.length > 0 && (
              <div className="card-solid p-6">
                <div className="label-caps mb-3 text-blue-400">Interview Preparation Talking Points</div>
                <ul className="space-y-2 text-xs text-neutral-300">
                  {analysis.interview_talking_points.map((tp, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-blue-400 font-bold">•</span>
                      <span>{tp}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </TabsContent>

        {/* Gap Analysis */}
        <TabsContent value="gap" className="mt-8">
          <div data-testid={RESUME.gapTable} className="card-solid overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left label-caps border-b border-[#262626] bg-[#0A0A0A]">
                  <th className="px-6 py-4 font-semibold w-1/3">Requirement</th>
                  <th className="px-6 py-4 font-semibold">Match & Weight</th>
                  <th className="px-6 py-4 font-semibold">Resume Evidence & Reasoning</th>
                </tr>
              </thead>
              <tbody>
                {gap.length === 0 && (
                  <tr><td className="px-6 py-6 text-neutral-500" colSpan={3}>No requirements returned.</td></tr>
                )}
                {gap.map((row, i) => (
                  <tr key={i} className="border-t border-[#1F1F1F] hover:bg-[#141414] transition-colors">
                    <td className="px-6 py-4 text-[#F5F5F5] font-medium">{row.requirement}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <MatchBadge match={row.match} />
                        {row.weight && (
                          <span className="text-[11px] text-neutral-400 bg-[#1A1A1A] px-2 py-0.5 rounded border border-[#333]">
                            Weight {row.weight}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-neutral-400">
                      <div className="text-sm text-neutral-300">{row.evidence}</div>
                      {row.reasoning && (
                        <div className="text-xs text-neutral-500 mt-1 italic">{row.reasoning}</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        {/* Missing */}
        <TabsContent value="missing" className="mt-8">
          <div data-testid={RESUME.missingList} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { key: "high", label: "High Priority Technical", items: missing.high || [], cls: "bg-[#2A0B0B] text-[#F87171] border-[#DC2626]/40" },
              { key: "medium", label: "Medium Priority Technical", items: missing.medium || [], cls: "bg-[#2A1B05] text-[#FBBF24] border-[#D97706]/40" },
              { key: "optional", label: "Optional / Plus", items: missing.optional || [], cls: "bg-[#0F1B2E] text-[#93C5FD] border-[#2563EB]/40" },
              { key: "soft_skills", label: "Missing Soft Skills", items: missing.soft_skills || [], cls: "bg-[#1E102A] text-[#C084FC] border-[#9333EA]/40" },
            ].map((g) => (
              <div key={g.key} className="card-solid p-6">
                <div className="label-caps mb-4">{g.label}</div>
                {g.items.length === 0 ? (
                  <div className="text-sm text-neutral-500">Nothing missing here.</div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {g.items.map((s, i) => (
                      <Badge key={i} className={`border ${g.cls} bg-transparent px-2.5 py-1 text-xs font-normal`}>{s}</Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </TabsContent>

        {/* Improvements */}
        <TabsContent value="improvements" className="mt-8">
          <div data-testid={RESUME.improvementsList} className="card-solid p-8">
            <div className="label-caps mb-4">AI-suggested improvements</div>
            {improvements.length === 0 ? (
              <div className="text-sm text-neutral-500">No suggestions returned.</div>
            ) : (
              <ol className="space-y-4">
                {improvements.map((imp, i) => (
                  <li key={i} className="flex gap-4 rm-fade-up" style={{ animationDelay: `${i * 40}ms` }}>
                    <div className="w-7 h-7 rounded-full bg-[#0F1B2E] border border-[#2563EB]/40 text-[#93C5FD] text-xs font-medium flex items-center justify-center flex-shrink-0">
                      {i + 1}
                    </div>
                    <div className="text-neutral-200 leading-relaxed">{imp}</div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </TabsContent>

        {/* Optimized */}
        <TabsContent value="optimized" className="mt-8">
          {!optimization ? (
            <div className="card-solid p-12 text-center">
              <div className="label-caps mb-3">Not generated yet</div>
              <div className="font-display text-xl text-[#F5F5F5] mb-2">Click Optimize or Boost to rewrite this resume</div>
              <div className="text-sm text-neutral-500 mb-6">The AI will inject relevant keywords, tighten bullets, and target 90+ ATS.</div>
              <div className="flex justify-center gap-3">
                <Button onClick={onOptimize} disabled={optimizing || autoOptimizing} className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full px-6">
                  <Sparkles className="w-4 h-4 mr-2" />
                  {optimizing ? "Optimizing..." : "Standard Optimize"}
                </Button>
                <Button onClick={onAutoOptimize} disabled={optimizing || autoOptimizing} className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white font-semibold rounded-full px-6 shadow-lg border border-amber-400/30">
                  <Zap className="w-4 h-4 mr-2 text-white fill-white" />
                  {autoOptimizing ? "Boosting to 90+..." : "Boost to 90+ ATS"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="card-solid p-6 md:p-8">
              <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
                <div>
                  <div className="label-caps mb-1 flex items-center gap-2">
                    <span>Optimized resume</span>
                    {optimization.auto_boosted && (
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px]">
                        ⚡ 90+ Auto-Boosted
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-sm text-neutral-400 flex-wrap">
                    <span>
                      Predicted ATS: <span className="text-[#4ADE80] font-medium">{optimization.predicted_ats_score ?? "—"}</span>
                    </span>
                    {optimization.actual_ats_score !== undefined && (
                      <>
                        <span className="text-neutral-600">•</span>
                        <span>
                          Evaluated Real ATS: <span className="text-[#4ADE80] font-bold text-base">{optimization.actual_ats_score}/100</span>
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 items-center flex-wrap">
                  <Button
                    type="button"
                    data-testid={RESUME.reEvaluateAtsBtn}
                    onClick={() => onReEvaluateATS && onReEvaluateATS(activeResumeText)}
                    disabled={optimizing || autoOptimizing || reEvaluating}
                    variant="outline"
                    className="bg-[#141414] border-[#262626] text-emerald-400 hover:bg-[#1A1A1A] hover:text-emerald-300 rounded-lg text-xs font-medium px-3.5 h-9 flex items-center gap-1.5 cursor-pointer shadow-none"
                  >
                    <BarChart2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{reEvaluating ? "Evaluating Real ATS..." : "Check Real ATS Score"}</span>
                  </Button>

                  <Button
                    onClick={onAutoOptimize}
                    disabled={optimizing || autoOptimizing || reEvaluating}
                    className="bg-[#1E293B] hover:bg-[#334155] border border-[#334155] text-blue-300 hover:text-white text-xs font-medium rounded-lg px-3.5 h-9 flex items-center gap-1.5 cursor-pointer shadow-none"
                  >
                    <Zap className="w-3.5 h-3.5 text-blue-400" />
                    <span>{autoOptimizing ? "Re-Boosting..." : "Re-Optimize to 90+"}</span>
                  </Button>

                  <div className="flex bg-[#0A0A0A] border border-[#262626] rounded-lg p-1 h-9 items-center">
                    <button
                      type="button"
                      onClick={() => setEditorMode("interactive")}
                      className={`h-7 px-3 text-xs rounded-md flex items-center gap-1.5 font-medium transition-all ${
                        editorMode === "interactive"
                          ? "bg-[#2563EB] text-white"
                          : "text-neutral-400 hover:text-white"
                      }`}
                    >
                      <Sparkles className="w-3.5 h-3.5 text-indigo-300" />
                      <span>Interactive AI Editor</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditorMode("raw")}
                      className={`h-7 px-3 text-xs rounded-md flex items-center gap-1.5 font-medium transition-all ${
                        editorMode === "raw"
                          ? "bg-[#2563EB] text-white"
                          : "text-neutral-400 hover:text-white"
                      }`}
                    >
                      <Code className="w-3.5 h-3.5" />
                      <span>Plain Text</span>
                    </button>
                  </div>

                  <Button
                    onClick={openSaveModal}
                    disabled={savingToTracker}
                    variant="outline"
                    className="bg-[#141414] border-[#262626] text-neutral-200 hover:bg-[#1F1F1F] hover:text-white text-xs font-medium rounded-lg px-3.5 h-9 flex items-center gap-1.5 cursor-pointer shadow-none"
                  >
                    <BookmarkPlus className="w-3.5 h-3.5 text-neutral-400" />
                    <span>Save to Tracker</span>
                  </Button>

                  <Button
                    data-testid={RESUME.copyResumeBtn}
                    variant="outline"
                    onClick={() => copyText(activeResumeText, "Optimized resume")}
                    className="bg-[#141414] border-[#262626] text-neutral-200 hover:bg-[#1F1F1F] hover:text-white text-xs font-medium rounded-lg px-3.5 h-9 flex items-center gap-1.5 cursor-pointer shadow-none"
                  >
                    <Copy className="w-3.5 h-3.5 text-neutral-400" />
                    <span>Copy</span>
                  </Button>

                  <Button
                    data-testid={RESUME.downloadPdfBtn}
                    onClick={downloadResumePdf}
                    className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-medium rounded-lg px-3.5 h-9 flex items-center gap-1.5 cursor-pointer shadow-none"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Export PDF/HTML</span>
                  </Button>
                </div>
              </div>

              {/* Editor Mode: Interactive vs Plain Text */}
              {editorMode === "interactive" ? (
                <InteractiveBulletEditor
                  initialResumeText={activeResumeText}
                  resumeText={activeResumeText}
                  jobDescription={analysis?.job_description || jobDesc || ""}
                  onChange={(newText) => setCurrentResumeText(newText)}
                  onUpdateResumeText={(newText) => setCurrentResumeText(newText)}
                />
              ) : (
                <pre className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-md p-6 font-mono text-xs text-neutral-200 whitespace-pre-wrap leading-relaxed max-h-[600px] overflow-y-auto">
                  {activeResumeText}
                </pre>
              )}
              {optimization.changes_summary?.length > 0 && (
                <div className="mt-6">
                  <div className="label-caps mb-3">Changes summary</div>
                  <ul className="space-y-2">
                    {optimization.changes_summary.map((c, i) => (
                      <li key={i} className="text-sm text-neutral-300 flex gap-2">
                        <span className="text-[#4ADE80]">›</span> {c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </TabsContent>

        {/* Cover Letter */}
        <TabsContent value="cover" className="mt-8">
          {!coverLetter ? (
            <div className="card-solid p-12 text-center">
              <div className="w-12 h-12 rounded-lg bg-[#0F1B2E] border border-[#2563EB]/40 flex items-center justify-center mx-auto mb-4">
                <Mail className="w-5 h-5 text-[#93C5FD]" strokeWidth={1.75} />
              </div>
              <div className="label-caps mb-3">Cover letter</div>
              <div className="font-display text-xl text-[#F5F5F5] mb-2">Generate a matching cover letter</div>
              <div className="text-sm text-neutral-500 mb-6 max-w-md mx-auto">
                Uses the same resume and job description to draft a specific, personalized letter — no cliches, no fake facts.
              </div>
              <Button data-testid={RESUME.coverLetterGenerate}
                onClick={onGenerateCoverLetter} disabled={coverLoading}
                className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full px-6">
                <Mail className="w-4 h-4 mr-2" />
                {coverLoading ? "Writing..." : "Generate cover letter"}
              </Button>
            </div>
          ) : (
            <div className="card-solid p-6 md:p-8">
              <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
                <div>
                  <div className="label-caps mb-1">Cover letter</div>
                  <div className="text-sm text-neutral-400">Tailored for <span className="text-white">{jobTitle || analysis?.job_title || "the role"}</span></div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={onGenerateCoverLetter} disabled={coverLoading}
                    className="bg-transparent border-[#262626] text-neutral-200 hover:bg-[#1F1F1F] hover:text-white rounded-full">
                    <Sparkles className="w-4 h-4 mr-2" /> Regenerate
                  </Button>
                  <Button data-testid={RESUME.coverLetterCopy} variant="outline"
                    onClick={() => copyText(coverLetter, "Cover letter")}
                    className="bg-transparent border-[#262626] text-neutral-200 hover:bg-[#1F1F1F] hover:text-white rounded-full">
                    <Copy className="w-4 h-4 mr-2" /> Copy
                  </Button>
                  <Button data-testid={RESUME.coverLetterDownload} onClick={downloadCoverPdf}
                    className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full">
                    <Download className="w-4 h-4 mr-2" /> Download PDF
                  </Button>
                </div>
              </div>
              <div
                data-testid={RESUME.coverLetterText}
                className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-md p-8 max-w-3xl"
              >
                {coverLetter.split(/\n\n+/).map((p, i) => (
                  <p key={i} className="text-neutral-200 leading-relaxed mb-4 last:mb-0">
                    {p.split("\n").map((line, j) => (
                      <React.Fragment key={j}>
                        {line}{j < p.split("\n").length - 1 && <br />}
                      </React.Fragment>
                    ))}
                  </p>
                ))}
              </div>
            </div>
          )}
        </TabsContent>

        {/* Diff */}
        <TabsContent value="diff" className="mt-8">
          {!originalResumeText || !optimization?.optimized_resume ? (
            <div className="card-solid p-12 text-center text-neutral-500">
              Optimize the resume first to see a before/after comparison.
            </div>
          ) : (
            <SimpleDiff before={originalResumeText} after={optimization.optimized_resume} />
          )}
        </TabsContent>
      </Tabs>

      {/* Export Modal */}
      <ExportModal
        open={exportModal.open}
        onClose={() => setExportModal({ open: false, type: "resume" })}
        title={exportModal.type === "cover_letter" ? "Export Cover Letter" : "Export Optimized Resume"}
        downloadType={exportModal.type}
        resumeText={activeResumeText}
        coverLetterText={coverLetter || ""}
        candidateName={user?.name || ""}
        jobTitle={jobTitle || analysis?.job_title || ""}
        filename={exportModal.type === "cover_letter" ? "cover-letter" : "resume-optimized"}
        token={token}
        backendUrl={API.replace(/\/api$/, "")}
      />

      {/* Save Package to Job Tracker Prompt Modal */}
      <Dialog open={saveModalOpen} onOpenChange={setSaveModalOpen}>
        <DialogContent className="sm:max-w-md bg-[#0F0F0F] border-[#262626] text-white rounded-xl shadow-2xl p-6">
          <DialogHeader className="pb-3 border-b border-[#262626]">
            <DialogTitle className="text-xl font-bold text-[#F5F5F5] flex items-center gap-2">
              <BookmarkPlus className="w-5 h-5 text-[#2563EB]" />
              Save Application to Job Tracker
            </DialogTitle>
            <DialogDescription className="text-neutral-400 text-xs mt-1">
              Specify the company name and confirm target details to save this optimized package to your job search pipeline.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={submitSaveToTracker} className="space-y-4 my-2">
            <div>
              <label className="block text-xs font-semibold label-caps text-neutral-300 mb-1.5">
                Company Name <span className="text-red-400">*</span>
              </label>
              <Input
                required
                autoFocus
                placeholder="e.g. Google, Stripe, OpenAI, Microsoft..."
                value={saveForm.company_name}
                onChange={(e) => setSaveForm((prev) => ({ ...prev, company_name: e.target.value }))}
                className="bg-[#1A1A1A] border-[#333333] text-white focus:border-[#2563EB] text-sm h-10"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold label-caps text-neutral-300 mb-1.5">
                Target Role / Job Title <span className="text-red-400">*</span>
              </label>
              <Input
                required
                placeholder="e.g. Senior Full Stack Engineer"
                value={saveForm.job_title}
                onChange={(e) => setSaveForm((prev) => ({ ...prev, job_title: e.target.value }))}
                className="bg-[#1A1A1A] border-[#333333] text-white focus:border-[#2563EB] text-sm h-10"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold label-caps text-neutral-300 mb-1.5">
                Pipeline Stage
              </label>
              <select
                value={saveForm.status}
                onChange={(e) => setSaveForm((prev) => ({ ...prev, status: e.target.value }))}
                className="w-full h-10 rounded-md border border-[#333333] bg-[#1A1A1A] px-3 py-1 text-sm text-white focus:outline-none focus:border-[#2563EB]"
              >
                <option value="applied">Applied</option>
                <option value="interviewing">Interviewing</option>
                <option value="offer">Offer Received</option>
                <option value="bookmarked">Bookmarked / Saved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>

            <div className="p-3 rounded-lg bg-[#141414] border border-[#262626] flex items-center justify-between text-xs">
              <span className="text-neutral-400">Match Score to Save:</span>
              <span className="font-bold text-[#4ADE80]">
                {optimization?.predicted_ats_score || analysis?.ats_score || 0}% ATS Match
              </span>
            </div>

            <DialogFooter className="mt-6 flex justify-end gap-2 pt-3 border-t border-[#262626]">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setSaveModalOpen(false)}
                className="text-neutral-400 hover:text-white"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={savingToTracker}
                className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-medium px-5 rounded-full"
              >
                {savingToTracker ? "Saving..." : "Save Application"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
