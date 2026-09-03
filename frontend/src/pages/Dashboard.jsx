import React, { useEffect, useState } from "react";
import AppHeader from "@/components/app/AppHeader";
import UploadZone from "@/components/app/UploadZone";
import ResultsDashboard from "@/components/app/ResultsDashboard";
import LoadingOverlay from "@/components/app/LoadingOverlay";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sparkles, Play } from "lucide-react";
import axios from "axios";
import { API, useAuth } from "@/context/AuthContext";
import { streamPost } from "@/lib/stream";
import { RESUME } from "@/constants/testIds";
import { toast } from "sonner";
import { useLocation } from "react-router-dom";
import JdUrlFetcher from "@/components/app/JdUrlFetcher";

export default function Dashboard() {
  const { authHeaders } = useAuth();
  const loc = useLocation();

  const [uploaded, setUploaded] = useState(null);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [aggressive, setAggressive] = useState(false);
  const [model, setModel] = useState("gemini-3.5-flash");

  const [analysis, setAnalysis] = useState(null);
  const [optimization, setOptimization] = useState(null);
  const [originalText, setOriginalText] = useState("");
  const [coverLetter, setCoverLetter] = useState("");

  const [loading, setLoading] = useState(null); // "analyze" | "optimize" | "cover" | "sample"
  const [streamText, setStreamText] = useState("");

  const handleLoadSample = async () => {
    const sampleResumeText = `Alex Morgan
Senior Full Stack Engineer
alex.morgan@email.com | (555) 019-2834 | San Francisco, CA | github.com/alexmorgan

SUMMARY
Experienced Full Stack Engineer with 6+ years of expertise in building scalable web applications, microservices, and cloud architectures. Proven track record in React, Node.js, Python, and AWS.

EXPERIENCE
Senior Software Engineer | TechCorp Inc. | 2022 - Present
- Architected and deployed microservices handling 2M+ daily active requests using Node.js, FastAPI, and PostgreSQL.
- Led frontend migration from legacy stack to React 18 and Tailwind CSS, improving core web vitals LCP by 45%.
- Implemented CI/CD pipelines with GitHub Actions and Docker, reducing release cycle time from 3 days to 30 minutes.

Full Stack Developer | CloudScale Solutions | 2019 - 2022
- Developed interactive analytics dashboards for enterprise client managing $50M+ in quarterly revenues.
- Integrated OpenAI & Gemini API services for automated report generation, increasing client engagement by 30%.
- Optimized MongoDB database queries and indexing, cutting median API response latency from 450ms to 85ms.

SKILLS
- Languages: JavaScript (ES6+), TypeScript, Python, HTML5, CSS3, SQL
- Frontend: React, Redux, Next.js, Tailwind CSS, REST APIs, WebSockets
- Backend: Node.js, Express, FastAPI, PostgreSQL, MongoDB, Redis
- DevOps & Cloud: AWS (EC2, S3, Lambda), Docker, GitHub Actions, CI/CD

EDUCATION
B.S. in Computer Science | University of California, Berkeley | 2015 - 2019`;

    const sampleJobTitle = "Senior Full Stack Engineer";
    const sampleJobDesc = `We are seeking a Senior Full Stack Engineer to lead the design and implementation of next-generation AI-powered web applications. In this role, you will work closely with product and data science teams to deliver highly scalable backend services and responsive frontend interfaces.

Key Responsibilities:
- Design, build, and maintain scalable web applications using React, TypeScript, Python (FastAPI/Django), and Node.js.
- Architect real-time streaming architectures and AI integrations using OpenAI, Gemini, and vector databases.
- Optimize database performance across PostgreSQL, MongoDB, and Redis caching layers.
- Drive engineering best practices, code reviews, automated testing, and CI/CD deployment pipelines on AWS/Docker.
- Collaborate with product managers and UX designers to craft intuitive, performant user interfaces.

Requirements & Qualifications:
- 5+ years of experience building production web applications as a Full Stack Engineer.
- Proficiency with React, TypeScript, Python (FastAPI or Django), and Node.js.
- Deep hands-on experience with cloud infrastructure (AWS/GCP), Docker containers, and CI/CD pipelines.
- Experience with AI model integration, real-time SSE/WebSockets streaming, and LLM APIs.
- Strong analytical skills, performance optimization mindset, and passion for clean, readable code.`;

    try {
      setLoading("sample");
      const blob = new Blob([sampleResumeText], { type: "application/pdf" });
      const file = new File([blob], "sample_resume_alex_morgan.pdf", { type: "application/pdf" });
      const form = new FormData();
      form.append("file", file);

      const res = await axios.post(`${API}/upload-resume`, form, {
        headers: { ...authHeaders, "Content-Type": "multipart/form-data" },
      });

      setUploaded(res.data);
      setJobTitle(sampleJobTitle);
      setJobDesc(sampleJobDesc);
      setAnalysis(null);
      setOptimization(null);
      setCoverLetter("");
      toast.success("Loaded sample resume & job description! Click 'Analyze Resume' to test.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load sample resume");
    } finally {
      setLoading(null);
    }
  };

  // Load a past analysis when redirected from History
  useEffect(() => {
    const st = loc.state;
    if (st?.loadedAnalysis) {
      const la = st.loadedAnalysis;
      const a = la.analysis || {};
      setAnalysis({ analysis_id: la.id, ...a });
      setJobTitle(la.job_title || "");
      setJobDesc(la.job_description || "");
      setUploaded({
        resume_id: la.resume_id, filename: la.resume_filename,
        text_preview: (la.original_resume_text || "").slice(0, 400),
        char_count: (la.original_resume_text || "").length,
      });
      if (la.optimization) {
        setOptimization(la.optimization);
        setOriginalText(la.original_resume_text || "");
      }
      if (la.cover_letter) setCoverLetter(la.cover_letter);
      window.history.replaceState({}, "");
    }
  }, [loc.state]);

  const canAnalyze = uploaded && jobTitle.trim() && jobDesc.trim().length > 30;

  const runAnalyze = async () => {
    if (!canAnalyze) {
      toast.error("Upload a resume and add a job title + description first.");
      return null;
    }
    setLoading("analyze");
    setStreamText("");
    setOptimization(null);
    setCoverLetter("");
    setAnalysis(null);
    let saved = null;
    try {
      await streamPost(
        `${API}/analyze-stream`,
        { resume_id: uploaded.resume_id, job_title: jobTitle, job_description: jobDesc, model },
        authHeaders,
        (ev) => {
          if (ev.type === "delta") setStreamText((prev) => prev + ev.text);
          else if (ev.type === "done") saved = { analysis_id: ev.analysis_id, job_title: jobTitle, job_description: jobDesc, ...(ev.result || {}) };
          else if (ev.type === "error") throw new Error(ev.error);
        },
      );
      if (saved) {
        setAnalysis(saved);
        toast.success(`ATS score: ${saved.ats_score}`);
      }
      return saved;
    } catch (e) {
      toast.error(e?.message || "Analysis failed");
      return null;
    } finally {
      setLoading(null);
    }
  };

  const runOptimize = async () => {
    let currentAnalysis = analysis;
    if (!currentAnalysis?.analysis_id) {
      if (!canAnalyze) {
        toast.error("Upload a resume and add a job description first.");
        return;
      }
      currentAnalysis = await runAnalyze();
      if (!currentAnalysis?.analysis_id) return;
    }
    setLoading("optimize");
    setStreamText("");
    try {
      let done = null;
      await streamPost(
        `${API}/optimize-stream`,
        { analysis_id: currentAnalysis.analysis_id, aggressive },
        authHeaders,
        (ev) => {
          if (ev.type === "delta") setStreamText((prev) => prev + ev.text);
          else if (ev.type === "done") done = ev;
          else if (ev.type === "error") throw new Error(ev.error);
        },
      );
      if (done) {
        setOptimization({
          optimized_resume: done.result?.optimized_resume,
          predicted_ats_score: done.result?.predicted_ats_score,
          changes_summary: done.result?.changes_summary,
          aggressive,
        });
        setOriginalText(done.original_resume_text || "");
        toast.success("Optimized resume ready");
      }
    } catch (e) {
      toast.error(e?.message || "Optimization failed");
    } finally {
      setLoading(null);
    }
  };

  const runAutoOptimize = async () => {
    let currentAnalysis = analysis;
    if (!currentAnalysis?.analysis_id) {
      if (!canAnalyze) {
        toast.error("Upload a resume and add a job description first.");
        return;
      }
      currentAnalysis = await runAnalyze();
      if (!currentAnalysis?.analysis_id) return;
    }
    setLoading("auto_optimize");
    setStreamText("");
    try {
      let done = null;
      await streamPost(
        `${API}/auto-optimize-stream`,
        { analysis_id: currentAnalysis.analysis_id, target_score: 90 },
        authHeaders,
        (ev) => {
          if (ev.type === "delta") setStreamText((prev) => prev + ev.text);
          else if (ev.type === "done") done = ev;
          else if (ev.type === "error") throw new Error(ev.error);
        },
      );
      if (done) {
        setOptimization({
          optimized_resume: done.result?.optimized_resume,
          predicted_ats_score: done.result?.predicted_ats_score,
          changes_summary: done.result?.changes_summary,
          aggressive: true,
          auto_boosted: true,
        });
        setOriginalText(done.original_resume_text || "");
        toast.success(`🚀 Reached ${done.result?.predicted_ats_score || 90}+ ATS Score!`);
      }
    } catch (e) {
      toast.error(e?.message || "Auto-optimization failed");
    } finally {
      setLoading(null);
    }
  };

  const runCoverLetter = async () => {
    if (!analysis?.analysis_id) {
      toast.error("Run an analysis first to generate a cover letter.");
      return;
    }
    setLoading("cover");
    setStreamText("");
    try {
      let letter = null;
      await streamPost(
        `${API}/cover-letter-stream`,
        { analysis_id: analysis.analysis_id },
        authHeaders,
        (ev) => {
          if (ev.type === "delta") setStreamText((prev) => prev + ev.text);
          else if (ev.type === "done") letter = ev.cover_letter;
          else if (ev.type === "error") throw new Error(ev.error);
        },
      );
      if (letter) {
        setCoverLetter(letter);
        toast.success("Cover letter ready");
      }
    } catch (e) {
      toast.error(e?.message || "Cover letter generation failed");
    } finally {
      setLoading(null);
    }
  };

  const runReEvaluateATS = async (customResumeText) => {
    const textToAnalyze = customResumeText || optimization?.optimized_resume || originalText;
    if (!textToAnalyze || textToAnalyze.trim().length < 30) {
      toast.error("No valid resume text to evaluate.");
      return;
    }
    if (!jobTitle.trim() || !jobDesc.trim()) {
      toast.error("Job title and job description are required for ATS evaluation.");
      return;
    }
    setLoading("re_evaluate");
    setStreamText("");
    try {
      let saved = null;
      await streamPost(
        `${API}/analyze-stream`,
        { resume_text: textToAnalyze, job_title: jobTitle, job_description: jobDesc, model },
        authHeaders,
        (ev) => {
          if (ev.type === "delta") setStreamText((prev) => prev + ev.text);
          else if (ev.type === "done") saved = { analysis_id: ev.analysis_id, job_title: jobTitle, job_description: jobDesc, ...(ev.result || {}) };
          else if (ev.type === "error") throw new Error(ev.error);
        },
      );
      if (saved) {
        setAnalysis(saved);
        if (optimization) {
          setOptimization((prev) => ({
            ...prev,
            actual_ats_score: saved.ats_score,
          }));
        }
        toast.success(`Evaluated Real ATS score: ${saved.ats_score}/100!`);
      }
    } catch (e) {
      toast.error(e?.message || "ATS re-evaluation failed");
    } finally {
      setLoading(null);
    }
  };

  return (
    <>
      <AppHeader />
      {loading && <LoadingOverlay kind={loading} streamText={streamText} />}

      <main className="max-w-[1400px] mx-auto px-6 lg:px-12 py-10">
        <section className="mb-12 rm-fade-up">
          <div className="label-caps mb-3">Recraftr</div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-medium tracking-tighter leading-tight text-[#F5F5F5] max-w-3xl">
            Turn any resume into a{" "}
            <span className="text-[#2563EB]">95+ ATS match</span> for the role you actually want.
          </h1>
          <p className="text-neutral-400 mt-4 max-w-2xl leading-relaxed">
            Upload your resume, paste the job description, and watch the model rewrite bullets, inject the right keywords, and draft a matching cover letter — live, in real time.
          </p>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8">
          <div>
            <div className="label-caps mb-3">Resume</div>
            <UploadZone
              uploaded={uploaded}
              onUploaded={setUploaded}
              onClear={() => { setUploaded(null); setAnalysis(null); setOptimization(null); setCoverLetter(""); }}
              onLoadSample={handleLoadSample}
            />
          </div>

          <div>
            <div className="label-caps mb-3">Job details</div>
            <div className="card-solid p-6 space-y-5">
              <JdUrlFetcher
                testIdInput={RESUME.jdUrlInput}
                testIdBtn={RESUME.jdUrlFetchBtn}
                onFetched={({ job_title, job_description }) => {
                  if (job_title) setJobTitle(job_title);
                  if (job_description) setJobDesc(job_description);
                }}
              />
              <div>
                <Label className="text-xs text-neutral-400 mb-2 block">Job title</Label>
                <Input
                  data-testid={RESUME.jobTitleInput}
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  placeholder="e.g. Senior Frontend Engineer"
                  className="bg-[#0A0A0A] border-[#262626] focus-visible:border-[#2563EB] focus-visible:ring-0 h-11"
                />
              </div>
              <div>
                <Label className="text-xs text-neutral-400 mb-2 block">Job description</Label>
                <Textarea
                  data-testid={RESUME.jobDescInput}
                  value={jobDesc}
                  onChange={(e) => setJobDesc(e.target.value)}
                  placeholder="Paste the full job description here..."
                  className="bg-[#0A0A0A] border-[#262626] focus-visible:border-[#2563EB] focus-visible:ring-0 min-h-[220px] resize-y font-mono text-xs leading-relaxed"
                />
                <div className="text-[11px] text-neutral-600 mt-2">{jobDesc.length} characters</div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-[#1F1F1F]">
                <div>
                  <div className="text-sm text-[#F5F5F5]">Aggressive optimization</div>
                  <div className="text-xs text-neutral-500">More assertive rewriting & keyword injection.</div>
                </div>
                <Switch
                  data-testid={RESUME.aggressiveToggle}
                  checked={aggressive}
                  onCheckedChange={setAggressive}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label className="text-xs text-neutral-400">Model</Label>
                <Select value={model} onValueChange={setModel}>
                  <SelectTrigger data-testid={RESUME.modelSelect} className="w-[200px] bg-[#0A0A0A] border-[#262626]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#141414] border-[#262626]">
                    <SelectItem value="gemini-3.5-flash">Gemini 3.5 Flash (Primary AI)</SelectItem>
                    <SelectItem value="gemini-flash-latest">Gemini Flash (Fast AI)</SelectItem>
                    <SelectItem value="groq-gpt-oss-120b">Groq GPT-OSS 120B (Fallback AI)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 card-solid p-5 flex items-center justify-between gap-4 flex-wrap">
          <div className="text-xs text-neutral-500">
            {canAnalyze ? "Ready to run analysis or auto-optimize." : "Upload a resume and paste a job description to enable actions."}
          </div>
          <div className="flex gap-3 flex-wrap">
            <Button
              data-testid={RESUME.analyzeBtn}
              onClick={runAnalyze}
              disabled={!canAnalyze || !!loading}
              className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full px-6 h-11 disabled:opacity-40"
            >
              <Play className="w-4 h-4 mr-2" strokeWidth={2} />
              Analyze Resume
            </Button>
            <Button
              data-testid={RESUME.optimizeBtn}
              onClick={runOptimize}
              disabled={!canAnalyze || !!loading}
              variant="outline"
              className="bg-transparent border-[#262626] text-[#F5F5F5] hover:bg-[#1F1F1F] rounded-full px-6 h-11"
            >
              <Sparkles className="w-4 h-4 mr-2" strokeWidth={2} />
              Optimize Resume
            </Button>
            <Button
              onClick={runAutoOptimize}
              disabled={!canAnalyze || !!loading}
              className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white font-semibold rounded-full px-6 h-11 shadow-lg border border-amber-400/30 flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4 text-amber-200 fill-amber-200" />
              <span>Boost to 90+ ATS</span>
            </Button>
          </div>
        </section>

        {analysis && (
          <ResultsDashboard
            analysis={analysis}
            optimization={optimization}
            originalResumeText={originalText}
            coverLetter={coverLetter}
            jobTitle={jobTitle}
            jobDesc={jobDesc}
            onOptimize={runOptimize}
            onAutoOptimize={runAutoOptimize}
            onGenerateCoverLetter={runCoverLetter}
            onReEvaluateATS={runReEvaluateATS}
            optimizing={loading === "optimize"}
            autoOptimizing={loading === "auto_optimize"}
            coverLoading={loading === "cover"}
            reEvaluating={loading === "re_evaluate"}
          />
        )}
      </main>
    </>
  );
}
