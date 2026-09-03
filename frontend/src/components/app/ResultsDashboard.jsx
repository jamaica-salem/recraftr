import React, { useMemo, useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RESUME } from "@/constants/testIds";
import { API, useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Copy, Download, Sparkles, CheckCircle2, Circle, AlertCircle, Mail, Code, Sparkle, Kanban, BookmarkPlus, BarChart2 } from "lucide-react";
import ExportModal from "@/components/ExportModal";
import InteractiveBulletEditor from "@/components/app/InteractiveBulletEditor";

function scoreColor(score) {
  if (score >= 80) return { hex: "#16A34A", label: "Strong", ring: "text-[#22C55E]" };
  if (score >= 60) return { hex: "#D97706", label: "Fair",   ring: "text-[#F59E0B]" };
  return                { hex: "#DC2626", label: "Weak",   ring: "text-[#EF4444]" };
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
    Exact:   { icon: CheckCircle2, cls: "bg-[#0B2818] text-[#4ADE80] border-[#16A34A]/40" },
    Partial: { icon: AlertCircle,  cls: "bg-[#2A1B05] text-[#FBBF24] border-[#D97706]/40" },
    Missing: { icon: Circle,       cls: "bg-[#2A0B0B] text-[#F87171] border-[#DC2626]/40" },
  };
  const c = cfg[match] || cfg.Missing;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border ${c.cls}`}>
      <Icon className="w-3 h-3" strokeWidth={2} />{match}
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
      left:  a.map((line) => ({ text: line, tag: setB.has(line.trim()) ? "eq" : "del" })),
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
  analysis, optimization, originalResumeText, coverLetter,
  onOptimize, onAutoOptimize, onGenerateCoverLetter, onReEvaluateATS,
  optimizing, autoOptimizing, coverLoading, reEvaluating,
}) {
  const { token, user } = useAuth();
  const [tab, setTab] = useState("overview");
  const [exportModal, setExportModal] = useState({ open: false, type: "resume" });
  const [editorMode, setEditorMode] = useState("interactive");
  const [currentResumeText, setCurrentResumeText] = useState("");

  React.useEffect(() => {
    if (optimization?.optimized_resume) {
      setCurrentResumeText(optimization.optimized_resume);
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

  const [savingToTracker, setSavingToTracker] = useState(false);

  const saveToTracker = async () => {
    try {
      setSavingToTracker(true);
      const payload = {
        job_title: analysis?.job_title || "Target Role",
        company_name: "Target Company",
        status: "applied",
        ats_score: analysis?.ats_score,
        job_description: analysis?.job_description || "",
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
      toast.success("Package saved to Job Tracker!");
    } catch {
      toast.error("Could not save to tracker");
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
            ["overview",     "Overview",         RESUME.tabOverview],
            ["gap",          "Gap Analysis",     RESUME.tabGap],
            ["missing",      "Missing Skills",   RESUME.tabMissing],
            ["improvements", "Improvements",     RESUME.tabImprovements],
            ["optimized",    "Optimized Resume", RESUME.tabOptimized],
            ["cover",        "Cover Letter",     RESUME.tabCoverLetter],
            ["diff",         "Before vs After",  RESUME.tabDiff],
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
        <TabsContent value="overview" className="mt-8">
          <div className="card-solid p-8 flex flex-col md:flex-row gap-8 items-start">
            <ScoreRing value={analysis?.ats_score} />
            <div className="flex-1 w-full">
              <div className="label-caps mb-2">ATS Match Score</div>
              <div className="font-display text-2xl text-[#F5F5F5] mb-1">
                {(analysis?.ats_score ?? 0) >= 80 ? "Strong alignment with the role."
                 : (analysis?.ats_score ?? 0) >= 60 ? "Decent match — a targeted rewrite will lift this significantly."
                 : "Low match — optimization will make the biggest difference here."}
              </div>
              <p className="text-sm text-neutral-400 max-w-xl">
                Based on keyword coverage, skill overlap, and experience relevance against the target job description.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
                <BreakdownCard label="Keyword Match" value={breakdown.keyword_match} testId={RESUME.breakdownKeyword} />
                <BreakdownCard label="Skills Match" value={breakdown.skills_match} testId={RESUME.breakdownSkills} />
                <BreakdownCard label="Experience"    value={breakdown.experience_match} testId={RESUME.breakdownExperience} />
              </div>

              <div className="mt-8 p-5 border border-[#262626] rounded-lg bg-[#0F0F0F] flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <div className="label-caps mb-1">Next step</div>
                  <div className="text-[#F5F5F5] font-medium">Iterative AI Optimization targeting 90+ ATS score</div>
                  <div className="text-xs text-neutral-500 mt-1">Multi-pass keyword injection and bullet refinement until 90+ score is hit.</div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button onClick={onOptimize} disabled={optimizing || autoOptimizing}
                    className="bg-[#2563EB] text-white hover:bg-[#1D4ED8] rounded-full px-5">
                    <Sparkles className="w-4 h-4 mr-2" />
                    {optimizing ? "Optimizing..." : "Standard Rewrite"}
                  </Button>
                  <Button onClick={onAutoOptimize} disabled={optimizing || autoOptimizing}
                    className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white font-semibold rounded-full px-5 shadow-lg border border-amber-400/30 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-200 fill-amber-200" />
                    {autoOptimizing ? "Boosting to 90+..." : "Boost to 90+ ATS"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Gap Analysis */}
        <TabsContent value="gap" className="mt-8">
          <div data-testid={RESUME.gapTable} className="card-solid overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left label-caps">
                  <th className="px-6 py-4 font-semibold w-2/5">Requirement</th>
                  <th className="px-6 py-4 font-semibold w-1/6">Match</th>
                  <th className="px-6 py-4 font-semibold">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {gap.length === 0 && (
                  <tr><td className="px-6 py-6 text-neutral-500" colSpan={3}>No requirements returned.</td></tr>
                )}
                {gap.map((row, i) => (
                  <tr key={i} className="border-t border-[#1F1F1F]">
                    <td className="px-6 py-4 text-[#F5F5F5]">{row.requirement}</td>
                    <td className="px-6 py-4"><MatchBadge match={row.match} /></td>
                    <td className="px-6 py-4 text-neutral-400">{row.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        {/* Missing */}
        <TabsContent value="missing" className="mt-8">
          <div data-testid={RESUME.missingList} className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { key: "high", label: "High Priority", items: missing.high || [], cls: "bg-[#2A0B0B] text-[#F87171] border-[#DC2626]/40" },
              { key: "medium", label: "Medium", items: missing.medium || [], cls: "bg-[#2A1B05] text-[#FBBF24] border-[#D97706]/40" },
              { key: "optional", label: "Optional", items: missing.optional || [], cls: "bg-[#0F1B2E] text-[#93C5FD] border-[#2563EB]/40" },
            ].map((g) => (
              <div key={g.key} className="card-solid p-6">
                <div className="label-caps mb-4">{g.label}</div>
                {g.items.length === 0 ? (
                  <div className="text-sm text-neutral-500">Nothing missing here.</div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {g.items.map((s, i) => (
                      <Badge key={i} className={`border ${g.cls} bg-transparent`}>{s}</Badge>
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
                  <Sparkles className="w-4 h-4 mr-2 text-amber-200 fill-amber-200" />
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
                    className="bg-[#0A2C1A] border-[#16A34A]/40 text-[#4ADE80] hover:bg-[#16A34A] hover:text-white rounded-full text-xs px-4 h-9 flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
                  >
                    <BarChart2 className="w-3.5 h-3.5" />
                    <span>{reEvaluating ? "Evaluating Real ATS..." : "Check Real ATS Score"}</span>
                  </Button>

                  <Button
                    onClick={onAutoOptimize}
                    disabled={optimizing || autoOptimizing || reEvaluating}
                    className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white text-xs font-semibold rounded-full px-4 h-9 shadow border border-amber-400/30 flex items-center gap-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-200 fill-amber-200" />
                    {autoOptimizing ? "Re-Boosting..." : "Re-Optimize to 90+"}
                  </Button>

                  <div className="flex bg-[#0A0A0A] border border-[#262626] rounded-full p-1">
                    <button
                      type="button"
                      onClick={() => setEditorMode("interactive")}
                      className={`px-3 py-1 text-xs rounded-full flex items-center gap-1.5 transition-all ${
                        editorMode === "interactive"
                          ? "bg-[#2563EB] text-white font-medium shadow"
                          : "text-neutral-400 hover:text-white"
                      }`}
                    >
                      <Sparkles className="w-3.5 h-3.5 text-indigo-300" />
                      <span>Interactive AI Editor</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditorMode("raw")}
                      className={`px-3 py-1 text-xs rounded-full flex items-center gap-1.5 transition-all ${
                        editorMode === "raw"
                          ? "bg-[#2563EB] text-white font-medium shadow"
                          : "text-neutral-400 hover:text-white"
                      }`}
                    >
                      <Code className="w-3.5 h-3.5" />
                      <span>Plain Text</span>
                    </button>
                  </div>

                  <Button
                    onClick={saveToTracker}
                    disabled={savingToTracker}
                    variant="outline"
                    className="bg-transparent border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/20 hover:text-white rounded-full"
                  >
                    <BookmarkPlus className="w-4 h-4 mr-2 text-indigo-400" />
                    {savingToTracker ? "Saving..." : "Save to Tracker"}
                  </Button>
                  <Button data-testid={RESUME.copyResumeBtn} variant="outline"
                    onClick={() => copyText(activeResumeText, "Optimized resume")}
                    className="bg-transparent border-[#262626] text-neutral-200 hover:bg-[#1F1F1F] hover:text-white rounded-full">
                    <Copy className="w-4 h-4 mr-2" /> Copy
                  </Button>
                  <Button data-testid={RESUME.downloadPdfBtn} onClick={downloadResumePdf}
                    className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full">
                    <Download className="w-4 h-4 mr-2" /> Export
                  </Button>
                </div>
              </div>

              {editorMode === "interactive" ? (
                <InteractiveBulletEditor
                  resumeText={activeResumeText}
                  onUpdateResumeText={setCurrentResumeText}
                  jobDescription={analysis?.job_description || ""}
                  authHeaders={{ Authorization: `Bearer ${token}` }}
                />
              ) : (
                <pre data-testid={RESUME.optimizedResume}
                  className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-neutral-200 bg-[#0A0A0A] border border-[#1F1F1F] rounded-md p-6 max-h-[70vh] overflow-auto">
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
                  <div className="text-sm text-neutral-400">Tailored for <span className="text-white">{analysis?.job_title || "the role"}</span></div>
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
          {!optimization ? (
            <div className="card-solid p-12 text-center text-neutral-500">
              Optimize the resume first to see a before/after comparison.
            </div>
          ) : (
            <SimpleDiff before={originalResumeText} after={optimization.optimized_resume} />
          )}
        </TabsContent>
      </Tabs>

      <ExportModal
        open={exportModal.open}
        onClose={() => setExportModal({ open: false, type: "resume" })}
        title={exportModal.type === "cover_letter" ? "Export Cover Letter" : "Export Optimized Resume"}
        downloadType={exportModal.type}
        resumeText={activeResumeText}
        coverLetterText={coverLetter || ""}
        candidateName={user?.name || ""}
        jobTitle={analysis?.job_title || ""}
        filename={exportModal.type === "cover_letter" ? "cover-letter" : "resume-optimized"}
        token={token}
        backendUrl={API.replace(/\/api$/, "")}
      />
    </div>
  );
}
