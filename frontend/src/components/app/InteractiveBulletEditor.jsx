import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sparkles,
  BarChart3,
  Zap,
  Crown,
  Wrench,
  RotateCcw,
  Loader2,
  Check,
} from "lucide-react";
import { API } from "@/context/AuthContext";
import { toast } from "sonner";

const SECTION_HEADERS = new Set([
  "SUMMARY",
  "SKILLS",
  "EXPERIENCE",
  "EDUCATION",
  "PROJECTS",
  "CERTIFICATIONS",
  "AWARDS",
]);

export default function InteractiveBulletEditor({
  resumeText = "",
  initialResumeText = "",
  onUpdateResumeText,
  onChange,
  jobDescription = "",
  authHeaders = {},
}) {
  const [loadingLineIndex, setLoadingLineIndex] = useState(null);
  const [keywordInputs, setKeywordInputs] = useState({}); // { [lineIndex]: string }
  const [activeKeywordLine, setActiveKeywordLine] = useState(null);
  const [history, setHistory] = useState([]); // [{ index, prevText }]

  const activeText = initialResumeText || resumeText || "";
  const lines = activeText.split("\n");

  const notifyChange = (newText) => {
    if (onUpdateResumeText) onUpdateResumeText(newText);
    if (onChange) onChange(newText);
  };

  const handleRewrite = async (lineIndex, instruction) => {
    const originalLine = lines[lineIndex];
    const bulletContent = originalLine.replace(/^[-•*]\s*/, "").trim();

    if (!bulletContent) return;

    try {
      setLoadingLineIndex(lineIndex);
      setActiveKeywordLine(null);

      const res = await fetch(`${API}/rewrite-bullet`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({
          bullet_text: bulletContent,
          instruction: instruction,
          job_description: jobDescription,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Rewrite failed");
      }

      const data = await res.json();
      const newBulletText = data.rewritten_bullet || bulletContent;

      // Preserve bullet prefix formatting
      const newFullLine = `- ${newBulletText}`;

      const updatedLines = [...lines];
      updatedLines[lineIndex] = newFullLine;

      // Save to undo history
      setHistory((prev) => [
        { index: lineIndex, prevLine: originalLine },
        ...prev,
      ]);

      notifyChange(updatedLines.join("\n"));
      toast.success("Bullet point rewritten!");
    } catch (e) {
      toast.error(e.message || "Failed to rewrite bullet");
    } finally {
      setLoadingLineIndex(null);
    }
  };

  const handleUndo = (lineIndex) => {
    const histItem = history.find((h) => h.index === lineIndex);
    if (!histItem) return;

    const updatedLines = [...lines];
    updatedLines[lineIndex] = histItem.prevLine;

    setHistory((prev) => prev.filter((h) => h !== histItem));
    notifyChange(updatedLines.join("\n"));
    toast.info("Reverted to previous bullet");
  };

  return (
    <div className="space-y-2 font-mono text-sm leading-relaxed text-neutral-200 bg-[#0A0A0A] border border-[#1F1F1F] rounded-xl p-6">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1F1F1F]">
        <div className="flex items-center gap-2 text-xs text-neutral-400 font-sans">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>
            Hover over any bullet point below to trigger instant AI rewrites
          </span>
        </div>
        {history.length > 0 && (
          <span className="text-[11px] text-indigo-400 font-sans">
            {history.length} edit{history.length > 1 ? "s" : ""} made
          </span>
        )}
      </div>

      {lines.map((line, idx) => {
        const trimmed = line.trim();
        const upper = trimmed.toUpperCase().replace(/:$/, "");
        const isHeader = SECTION_HEADERS.has(upper);
        const isBullet = /^[-\u2022*]\s*/.test(trimmed);
        const isLoading = loadingLineIndex === idx;
        const hasHistory = history.some((h) => h.index === idx);

        if (isHeader) {
          return (
            <div
              key={idx}
              className="font-sans font-bold text-xs text-indigo-400 uppercase tracking-wider pt-4 pb-1 border-b border-indigo-900/30"
            >
              {trimmed}
            </div>
          );
        }

        if (isBullet) {
          return (
            <div
              key={idx}
              className="group relative rounded-lg p-2 transition-all hover:bg-slate-900/90 hover:ring-1 hover:ring-indigo-500/50 my-1"
            >
              <div className="flex items-start gap-2">
                <span className="text-indigo-400 font-bold select-none">•</span>
                <span className="flex-1 text-neutral-200">
                  {trimmed.replace(/^[-•*]\s*/, "")}
                </span>

                {isLoading && (
                  <div className="flex items-center gap-1.5 text-xs text-indigo-400 font-sans animate-pulse">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Rewriting...</span>
                  </div>
                )}
              </div>

              {/* Action Toolbar Overlay on Hover */}
              {!isLoading && (
                <div className="hidden group-hover:flex items-center gap-1.5 mt-2 pt-2 border-t border-slate-800/80 font-sans flex-wrap">
                  <span className="text-[10px] uppercase font-bold text-slate-500 mr-1">
                    AI Rewrite:
                  </span>

                  <button
                    type="button"
                    onClick={() => handleRewrite(idx, "metrics")}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 transition-all"
                    title="Make more metric & data-driven"
                  >
                    <BarChart3 className="w-3 h-3" />
                    <span>Add Metrics</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleRewrite(idx, "shorten")}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 hover:bg-amber-500/20 transition-all"
                    title="Shorten to concise single line"
                  >
                    <Zap className="w-3 h-3" />
                    <span>Shorten</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleRewrite(idx, "leadership")}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-500/20 transition-all"
                    title="Emphasize leadership & ownership"
                  >
                    <Crown className="w-3 h-3" />
                    <span>Leadership</span>
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setActiveKeywordLine(
                        activeKeywordLine === idx ? null : idx
                      )
                    }
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30 hover:bg-purple-500/20 transition-all"
                    title="Inject specific keyword"
                  >
                    <Wrench className="w-3 h-3" />
                    <span>Inject Tool</span>
                  </button>

                  {hasHistory && (
                    <button
                      type="button"
                      onClick={() => handleUndo(idx)}
                      className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all ml-auto"
                      title="Undo rewrite"
                    >
                      <RotateCcw className="w-3 h-3 text-slate-400" />
                      <span>Undo</span>
                    </button>
                  )}
                </div>
              )}

              {/* Inline Keyword Injection Input */}
              {activeKeywordLine === idx && (
                <div className="flex items-center gap-2 mt-2 font-sans bg-slate-950 p-2 rounded border border-purple-500/40">
                  <Input
                    placeholder="Enter keyword to inject (e.g. Docker, GraphQL, AWS)..."
                    value={keywordInputs[idx] || ""}
                    onChange={(e) =>
                      setKeywordInputs({
                        ...keywordInputs,
                        [idx]: e.target.value,
                      })
                    }
                    className="h-8 text-xs bg-slate-900 border-slate-700 text-white"
                  />
                  <Button
                    size="sm"
                    onClick={() => {
                      const kw = keywordInputs[idx] || "modern tools";
                      handleRewrite(idx, `inject keyword: ${kw}`);
                    }}
                    className="h-8 px-3 text-xs bg-purple-600 hover:bg-purple-500 text-white"
                  >
                    <Check className="w-3.5 h-3.5 mr-1" /> Inject
                  </Button>
                </div>
              )}
            </div>
          );
        }

        return (
          <div key={idx} className="py-0.5 text-neutral-300">
            {line}
          </div>
        );
      })}
    </div>
  );
}
