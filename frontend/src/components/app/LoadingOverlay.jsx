import React, { useEffect, useRef, useState } from "react";
import { RESUME } from "@/constants/testIds";

const MESSAGES = {
  analyze: ["Parsing resume...", "Analyzing job match...", "Scoring against ATS..."],
  optimize: ["Rewriting bullets...", "Injecting keywords...", "Polishing for ATS 95+..."],
  auto_optimize: ["Evaluating current ATS score...", "Running iterative keyword boost...", "Refining bullets targeting 90+ ATS...", "Finalizing optimal resume..."],
  cover: ["Drafting your cover letter...", "Weaving in your best wins...", "Finalizing the closing line..."],
};

export default function LoadingOverlay({ kind, streamText = "" }) {
  const msgs = MESSAGES[kind] || MESSAGES.analyze;
  const [i, setI] = useState(0);
  const scrollerRef = useRef(null);

  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % msgs.length), 1600);
    return () => clearInterval(t);
  }, [msgs.length]);

  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [streamText]);

  // Strip JSON-noise for a slightly cleaner preview
  const preview = (streamText || "")
    .replace(/[{}\[\]"]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  return (
    <div
      data-testid={RESUME.loadingState}
      className="fixed inset-0 z-50 bg-[#0A0A0A]/95 backdrop-blur-sm flex flex-col items-center justify-center p-6"
    >
      <div className="w-full max-w-2xl">
        <div className="flex items-center gap-2 mb-6">
          <span className="w-2 h-2 bg-[#2563EB] rounded-full rm-dot" style={{ animationDelay: "0ms" }} />
          <span className="w-2 h-2 bg-[#2563EB] rounded-full rm-dot" style={{ animationDelay: "200ms" }} />
          <span className="w-2 h-2 bg-[#2563EB] rounded-full rm-dot" style={{ animationDelay: "400ms" }} />
          <span className="ml-3 label-caps">Live from the model</span>
        </div>
        <div className="font-display text-2xl sm:text-3xl text-[#F5F5F5] mb-6 tracking-tight">{msgs[i]}</div>

        <div
          ref={scrollerRef}
          data-testid={RESUME.streamPreview}
          className="card-solid p-5 h-48 overflow-hidden text-xs font-mono text-neutral-500 leading-relaxed whitespace-pre-wrap"
        >
          {preview || "Waiting for the first tokens..."}
        </div>
        <div className="text-xs text-neutral-600 mt-3 text-center">Usually 10–30 seconds. You can watch it think in real time.</div>
      </div>
    </div>
  );
}
