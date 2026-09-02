import React, { useEffect, useMemo, useRef, useState } from "react";
import AppHeader from "@/components/app/AppHeader";
import { API, useAuth } from "@/context/AuthContext";
import axios from "axios";
import { RESUME } from "@/constants/testIds";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { UploadCloud, Layers, Trash2, Loader2, Search } from "lucide-react";
import JdUrlFetcher from "@/components/app/JdUrlFetcher";

function scoreCls(s) {
  if ((s ?? 0) >= 80) return "text-[#4ADE80] border-[#16A34A]/40 bg-[#0B2818]";
  if ((s ?? 0) >= 60) return "text-[#FBBF24] border-[#D97706]/40 bg-[#2A1B05]";
  return "text-[#F87171] border-[#DC2626]/40 bg-[#2A0B0B]";
}
function scoreBar(v) {
  if ((v ?? 0) >= 80) return "#16A34A";
  if ((v ?? 0) >= 60) return "#D97706";
  return "#DC2626";
}

export default function Compare() {
  const { authHeaders } = useAuth();
  const inputRef = useRef(null);
  const [resumes, setResumes] = useState(null);
  const [selected, setSelected] = useState([]);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [uploading, setUploading] = useState(false);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [search, setSearch] = useState("");
  const [showAllVersions, setShowAllVersions] = useState(false);

  const loadResumes = async () => {
    try {
      const res = await axios.get(`${API}/resumes`, { headers: authHeaders });
      setResumes(res.data.items || []);
    } catch { setResumes([]); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadResumes(); }, []);

  // Build library view: optional dedupe by filename (keep newest by created_at) + search filter
  const libraryView = useMemo(() => {
    if (!resumes) return null;
    let items = [...resumes];
    if (!showAllVersions) {
      const seen = new Map(); // filename -> resume
      // resumes are already sorted desc by created_at (server-side)
      for (const r of items) {
        const key = (r.filename || "").toLowerCase().trim();
        if (!seen.has(key)) seen.set(key, r);
      }
      items = Array.from(seen.values());
    }
    const q = search.trim().toLowerCase();
    if (q) items = items.filter((r) => (r.filename || "").toLowerCase().includes(q));
    return items;
  }, [resumes, showAllVersions, search]);

  const duplicateCount = useMemo(() => {
    if (!resumes) return 0;
    const seen = new Set();
    let dupes = 0;
    for (const r of resumes) {
      const k = (r.filename || "").toLowerCase();
      if (seen.has(k)) dupes += 1; else seen.add(k);
    }
    return dupes;
  }, [resumes]);

  const upload = async (file) => {
    if (!file) return;
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      toast.error("Only PDF or DOCX allowed."); return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await axios.post(`${API}/upload-resume`, form, {
        headers: { ...authHeaders, "Content-Type": "multipart/form-data" },
      });
      toast.success(`Added ${res.data.filename}`);
      setSelected((s) => (s.length < 5 ? [...s, res.data.resume_id] : s));
      loadResumes();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally { setUploading(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this resume from your library?")) return;
    try {
      await axios.delete(`${API}/resumes/${id}`, { headers: authHeaders });
      setResumes(resumes.filter((r) => r.id !== id));
      setSelected(selected.filter((s) => s !== id));
    } catch { toast.error("Delete failed"); }
  };

  const toggle = (id) => {
    setSelected((s) => {
      if (s.includes(id)) return s.filter((x) => x !== id);
      if (s.length >= 5) { toast.error("Max 5 resumes per comparison"); return s; }
      return [...s, id];
    });
  };

  const runCompare = async () => {
    if (selected.length < 2) { toast.error("Pick at least 2 resumes"); return; }
    if (!jobTitle.trim() || jobDesc.trim().length < 30) {
      toast.error("Add a job title and description (min 30 chars)"); return;
    }
    setRunning(true);
    setResults(null);
    try {
      const res = await axios.post(
        `${API}/compare`,
        { resume_ids: selected, job_title: jobTitle, job_description: jobDesc },
        { headers: authHeaders, timeout: 90000 },
      );
      setResults(res.data.results || []);
      toast.success("Comparison complete");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Compare failed");
    } finally { setRunning(false); }
  };

  return (
    <>
      <AppHeader />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-12 py-12">
        <div className="mb-10">
          <div className="label-caps mb-3">Version Compare</div>
          <h1 className="font-display text-4xl sm:text-5xl font-medium tracking-tighter text-[#F5F5F5]">
            Which resume wins this role?
          </h1>
          <p className="text-neutral-400 mt-3 max-w-2xl">
            Score up to 5 different resume versions against the same job description — side by side. All 5 run in parallel.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Left: library */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <div className="label-caps">Resume library</div>
              <div className="text-[11px] text-neutral-500">{selected.length}/5 selected</div>
            </div>

            <div className="card-solid p-4 space-y-3">
              {/* Search + toggle */}
              <div className="flex items-center gap-2 rounded-md border border-[#1F1F1F] bg-[#0A0A0A] px-3 py-1 focus-within:border-[#2563EB] transition-colors">
                <Search className="w-4 h-4 text-neutral-500 flex-shrink-0" strokeWidth={1.75} />
                <Input
                  data-testid={RESUME.compareSearch}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by filename..."
                  className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 h-8 px-0 text-sm placeholder:text-neutral-600"
                />
                {search && (
                  <button
                    onClick={() => setSearch("")}
                    className="text-xs text-neutral-500 hover:text-white px-2"
                  >
                    Clear
                  </button>
                )}
              </div>

              {duplicateCount > 0 && (
                <label className="flex items-center gap-3 text-xs text-neutral-400 py-1 select-none">
                  <Switch
                    data-testid={RESUME.compareShowAllToggle}
                    checked={showAllVersions}
                    onCheckedChange={setShowAllVersions}
                  />
                  <span>
                    Show all {resumes.length} versions
                    <span className="text-neutral-600 ml-1">({duplicateCount} duplicate filename{duplicateCount > 1 ? "s" : ""} hidden)</span>
                  </span>
                </label>
              )}

              {/* List */}
              <div data-testid={RESUME.compareResumeList} className="space-y-2 max-h-[380px] overflow-auto pr-1">
                {libraryView === null && <div className="text-sm text-neutral-500">Loading...</div>}
                {libraryView && libraryView.length === 0 && (
                  <div className="text-sm text-neutral-500 py-4 text-center">
                    {resumes && resumes.length > 0 ? "No resumes match your search." : "No resumes yet."}
                  </div>
                )}
                {libraryView && libraryView.map((r) => (
                  <label
                    key={r.id}
                    data-testid={RESUME.compareResumeItem}
                    className="flex items-center gap-3 p-3 rounded-md border border-[#1F1F1F] hover:bg-[#1A1A1A] cursor-pointer transition-colors"
                  >
                    <Checkbox
                      checked={selected.includes(r.id)}
                      onCheckedChange={() => toggle(r.id)}
                      className="border-[#404040] data-[state=checked]:bg-[#2563EB] data-[state=checked]:border-[#2563EB]"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-[#F5F5F5] truncate">{r.filename}</div>
                      <div className="text-[11px] text-neutral-500">
                        {new Date(r.created_at).toLocaleString()}
                      </div>
                    </div>
                    <button
                      onClick={(e) => { e.preventDefault(); remove(r.id); }}
                      className="text-neutral-500 hover:text-[#F87171] p-1"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-4">
              <input
                ref={inputRef}
                data-testid={RESUME.compareUploadInput}
                type="file"
                accept=".pdf,.docx"
                className="hidden"
                onChange={(e) => upload(e.target.files?.[0])}
              />
              <Button
                data-testid={RESUME.compareUploadBtn}
                onClick={() => inputRef.current?.click()}
                disabled={uploading}
                variant="outline"
                className="w-full bg-transparent border-[#262626] text-neutral-200 hover:bg-[#1F1F1F] rounded-full h-11"
              >
                <UploadCloud className="w-4 h-4 mr-2" />
                {uploading ? "Uploading..." : "Add a resume version"}
              </Button>
            </div>
          </div>

          {/* Right: job details */}
          <div className="lg:col-span-3">
            <div className="label-caps mb-3">Job details</div>
            <div className="card-solid p-6 space-y-5">
              <JdUrlFetcher
                testIdInput={RESUME.compareJdUrl}
                testIdBtn={RESUME.compareJdUrlFetch}
                onFetched={({ job_title, job_description }) => {
                  if (job_title) setJobTitle(job_title);
                  if (job_description) setJobDesc(job_description);
                }}
              />
              <div>
                <Label className="text-xs text-neutral-400 mb-2 block">Job title</Label>
                <Input
                  data-testid={RESUME.compareJobTitle}
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  placeholder="e.g. Staff Product Designer"
                  className="bg-[#0A0A0A] border-[#262626] focus-visible:border-[#2563EB] focus-visible:ring-0 h-11"
                />
              </div>
              <div>
                <Label className="text-xs text-neutral-400 mb-2 block">Job description</Label>
                <Textarea
                  data-testid={RESUME.compareJobDesc}
                  value={jobDesc}
                  onChange={(e) => setJobDesc(e.target.value)}
                  placeholder="Paste the job description here..."
                  className="bg-[#0A0A0A] border-[#262626] focus-visible:border-[#2563EB] focus-visible:ring-0 min-h-[220px] font-mono text-xs leading-relaxed"
                />
              </div>
              <div className="flex items-center justify-end pt-2 border-t border-[#1F1F1F]">
                <Button
                  data-testid={RESUME.compareRunBtn}
                  onClick={runCompare}
                  disabled={running || selected.length < 2}
                  className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full h-11 px-6 disabled:opacity-40"
                >
                  {running ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Scoring {selected.length} versions in parallel...</>
                  ) : (
                    <><Layers className="w-4 h-4 mr-2" />Compare {selected.length || ""} versions</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Results */}
        {results && (
          <div data-testid={RESUME.compareResults} className="mt-12 rm-fade-up">
            <div className="label-caps mb-4">Results</div>
            <div className="card-solid overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left label-caps">
                    <th className="px-6 py-4 w-8">#</th>
                    <th className="px-6 py-4">Resume</th>
                    <th className="px-6 py-4">ATS</th>
                    <th className="px-6 py-4">Keywords</th>
                    <th className="px-6 py-4">Skills</th>
                    <th className="px-6 py-4">Experience</th>
                    <th className="px-6 py-4">Top gap</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => {
                    const gaps = (r.missing_skills?.high || []).slice(0, 2).join(", ") || "—";
                    return (
                      <tr key={r.resume_id} data-testid={RESUME.compareResultRow} className="border-t border-[#1F1F1F]">
                        <td className="px-6 py-4 text-neutral-500 font-mono">#{i + 1}</td>
                        <td className="px-6 py-4 text-[#F5F5F5] max-w-[240px] truncate">{r.filename || "Unknown"}</td>
                        <td className="px-6 py-4">
                          {r.error ? (
                            <span className="text-xs text-[#F87171]">Failed</span>
                          ) : (
                            <span className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-md border ${scoreCls(r.ats_score)}`}>
                              <span className="font-medium">{r.ats_score ?? "—"}</span>
                              <span className="opacity-60">/100</span>
                            </span>
                          )}
                        </td>
                        {["keyword_match", "skills_match", "experience_match"].map((k) => {
                          const v = r.breakdown?.[k];
                          return (
                            <td key={k} className="px-6 py-4 min-w-[110px]">
                              <div className="flex items-center gap-3">
                                <div className="w-16 h-1.5 bg-[#1F1F1F] rounded-full overflow-hidden">
                                  <div style={{ width: `${v || 0}%`, background: scoreBar(v) }} className="h-full" />
                                </div>
                                <span className="text-xs text-neutral-400 w-8">{v ?? "—"}</span>
                              </div>
                            </td>
                          );
                        })}
                        <td className="px-6 py-4 text-neutral-400 text-xs max-w-[220px] truncate">{gaps}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {results[0] && !results[0].error && (
              <div className="mt-4 text-sm text-neutral-400">
                Best fit: <span className="text-[#4ADE80] font-medium">{results[0].filename}</span> at ATS{" "}
                <span className="text-[#4ADE80] font-medium">{results[0].ats_score}</span>.
              </div>
            )}
          </div>
        )}
      </main>
    </>
  );
}
