import React, { useRef, useState } from "react";
import { UploadCloud, FileCheck2, X, Sparkles } from "lucide-react";
import { toast } from "sonner";
import axios from "axios";
import { API, useAuth } from "@/context/AuthContext";
import { RESUME } from "@/constants/testIds";
import { Button } from "@/components/ui/button";

export default function UploadZone({ onUploaded, uploaded, onClear, onLoadSample }) {
  const { authHeaders } = useAuth();
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);

  const uploadFile = async (file) => {
    if (!file) return;
    const okExt = /\.(pdf|docx)$/i.test(file.name);
    if (!okExt) {
      toast.error("Only PDF or DOCX files are supported.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error("File must be smaller than 5 MB.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await axios.post(`${API}/upload-resume`, form, {
        headers: { ...authHeaders, "Content-Type": "multipart/form-data" },
      });
      onUploaded(res.data);
      toast.success("Resume uploaded and parsed");
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
          ? detail[0]?.msg || "Invalid upload parameters"
          : typeof detail === "object" && detail !== null
          ? JSON.stringify(detail)
          : e?.message || "Upload failed";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    uploadFile(f);
  };

  if (uploaded) {
    return (
      <div
        data-testid={RESUME.uploadedFile}
        className="card-solid p-6 flex items-start gap-4"
      >
        <div className="w-11 h-11 rounded-md bg-[#0A2C1A] border border-[#16A34A]/40 flex items-center justify-center flex-shrink-0">
          <FileCheck2 className="w-5 h-5 text-[#4ADE80]" strokeWidth={1.75} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] label-caps mb-1">Resume uploaded</div>
          <div className="text-[#F5F5F5] font-medium truncate">{uploaded.filename}</div>
          <div className="text-xs text-neutral-500 mt-1">
            {uploaded.char_count.toLocaleString()} characters parsed
          </div>
          <div className="mt-3 p-3 bg-[#0A0A0A] border border-[#262626] rounded-md text-xs text-neutral-400 font-mono leading-relaxed max-h-24 overflow-hidden">
            {uploaded.text_preview}...
          </div>
        </div>
        <Button
          data-testid={RESUME.uploadRemove}
          variant="ghost"
          size="icon"
          onClick={onClear}
          className="text-neutral-500 hover:text-white hover:bg-[#1F1F1F]"
          title="Remove"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>
    );
  }

  return (
    <div
      data-testid={RESUME.uploadZone}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-xl p-8 lg:p-10 cursor-pointer transition-colors duration-200 ${
        dragOver ? "border-[#2563EB] bg-[#0E1830]" : "border-[#404040] bg-[#141414] hover:bg-[#1A1A1A]"
      }`}
    >
      <input
        ref={inputRef}
        data-testid={RESUME.uploadInput}
        type="file"
        accept=".pdf,.docx"
        className="hidden"
        onChange={(e) => uploadFile(e.target.files?.[0])}
      />
      <div className="flex flex-col items-start gap-4 w-full">
        <div className="w-12 h-12 rounded-lg bg-[#1F1F1F] border border-[#262626] flex items-center justify-center">
          <UploadCloud className="w-6 h-6 text-[#2563EB]" strokeWidth={1.75} />
        </div>
        <div>
          <div className="label-caps mb-2">Step 1</div>
          <div className="font-display text-xl text-[#F5F5F5] mb-1">
            {busy ? "Parsing resume..." : "Drop your resume here"}
          </div>
          <div className="text-sm text-neutral-400">
            PDF or DOCX, up to 5 MB. Or click to browse.
          </div>
        </div>

        {onLoadSample && (
          <div className="pt-3 border-t border-[#1F1F1F] w-full mt-1 flex items-center justify-between gap-3">
            <span className="text-xs text-neutral-500">No file ready?</span>
            <Button
              type="button"
              data-testid={RESUME.loadSampleBtn}
              variant="outline"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onLoadSample();
              }}
              className="bg-[#1A1A1A] border-[#262626] text-[#F5F5F5] hover:bg-[#2563EB] hover:border-[#2563EB] hover:text-white rounded-lg text-xs h-8 px-3 flex items-center justify-center transition-all cursor-pointer"
            >
              <span>Load Sample Resume & JD</span>
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

