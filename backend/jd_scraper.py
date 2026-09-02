"""Scrape a job posting URL and return {job_title, job_description}.

Strategy (in order):
1. Provider-specific public APIs for common ATS platforms (Greenhouse, Lever, Ashby).
   These are the modern job boards that render content client-side; scraping the
   HTML directly returns nothing.
2. schema.org JobPosting via <script type="application/ld+json">.
3. Fallback: clean-extract the visible body text and ask the LLM to distill it.
"""
import json
import re
import html as html_lib
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ai_service import _new_chat, _extract_json, DEFAULT_MODEL
from emergentintegrations.llm.chat import UserMessage

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _html_to_plain(html: str) -> str:
    """Convert an HTML fragment (or full page) to clean plaintext.
    Unescapes HTML entities first so provider APIs that return entity-encoded
    HTML (e.g. Greenhouse) don't leak literal <div>/<p>/<strong> into the output.
    """
    unescaped = html_lib.unescape(html or "")
    soup = BeautifulSoup(unescaped, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


# ---------------- Provider adapters ----------------
GREENHOUSE_HOST = re.compile(r"^(boards|job-boards)\.greenhouse\.io$", re.IGNORECASE)
GREENHOUSE_PATH = re.compile(r"^/(?:embed/job_app\?token=(\d+)|([^/]+)/jobs/(\d+))/?$", re.IGNORECASE)


def _try_greenhouse(url: str) -> Optional[Dict[str, str]]:
    p = urlparse(url)
    if not GREENHOUSE_HOST.match(p.netloc):
        return None
    m = GREENHOUSE_PATH.match(p.path)
    if not m:
        return None
    board_token, job_id = None, None
    if m.group(1):
        job_id = m.group(1)
    else:
        board_token = m.group(2)
        job_id = m.group(3)
    if not job_id:
        return None
    if board_token:
        api = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=false"
    else:
        # Old embed URL — the API needs a board token, we can't derive it. Bail.
        return None
    r = requests.get(api, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    title = (data.get("title") or "").strip()
    desc_html = data.get("content") or ""
    desc_text = _html_to_plain(desc_html)
    if title and len(desc_text) > 80:
        return {"job_title": title, "job_description": desc_text}
    return None


LEVER_HOST = re.compile(r"^jobs\.lever\.co$", re.IGNORECASE)
LEVER_PATH = re.compile(r"^/([^/]+)/([^/]+)/?$", re.IGNORECASE)


def _try_lever(url: str) -> Optional[Dict[str, str]]:
    p = urlparse(url)
    if not LEVER_HOST.match(p.netloc):
        return None
    m = LEVER_PATH.match(p.path)
    if not m:
        return None
    company, posting_id = m.group(1), m.group(2)
    api = f"https://api.lever.co/v0/postings/{company}/{posting_id}?mode=json"
    r = requests.get(api, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    title = (data.get("text") or "").strip()
    parts: List[str] = []
    if data.get("descriptionPlain"):
        parts.append(data["descriptionPlain"])
    elif data.get("description"):
        parts.append(_html_to_plain(data["description"]))
    for section in data.get("lists", []) or []:
        heading = (section.get("text") or "").strip()
        content = _html_to_plain(section.get("content") or "")
        if heading or content:
            parts.append(f"\n{heading}\n{content}".strip())
    if data.get("additionalPlain"):
        parts.append(data["additionalPlain"])
    desc = "\n\n".join([p for p in parts if p.strip()])
    if title and len(desc) > 80:
        return {"job_title": title, "job_description": desc}
    return None


ASHBY_HOST = re.compile(r"^jobs\.ashbyhq\.com$", re.IGNORECASE)


def _try_ashby(url: str) -> Optional[Dict[str, str]]:
    """Ashby exposes a public GraphQL endpoint. Skip complex GraphQL and instead
    try their JSON API: https://api.ashbyhq.com/posting-api/job-board/{org}
    then match by posting id in the URL path."""
    p = urlparse(url)
    if not ASHBY_HOST.match(p.netloc):
        return None
    parts = [s for s in p.path.split("/") if s]
    if len(parts) < 2:
        return None
    org, posting_id = parts[0], parts[1]
    api = f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=false"
    try:
        r = requests.get(api, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        for job in (data.get("jobs") or []):
            if job.get("id") == posting_id or job.get("jobUrl", "").endswith(posting_id):
                title = (job.get("title") or "").strip()
                desc = _html_to_plain(job.get("descriptionHtml") or job.get("descriptionPlain") or "")
                if title and len(desc) > 80:
                    return {"job_title": title, "job_description": desc}
    except Exception:
        return None
    return None


# ---------------- Generic paths ----------------
def _fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    r.raise_for_status()
    return r.text


def _collect_jsonld(html: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            raw = tag.string or tag.text or ""
            if not raw.strip():
                continue
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            out.extend([d for d in data if isinstance(d, dict)])
        elif isinstance(data, dict):
            if isinstance(data.get("@graph"), list):
                out.extend([d for d in data["@graph"] if isinstance(d, dict)])
            else:
                out.append(data)
    return out


def _try_jsonld(html: str) -> Optional[Dict[str, str]]:
    for node in _collect_jsonld(html):
        t = node.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            title = (node.get("title") or "").strip()
            desc_html = node.get("description") or ""
            desc_text = _html_to_plain(desc_html) if desc_html else ""
            if title and desc_text and len(desc_text) > 80:
                return {"job_title": title, "job_description": desc_text}
    return None


def _visible_body_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "svg"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


LLM_SYSTEM = "You extract job postings from raw web page text. Return ONE valid JSON object. No prose."
LLM_PROMPT = """Extract the job posting from the page content below.

PAGE CONTENT:
{content}

Return ONLY:
{{
  "job_title": "<the exact job title as posted>",
  "job_description": "<the full role description: responsibilities, requirements, qualifications; strip nav/footer text; keep line breaks as \\n>"
}}

If this page is NOT a job posting, return {{"job_title":"","job_description":""}}."""


async def _from_llm(content: str, model_key: str = DEFAULT_MODEL) -> Dict[str, str]:
    chat = _new_chat(LLM_SYSTEM, model_key)
    prompt = LLM_PROMPT.format(content=content[:14000])
    resp = await chat.send_message(UserMessage(text=prompt))
    parsed = _extract_json(resp if isinstance(resp, str) else str(resp))
    return {
        "job_title": (parsed.get("job_title") or "").strip(),
        "job_description": (parsed.get("job_description") or "").strip(),
    }


async def scrape_jd(url: str, model_key: str = DEFAULT_MODEL) -> Dict[str, str]:
    if not URL_RE.match(url or ""):
        raise ValueError("URL must start with http:// or https://")

    # 1. Provider-specific API adapters
    for adapter in (_try_greenhouse, _try_lever, _try_ashby):
        try:
            hit = adapter(url)
            if hit:
                return hit
        except Exception:
            continue

    # 2. Fetch HTML and try JSON-LD
    try:
        html = _fetch_html(url)
    except requests.HTTPError as e:
        raise ValueError(f"Could not fetch the URL ({e.response.status_code})")
    except Exception as e:
        raise ValueError(f"Could not fetch the URL: {e}")

    jld = _try_jsonld(html)
    if jld:
        return jld

    # 3. LLM fallback on cleaned body text
    text = _visible_body_text(html)
    if len(text) < 120:
        raise ValueError(
            "Couldn't extract job content from this page. Some sites (LinkedIn, Ashby) "
            "render content client-side — try pasting the description manually, or use "
            "a Greenhouse / Lever / company-careers URL."
        )
    return await _from_llm(text, model_key)
