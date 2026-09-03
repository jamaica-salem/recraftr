import React, { useEffect, useState } from "react";
import AppHeader from "@/components/app/AppHeader";
import { API, useAuth } from "@/context/AuthContext";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  FileText,
  Building2,
  MapPin,
  Sparkles,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
  Copy,
  Download,
  Notebook,
  GripVertical,
  Bookmark,
  Mic,
  Trophy,
  XCircle,
  Mail,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ExportModal from "@/components/ExportModal";

const KANBAN_STAGES = [
  { id: "bookmarked", label: "Bookmarked", icon: Bookmark, color: "text-blue-400" },
  { id: "applied", label: "Applied", icon: FileText, color: "text-purple-400" },
  { id: "interviewing", label: "Interviewing", icon: Mic, color: "text-amber-400" },
  { id: "offer", label: "Offer Received", icon: Trophy, color: "text-emerald-400" },
  { id: "rejected", label: "Rejected", icon: XCircle, color: "text-rose-400" },
];

export default function Tracker() {
  const { authHeaders, token, user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  // Drag and drop states
  const [draggedItemId, setDraggedItemId] = useState(null);
  const [dragOverStageId, setDragOverStageId] = useState(null);

  // Dialog states
  const [selectedApp, setSelectedApp] = useState(null); // for Package Detail Modal
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [exportModal, setExportModal] = useState({ open: false, type: "resume" });

  // Add Form state
  const [newTitle, setNewTitle] = useState("");
  const [newCompany, setNewCompany] = useState("");
  const [newLocation, setNewLocation] = useState("");
  const [newStatus, setNewStatus] = useState("applied");
  const [newNotes, setNewNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Detail Modal editable notes
  const [detailNotes, setDetailNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);

  const fetchApplications = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/applications`, { headers: authHeaders });
      setItems(res.data.items || []);
    } catch {
      toast.error("Failed to load application pipeline");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApplications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAddSubmit = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      toast.error("Please enter a job title");
      return;
    }
    try {
      setSubmitting(true);
      const res = await axios.post(
        `${API}/applications`,
        {
          job_title: newTitle,
          company_name: newCompany || "Target Company",
          location: newLocation,
          status: newStatus,
          notes: newNotes,
        },
        { headers: authHeaders }
      );
      setItems((prev) => [res.data, ...prev]);
      toast.success("Application added to tracker");
      setIsAddOpen(false);
      setNewTitle("");
      setNewCompany("");
      setNewLocation("");
      setNewNotes("");
    } catch {
      toast.error("Failed to add application");
    } finally {
      setSubmitting(false);
    }
  };

  const updateStage = async (id, currentStatus, direction) => {
    const stageIds = KANBAN_STAGES.map((s) => s.id);
    const currIndex = stageIds.indexOf(currentStatus);
    const nextIndex = currIndex + direction;

    if (nextIndex < 0 || nextIndex >= stageIds.length) return;

    const nextStatus = stageIds[nextIndex];

    try {
      const res = await axios.put(
        `${API}/applications/${id}`,
        { status: nextStatus },
        { headers: authHeaders }
      );
      setItems((prev) => prev.map((item) => (item.id === id ? res.data : item)));
      toast.success(`Moved to ${KANBAN_STAGES[nextIndex].label}`);
    } catch {
      toast.error("Failed to move stage");
    }
  };

  const handleDragStart = (e, itemId) => {
    setDraggedItemId(itemId);
    e.dataTransfer.setData("text/plain", itemId);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e, stageId) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragOverStageId !== stageId) {
      setDragOverStageId(stageId);
    }
  };

  const handleDragLeave = (e, stageId) => {
    if (dragOverStageId === stageId) {
      setDragOverStageId(null);
    }
  };

  const handleDragEnd = () => {
    setDraggedItemId(null);
    setDragOverStageId(null);
  };

  const handleDrop = async (e, targetStageId) => {
    e.preventDefault();
    const itemId = e.dataTransfer.getData("text/plain") || draggedItemId;
    setDraggedItemId(null);
    setDragOverStageId(null);

    if (!itemId) return;

    const targetItem = items.find((it) => it.id === itemId);
    if (!targetItem || targetItem.status === targetStageId) return;

    setItems((prev) =>
      prev.map((item) => (item.id === itemId ? { ...item, status: targetStageId } : item))
    );

    try {
      const res = await axios.put(
        `${API}/applications/${itemId}`,
        { status: targetStageId },
        { headers: authHeaders }
      );
      setItems((prev) => prev.map((item) => (item.id === itemId ? res.data : item)));
      const targetStage = KANBAN_STAGES.find((s) => s.id === targetStageId);
      toast.success(`Moved application to ${targetStage?.label || targetStageId}`);
    } catch {
      toast.error("Failed to update application status");
      setItems((prev) =>
        prev.map((item) => (item.id === itemId ? targetItem : item))
      );
    }
  };

  const handleDelete = async (id, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm("Delete this application from tracker?")) return;
    try {
      await axios.delete(`${API}/applications/${id}`, { headers: authHeaders });
      setItems((prev) => prev.filter((item) => item.id !== id));
      if (selectedApp?.id === id) setSelectedApp(null);
      toast.success("Application removed");
    } catch {
      toast.error("Failed to delete application");
    }
  };

  const handleSaveNotes = async () => {
    if (!selectedApp) return;
    try {
      setSavingNotes(true);
      const res = await axios.put(
        `${API}/applications/${selectedApp.id}`,
        { notes: detailNotes },
        { headers: authHeaders }
      );
      setItems((prev) => prev.map((item) => (item.id === selectedApp.id ? res.data : item)));
      setSelectedApp(res.data);
      toast.success("Notes saved");
    } catch {
      toast.error("Failed to save notes");
    } finally {
      setSavingNotes(false);
    }
  };

  const copyText = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text || "");
      toast.success(`${label} copied`);
    } catch {
      toast.error("Copy failed");
    }
  };

  return (
    <>
      <AppHeader />
      <main className="max-w-[1500px] mx-auto px-6 lg:px-12 py-10">
        {/* Title & Actions Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <div className="label-caps mb-2 text-indigo-400">Job Search Pipeline</div>
            <h1 className="font-display text-4xl font-medium tracking-tight text-[#F5F5F5]">
              Application Kanban Board
            </h1>
            <p className="text-neutral-400 text-sm mt-1">
              Track applications and review saved resume/cover letter packages for each target role.
            </p>
          </div>

          <Button
            onClick={() => setIsAddOpen(true)}
            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-full px-5 h-11 self-start md:self-auto shadow-lg flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>Add Application</span>
          </Button>
        </div>

        {/* Kanban Board Grid */}
        {loading ? (
          <div className="text-neutral-500 py-12 text-center">Loading pipeline...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-5">
            {KANBAN_STAGES.map((stage) => {
              const stageItems = items.filter((it) => (it.status || "applied") === stage.id);
              const isOver = dragOverStageId === stage.id;
              const StageIcon = stage.icon;
              return (
                <div
                  key={stage.id}
                  onDragOver={(e) => handleDragOver(e, stage.id)}
                  onDragLeave={(e) => handleDragLeave(e, stage.id)}
                  onDrop={(e) => handleDrop(e, stage.id)}
                  className={`border rounded-xl p-4 flex flex-col min-h-[650px] transition-all duration-200 ${
                    isOver
                      ? "bg-indigo-950/40 border-indigo-500/80 ring-2 ring-indigo-500/50 shadow-xl scale-[1.01]"
                      : "bg-slate-950/80 border-slate-800/80"
                  }`}
                >
                  {/* Column Header */}
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800">
                    <div className="flex items-center gap-2">
                      <StageIcon className={`w-4 h-4 ${stage.color}`} />
                      <span className="text-sm font-bold text-slate-200">{stage.label}</span>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono font-medium">
                      {stageItems.length}
                    </span>
                  </div>

                  {/* Column Cards */}
                  <div className="space-y-3 flex-1 overflow-y-auto pr-0.5">
                    {stageItems.length === 0 ? (
                      <div className={`text-xs italic text-center py-12 border-2 border-dashed rounded-lg transition-colors ${
                        isOver ? "border-indigo-500/50 text-indigo-300 bg-indigo-500/5" : "border-slate-800/60 text-slate-600"
                      }`}>
                        {isOver ? "Drop application here" : `No applications in ${stage.label.toLowerCase()}`}
                      </div>
                    ) : (
                      stageItems.map((item) => {
                        const isDraggingThis = draggedItemId === item.id;
                        return (
                          <div
                            key={item.id}
                            draggable={true}
                            onDragStart={(e) => handleDragStart(e, item.id)}
                            onDragEnd={handleDragEnd}
                            onClick={() => {
                              setSelectedApp(item);
                              setDetailNotes(item.notes || "");
                            }}
                            className={`group bg-slate-900/90 border rounded-lg p-4 cursor-grab active:cursor-grabbing hover:border-indigo-500/50 hover:bg-slate-900 transition-all shadow-md relative ${
                              isDraggingThis
                                ? "opacity-40 border-dashed border-indigo-400 scale-[0.98]"
                                : "border-slate-800"
                            }`}
                          >
                            {/* Company & Title */}
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <div>
                                <div className="text-xs font-semibold text-indigo-300 flex items-center gap-1 mb-0.5">
                                  <GripVertical className="w-3.5 h-3.5 text-slate-600 group-hover:text-indigo-400 flex-shrink-0 cursor-grab" />
                                  <Building2 className="w-3 h-3 text-indigo-400" />
                                  <span className="truncate max-w-[130px]">{item.company_name}</span>
                                </div>
                                <div className="text-sm font-bold text-white line-clamp-1">
                                  {item.job_title}
                                </div>
                              </div>
                              {item.ats_score != null && (
                                <span className="text-[11px] font-bold px-2 py-0.5 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 flex-shrink-0">
                                  {item.ats_score}%
                                </span>
                              )}
                            </div>

                            {/* Location & Package indicators */}
                            <div className="flex items-center justify-between text-[11px] text-slate-400 mt-3 pt-2 border-t border-slate-800/60">
                              {item.location ? (
                                <span className="flex items-center gap-1 text-slate-500">
                                  <MapPin className="w-3 h-3" />
                                  <span className="truncate max-w-[90px]">{item.location}</span>
                                </span>
                              ) : (
                                <span className="text-slate-600">No loc</span>
                              )}

                              <div className="flex items-center gap-2">
                                {item.optimized_resume && (
                                  <FileText className="w-3.5 h-3.5 text-blue-400" title="Saved Optimized Resume" />
                                )}
                                {item.cover_letter && (
                                  <Mail className="w-3.5 h-3.5 text-indigo-400" title="Saved Cover Letter" />
                                )}
                              </div>
                            </div>

                            {/* Hover Stage Quick Controls */}
                            <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-800/80">
                              <div className="flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    updateStage(item.id, item.status, -1);
                                  }}
                                  title="Move left"
                                  className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 disabled:opacity-30"
                                >
                                  <ChevronLeft className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    updateStage(item.id, item.status, 1);
                                  }}
                                  title="Move right"
                                  className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 disabled:opacity-30"
                                >
                                  <ChevronRight className="w-3.5 h-3.5" />
                                </button>
                              </div>

                              <button
                                type="button"
                                onClick={(e) => handleDelete(item.id, e)}
                                className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800"
                                title="Delete application"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Application Package Inspection Modal */}
      {selectedApp && (
        <Dialog open={!!selectedApp} onOpenChange={(val) => !val && setSelectedApp(null)}>
          <DialogContent className="max-w-4xl bg-slate-900 border-slate-800 text-white rounded-xl shadow-2xl p-6">
            <DialogHeader className="pb-3 border-b border-slate-800">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold text-indigo-400 flex items-center gap-1.5 mb-1">
                    <Building2 className="w-4 h-4" />
                    <span>{selectedApp.company_name}</span>
                    {selectedApp.location && (
                      <span className="text-slate-500 font-normal">| {selectedApp.location}</span>
                    )}
                  </div>
                  <DialogTitle className="text-2xl font-bold text-white">
                    {selectedApp.job_title}
                  </DialogTitle>
                </div>
                {selectedApp.ats_score != null && (
                  <div className="text-right">
                    <div className="text-xs text-slate-400">Match Score</div>
                    <div className="text-xl font-bold text-emerald-400">{selectedApp.ats_score}%</div>
                  </div>
                )}
              </div>
            </DialogHeader>

            <Tabs defaultValue="package" className="mt-4">
              <TabsList className="bg-slate-950 p-1 border border-slate-800 rounded-lg">
                <TabsTrigger value="package" className="text-xs">Saved Package</TabsTrigger>
                <TabsTrigger value="job_desc" className="text-xs">Job Description</TabsTrigger>
                <TabsTrigger value="notes" className="text-xs">Notes & Feedback</TabsTrigger>
              </TabsList>

              {/* Saved Resume & Cover Letter Package */}
              <TabsContent value="package" className="mt-4 space-y-5">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs uppercase font-bold text-slate-400">
                      Saved Optimized Resume
                    </Label>
                    {selectedApp.optimized_resume && (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => copyText(selectedApp.optimized_resume, "Resume")}
                          className="h-7 text-xs text-slate-300 hover:text-white"
                        >
                          <Copy className="w-3 h-3 mr-1" /> Copy
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => setExportModal({ open: true, type: "resume" })}
                          className="h-7 text-xs bg-indigo-600 hover:bg-indigo-500 text-white"
                        >
                          <Download className="w-3 h-3 mr-1" /> Export PDF/HTML
                        </Button>
                      </div>
                    )}
                  </div>
                  {selectedApp.optimized_resume ? (
                    <pre className="whitespace-pre-wrap font-mono text-xs text-neutral-200 bg-slate-950 p-4 rounded-lg border border-slate-800 max-h-60 overflow-y-auto">
                      {selectedApp.optimized_resume}
                    </pre>
                  ) : (
                    <div className="text-xs text-slate-500 bg-slate-950 p-4 rounded border border-slate-800 italic">
                      No optimized resume saved for this application.
                    </div>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs uppercase font-bold text-slate-400">
                      Saved Cover Letter
                    </Label>
                    {selectedApp.cover_letter && (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => copyText(selectedApp.cover_letter, "Cover Letter")}
                          className="h-7 text-xs text-slate-300 hover:text-white"
                        >
                          <Copy className="w-3 h-3 mr-1" /> Copy
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => setExportModal({ open: true, type: "cover_letter" })}
                          className="h-7 text-xs bg-indigo-600 hover:bg-indigo-500 text-white"
                        >
                          <Download className="w-3 h-3 mr-1" /> Export PDF/HTML
                        </Button>
                      </div>
                    )}
                  </div>
                  {selectedApp.cover_letter ? (
                    <div className="whitespace-pre-wrap text-xs text-neutral-200 bg-slate-950 p-4 rounded-lg border border-slate-800 max-h-48 overflow-y-auto leading-relaxed">
                      {selectedApp.cover_letter}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 bg-slate-950 p-4 rounded border border-slate-800 italic">
                      No cover letter saved for this application.
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* Job Description Reference */}
              <TabsContent value="job_desc" className="mt-4">
                <Label className="text-xs uppercase font-bold text-slate-400 mb-2 block">
                  Job Description Text
                </Label>
                {selectedApp.job_description ? (
                  <pre className="whitespace-pre-wrap font-mono text-xs text-neutral-300 bg-slate-950 p-4 rounded-lg border border-slate-800 max-h-80 overflow-y-auto">
                    {selectedApp.job_description}
                  </pre>
                ) : (
                  <div className="text-xs text-slate-500 bg-slate-950 p-4 rounded border border-slate-800 italic">
                    No job description attached.
                  </div>
                )}
              </TabsContent>

              {/* Notes & Feedback */}
              <TabsContent value="notes" className="mt-4 space-y-3">
                <Label className="text-xs uppercase font-bold text-slate-400 block">
                  Application Notes & Interview Reminders
                </Label>
                <Textarea
                  value={detailNotes}
                  onChange={(e) => setDetailNotes(e.target.value)}
                  placeholder="Add notes about recruiter contacts, salary range, interview rounds, etc..."
                  className="bg-slate-950 border-slate-800 text-white text-xs min-h-[160px]"
                />
                <Button
                  onClick={handleSaveNotes}
                  disabled={savingNotes}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-4 h-9"
                >
                  {savingNotes ? "Saving..." : "Save Notes"}
                </Button>
              </TabsContent>
            </Tabs>
          </DialogContent>
        </Dialog>
      )}

      {/* Manual Add Application Dialog */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent className="max-w-md bg-slate-900 border-slate-800 text-white rounded-xl p-6">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold">Add Tracked Application</DialogTitle>
            <DialogDescription className="text-xs text-slate-400">
              Add a new job application to your Kanban pipeline.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleAddSubmit} className="space-y-4 my-2">
            <div>
              <Label className="text-xs text-slate-300 mb-1 block">Job Title *</Label>
              <Input
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Senior Frontend Engineer"
                className="bg-slate-950 border-slate-800 text-white text-xs h-10"
              />
            </div>

            <div>
              <Label className="text-xs text-slate-300 mb-1 block">Company Name</Label>
              <Input
                value={newCompany}
                onChange={(e) => setNewCompany(e.target.value)}
                placeholder="e.g. Stripe, Acme Corp"
                className="bg-slate-950 border-slate-800 text-white text-xs h-10"
              />
            </div>

            <div>
              <Label className="text-xs text-slate-300 mb-1 block">Location</Label>
              <Input
                value={newLocation}
                onChange={(e) => setNewLocation(e.target.value)}
                placeholder="e.g. San Francisco, Remote"
                className="bg-slate-950 border-slate-800 text-white text-xs h-10"
              />
            </div>

            <div>
              <Label className="text-xs text-slate-300 mb-1 block">Initial Pipeline Stage</Label>
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 text-white text-xs h-10 rounded px-3"
              >
                {KANBAN_STAGES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.icon} {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label className="text-xs text-slate-300 mb-1 block">Notes</Label>
              <Textarea
                value={newNotes}
                onChange={(e) => setNewNotes(e.target.value)}
                placeholder="Referral details, link, etc..."
                className="bg-slate-950 border-slate-800 text-white text-xs min-h-[80px]"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button type="submit" disabled={submitting} className="bg-indigo-600 hover:bg-indigo-500 text-white w-full">
                {submitting ? "Adding..." : "Add to Tracker"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Export Modal Integration */}
      {selectedApp && (
        <ExportModal
          open={exportModal.open}
          onClose={() => setExportModal({ open: false, type: "resume" })}
          title={exportModal.type === "cover_letter" ? "Export Cover Letter" : "Export Resume"}
          downloadType={exportModal.type}
          resumeText={selectedApp.optimized_resume || ""}
          coverLetterText={selectedApp.cover_letter || ""}
          candidateName={user?.name || ""}
          jobTitle={selectedApp.job_title || ""}
          filename={selectedApp.job_title?.toLowerCase().replace(/\s+/g, "-") || "resume"}
          token={token}
          backendUrl={API.replace(/\/api$/, "")}
        />
      )}
    </>
  );
}
