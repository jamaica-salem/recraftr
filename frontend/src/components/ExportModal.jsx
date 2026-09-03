import React, { useState, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Download,
  FileText,
  Sparkles,
  Palette,
  Check,
  Code2,
  Eye,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from "lucide-react";
import { toast } from "sonner";
import { generateResumeHtmlPreview } from "@/lib/resumeTemplateHtml";

const PRESET_THEMES = [
  {
    id: "jamaica",
    name: "Jamaica Academic",
    desc: "Centered serif header, double horizontal divider rules & 2-column entries",
    badge: "Featured",
    color: "#0A0A0A",
  },
  {
    id: "classic",
    name: "Classic Minimal",
    desc: "Standard black/gray ATS layout",
    badge: "ATS Default",
    color: "#0A0A0A",
  },
  {
    id: "modern",
    name: "Modern Executive",
    desc: "Accent header titles with divider rules",
    badge: "Popular",
    color: "#1E3A8A",
  },
  {
    id: "compact",
    name: "Compact 1-Page",
    desc: "Dense spacing to fit multi-page content",
    badge: "Space Saver",
    color: "#111827",
  },
  {
    id: "elegant",
    name: "Serif Elegant",
    desc: "Centered headers with classic serif typography",
    badge: "Executive",
    color: "#1E293B",
  },
];

const COLOR_SWATCHES = [
  { id: "black", label: "Classic Black", value: "#0A0A0A" },
  { id: "navy", label: "Navy Blue", value: "#1E3A8A" },
  { id: "charcoal", label: "Charcoal", value: "#111827" },
  { id: "emerald", label: "Emerald", value: "#065F46" },
  { id: "purple", label: "Royal Purple", value: "#6D28D9" },
  { id: "wine", label: "Wine Red", value: "#991B1B" },
];

export default function ExportModal({
  open,
  onClose,
  title = "Export Resume",
  downloadType = "resume", // "resume" or "cover_letter"
  resumeText = "",
  coverLetterText = "",
  candidateName = "",
  jobTitle = "",
  filename = "resume-optimized",
  token = "",
  backendUrl = "",
}) {
  const [template, setTemplate] = useState("jamaica");
  const [primaryColor, setPrimaryColor] = useState("#0A0A0A");
  const [fontFamily, setFontFamily] = useState("Times-Roman");
  const [headerAlign, setHeaderAlign] = useState("center");
  const [exportFormat, setExportFormat] = useState("pdf");
  const [zoomScale, setZoomScale] = useState(0.85); // 0.75, 0.85, 1.0
  const [downloading, setDownloading] = useState(false);

  const rawDocumentText =
    downloadType === "cover_letter"
      ? `${candidateName}\nCover letter — ${jobTitle}\n\n${coverLetterText}`
      : resumeText;

  // Real-time live preview HTML string
  const previewHtml = useMemo(() => {
    return generateResumeHtmlPreview(
      rawDocumentText,
      downloadType,
      template,
      {
        primary_color: primaryColor,
        font_family: fontFamily,
        header_align: headerAlign,
      }
    );
  }, [rawDocumentText, downloadType, template, primaryColor, fontFamily, headerAlign]);

  const handleDownload = async () => {
    try {
      setDownloading(true);

      const endpoint =
        downloadType === "cover_letter"
          ? `${backendUrl}/api/cover-letter-pdf`
          : `${backendUrl}/api/download-pdf`;

      const payload =
        downloadType === "cover_letter"
          ? {
              cover_letter: coverLetterText,
              candidate_name: candidateName,
              job_title: jobTitle,
              filename: filename || "cover-letter",
              template: template,
              custom_styles: {
                primary_color: primaryColor,
                font_family: fontFamily,
                header_align: headerAlign,
              },
              format: exportFormat,
            }
          : {
              resume_text: resumeText,
              filename: filename || "resume-optimized",
              template: template,
              custom_styles: {
                primary_color: primaryColor,
                font_family: fontFamily,
                header_align: headerAlign,
              },
              format: exportFormat,
            };

      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Download failed");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${filename || "document"}.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      toast.success(
        `Exported ${exportFormat.toUpperCase()} using ${
          PRESET_THEMES.find((t) => t.id === template)?.name
        } theme!`
      );
      onClose();
    } catch (e) {
      toast.error(e.message || "Failed to download document");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="max-w-6xl w-[95vw] max-h-[92vh] bg-slate-900 border-slate-800 text-white rounded-xl shadow-2xl p-6 flex flex-col overflow-hidden">
        <DialogHeader className="pb-2 border-b border-slate-800">
          <DialogTitle className="text-xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            {title}
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Real-time split workspace: customize styles on the left, preview paper rendering on the right.
          </DialogDescription>
        </DialogHeader>

        {/* Side-by-Side Split Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 overflow-hidden my-3 min-h-0">
          {/* Left Controls Pane */}
          <div className="lg:col-span-5 space-y-4 overflow-y-auto pr-1">
            {/* Format Selection */}
            <div>
              <Label className="text-xs uppercase font-semibold text-slate-400 tracking-wider mb-2 block">
                Export Format
              </Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setExportFormat("pdf")}
                  className={`flex items-center gap-2.5 p-2.5 rounded-lg border text-left transition-all ${
                    exportFormat === "pdf"
                      ? "border-indigo-500 bg-indigo-500/10 text-white font-medium shadow"
                      : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <FileText className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <div>
                    <div className="text-xs font-semibold">PDF Document</div>
                    <div className="text-[10px] text-slate-400">Printable ATS PDF</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setExportFormat("html")}
                  className={`flex items-center gap-2.5 p-2.5 rounded-lg border text-left transition-all ${
                    exportFormat === "html"
                      ? "border-indigo-500 bg-indigo-500/10 text-white font-medium shadow"
                      : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <Code2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <div>
                    <div className="text-xs font-semibold">HTML & CSS</div>
                    <div className="text-[10px] text-slate-400">Editable Web Page</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Theme Presets */}
            <div>
              <Label className="text-xs uppercase font-semibold text-slate-400 tracking-wider mb-2 block">
                Select Design Theme
              </Label>
              <div className="grid grid-cols-2 gap-2.5">
                {PRESET_THEMES.map((th) => {
                  const active = template === th.id;
                  return (
                    <button
                      key={th.id}
                      type="button"
                      onClick={() => {
                        setTemplate(th.id);
                        if (th.id === "jamaica") {
                          setFontFamily("Times-Roman");
                          setPrimaryColor("#0A0A0A");
                          setHeaderAlign("center");
                        } else if (th.id === "elegant") {
                          setFontFamily("Times-Roman");
                        } else if (th.id === "classic") {
                          setPrimaryColor("#0A0A0A");
                        }
                      }}
                      className={`relative p-2.5 rounded-lg border text-left transition-all ${
                        active
                          ? "border-indigo-500 bg-indigo-500/10 text-white shadow-md ring-1 ring-indigo-500"
                          : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-white">
                          {th.name}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-1">
                        {th.desc}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Color Palette */}
            <div>
              <Label className="text-xs uppercase font-semibold text-slate-400 tracking-wider mb-2 flex items-center gap-1.5">
                <Palette className="w-3.5 h-3.5 text-indigo-400" />
                Primary Accent Color
              </Label>
              <div className="flex items-center gap-3">
                {COLOR_SWATCHES.map((sw) => (
                  <button
                    key={sw.id}
                    type="button"
                    onClick={() => setPrimaryColor(sw.value)}
                    title={sw.label}
                    className={`w-7 h-7 rounded-full flex items-center justify-center transition-transform ${
                      primaryColor === sw.value
                        ? "scale-110 ring-2 ring-white ring-offset-2 ring-offset-slate-900"
                        : "opacity-80 hover:opacity-100"
                    }`}
                    style={{ backgroundColor: sw.value }}
                  >
                    {primaryColor === sw.value && (
                      <Check className="w-3.5 h-3.5 text-white drop-shadow" />
                    )}
                  </button>
                ))}
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-7 h-7 rounded border border-slate-700 bg-transparent cursor-pointer"
                  title="Custom Color"
                />
              </div>
            </div>

            {/* Typography & Alignment */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold text-slate-400 mb-1.5 block">
                  Font Family
                </Label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setFontFamily("Helvetica")}
                    className={`flex-1 py-1.5 text-xs rounded border text-center transition-all ${
                      fontFamily === "Helvetica"
                        ? "border-indigo-500 bg-indigo-500/20 text-white font-medium"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    Sans-Serif
                  </button>
                  <button
                    type="button"
                    onClick={() => setFontFamily("Times-Roman")}
                    className={`flex-1 py-1.5 text-xs rounded border text-center font-serif transition-all ${
                      fontFamily === "Times-Roman"
                        ? "border-indigo-500 bg-indigo-500/20 text-white font-medium"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    Serif
                  </button>
                </div>
              </div>

              <div>
                <Label className="text-xs font-semibold text-slate-400 mb-1.5 block">
                  Header Alignment
                </Label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setHeaderAlign("left")}
                    className={`flex-1 py-1.5 text-xs rounded border text-center transition-all ${
                      headerAlign === "left"
                        ? "border-indigo-500 bg-indigo-500/20 text-white font-medium"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    Left
                  </button>
                  <button
                    type="button"
                    onClick={() => setHeaderAlign("center")}
                    className={`flex-1 py-1.5 text-xs rounded border text-center transition-all ${
                      headerAlign === "center"
                        ? "border-indigo-500 bg-indigo-500/20 text-white font-medium"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    Center
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Right Live Preview Canvas Pane */}
          <div className="lg:col-span-7 flex flex-col bg-slate-950 rounded-xl border border-slate-800 overflow-hidden">
            {/* Viewport Control Bar */}
            <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-800">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
                <Eye className="w-3.5 h-3.5 text-indigo-400" />
                <span>Live Canvas Preview</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300">
                  Instant Sync
                </span>
              </div>

              {/* Zoom Controls */}
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setZoomScale(Math.max(0.6, zoomScale - 0.1))}
                  className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-3.5 h-3.5" />
                </button>
                <span className="text-[11px] text-slate-400 font-mono w-10 text-center">
                  {Math.round(zoomScale * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => setZoomScale(Math.min(1.2, zoomScale + 0.1))}
                  className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800"
                  title="Zoom In"
                >
                  <ZoomIn className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoomScale(0.85)}
                  className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 ml-1"
                  title="Reset Fit"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Paper Sheet Viewport Container */}
            <div className="flex-1 overflow-auto p-4 flex items-start justify-center bg-slate-950/90">
              <div
                className="bg-white rounded shadow-2xl border border-slate-300 transition-transform origin-top"
                style={{
                  width: "500px",
                  minHeight: "650px",
                  transform: `scale(${zoomScale})`,
                }}
              >
                <iframe
                  title="Live Resume Preview"
                  srcDoc={previewHtml}
                  className="w-full h-full min-h-[650px] border-none rounded"
                />
              </div>
            </div>
          </div>
        </div>

        <DialogFooter className="pt-3 border-t border-slate-800 gap-2">
          <Button
            variant="ghost"
            onClick={onClose}
            className="text-slate-400 hover:text-white"
          >
            Cancel
          </Button>
          <Button
            onClick={handleDownload}
            disabled={downloading}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex items-center gap-2 px-6"
          >
            <Download className="w-4 h-4" />
            {downloading
              ? "Generating..."
              : `Download ${exportFormat.toUpperCase()}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
