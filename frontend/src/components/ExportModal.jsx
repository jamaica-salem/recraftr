import React, { useState } from "react";
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
  Layout,
  Check,
  Code2,
} from "lucide-react";
import { toast } from "sonner";

const PRESET_THEMES = [
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
  const [template, setTemplate] = useState("modern");
  const [primaryColor, setPrimaryColor] = useState("#1E3A8A");
  const [fontFamily, setFontFamily] = useState("Helvetica");
  const [headerAlign, setHeaderAlign] = useState("left");
  const [exportFormat, setExportFormat] = useState("pdf");
  const [downloading, setDownloading] = useState(false);

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
      <DialogContent className="max-w-xl bg-slate-900 border-slate-800 text-white rounded-xl shadow-2xl p-6">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            {title}
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-sm">
            Customize layout, theme colors, and typography before downloading.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 my-2">
          {/* Format Selection */}
          <div>
            <Label className="text-xs uppercase font-semibold text-slate-400 tracking-wider mb-2 block">
              Export Format
            </Label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setExportFormat("pdf")}
                className={`flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                  exportFormat === "pdf"
                    ? "border-indigo-500 bg-indigo-500/10 text-white font-medium shadow"
                    : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700"
                }`}
              >
                <FileText className="w-5 h-5 text-indigo-400" />
                <div>
                  <div className="text-sm font-semibold">PDF Document</div>
                  <div className="text-xs text-slate-400">
                    ATS-Compliant Printable PDF
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setExportFormat("html")}
                className={`flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                  exportFormat === "html"
                    ? "border-indigo-500 bg-indigo-500/10 text-white font-medium shadow"
                    : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700"
                }`}
              >
                <Code2 className="w-5 h-5 text-emerald-400" />
                <div>
                  <div className="text-sm font-semibold">HTML & CSS</div>
                  <div className="text-xs text-slate-400">
                    Editable Web Page Resume
                  </div>
                </div>
              </button>
            </div>
          </div>

          {/* Theme Presets */}
          <div>
            <Label className="text-xs uppercase font-semibold text-slate-400 tracking-wider mb-2 flex items-center justify-between">
              <span>Select Design Theme</span>
            </Label>
            <div className="grid grid-cols-2 gap-3">
              {PRESET_THEMES.map((th) => {
                const active = template === th.id;
                return (
                  <button
                    key={th.id}
                    type="button"
                    onClick={() => {
                      setTemplate(th.id);
                      if (th.id === "elegant") setFontFamily("Times-Roman");
                      if (th.id === "classic") setPrimaryColor("#0A0A0A");
                    }}
                    className={`relative p-3 rounded-lg border text-left transition-all ${
                      active
                        ? "border-indigo-500 bg-indigo-500/10 text-white shadow-md ring-1 ring-indigo-500"
                        : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-white">
                        {th.name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300 font-medium">
                        {th.badge}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 line-clamp-1">
                      {th.desc}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Color Palette */}
          <div>
            <Label className="text-xs uppercase font-semibold text-slate-400 tracking-wider mb-2 flex items-center gap-2">
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
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-transform ${
                    primaryColor === sw.value
                      ? "scale-110 ring-2 ring-white ring-offset-2 ring-offset-slate-900"
                      : "opacity-80 hover:opacity-100"
                  }`}
                  style={{ backgroundColor: sw.value }}
                >
                  {primaryColor === sw.value && (
                    <Check className="w-4 h-4 text-white drop-shadow" />
                  )}
                </button>
              ))}
              <input
                type="color"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                className="w-8 h-8 rounded border border-slate-700 bg-transparent cursor-pointer"
                title="Custom Color"
              />
            </div>
          </div>

          {/* Typography & Alignment */}
          <div className="grid grid-cols-2 gap-4">
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

        <DialogFooter className="mt-4 gap-2">
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
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex items-center gap-2 px-5"
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
