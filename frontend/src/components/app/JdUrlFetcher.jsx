import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Link2, Wand2, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { API, useAuth } from "@/context/AuthContext";

/**
 * Small inline widget: paste a job URL, click, autofill title + description.
 * onFetched({ job_title, job_description })
 */
export default function JdUrlFetcher({ onFetched, testIdInput, testIdBtn }) {
  const { authHeaders } = useAuth();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const trimmed = url.trim();
    if (!/^https?:\/\//i.test(trimmed)) {
      toast.error("Enter a full URL starting with http:// or https://");
      return;
    }
    setBusy(true);
    try {
      const res = await axios.post(
        `${API}/scrape-jd`,
        { url: trimmed },
        { headers: authHeaders, timeout: 45000 },
      );
      onFetched(res.data);
      toast.success("Job details autofilled");
      setUrl("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || e?.message || "Failed to scrape");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2 rounded-md border border-[#1F1F1F] bg-[#0A0A0A] pl-3 pr-1 py-1 focus-within:border-[#2563EB] transition-colors">
      <Link2 className="w-4 h-4 text-neutral-500 flex-shrink-0" strokeWidth={1.75} />
      <Input
        data-testid={testIdInput}
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }}
        placeholder="Paste a job posting URL to autofill..."
        className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 h-8 px-0 text-sm placeholder:text-neutral-600"
        disabled={busy}
      />
      <Button
        data-testid={testIdBtn}
        onClick={submit}
        disabled={busy || !url.trim()}
        size="sm"
        className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-full h-8 px-3 flex-shrink-0"
      >
        {busy ? (
          <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />Fetching</>
        ) : (
          <><Wand2 className="w-3.5 h-3.5 mr-1.5" />Autofill</>
        )}
      </Button>
    </div>
  );
}
