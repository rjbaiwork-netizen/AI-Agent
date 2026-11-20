"""Validated topic-based brain writes and bounded live HTTPS knowledge retrieval."""
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import os
import re
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from bot.tracer import append_trace
from agent.reverify import REQUIRED_BRAINS, reverify_all_brains

ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = ROOT / "agent" / "brains"
BOT_LOG = ROOT / "logs" / "bot.log"
MAX_SOURCE_BYTES = 512 * 1024
MAX_EXTRACTED_CHARS = 16000
DEFAULT_TIMEOUT = 12
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b", re.I),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b", re.I),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.I),
)

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _validate_text(value, field, maximum):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty")
    if len(value) > maximum:
        raise ValueError(f"{field} cannot exceed {maximum} characters")
    if field == "topic" and any(char in value for char in "\n\r"):
        raise ValueError("topic must be a single line")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in value):
        raise ValueError(f"{field} contains unsupported control characters")
    if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
        raise ValueError(f"{field} appears to contain a credential or private key; remove secrets before saving")
    return value

def _target_path(brain_file):
    if not isinstance(brain_file, str) or brain_file not in REQUIRED_BRAINS:
        raise ValueError("brain_file must name one of the seven registered brain documents")
    path = (BRAIN_DIR / brain_file).resolve()
    if path.parent != BRAIN_DIR.resolve():
        raise ValueError("Invalid brain file target")
    if not path.is_file():
        raise RuntimeError(f"Required brain file is missing: {brain_file}")
    return path

def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".brain-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise

def _record(event, details, status="ok"):
    safe_details = {key: value for key, value in details.items() if key not in {"content", "body"}}
    BOT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{_now()} | {event} | status={status} | {json.dumps(safe_details, ensure_ascii=False, sort_keys=True)}\n"
    with BOT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
    append_trace(event, safe_details, status=status, source="agent.brain_updates")

def update_topic(topic, content, brain_file="project_logic.md", source_url=None):
    topic = _validate_text(topic, "topic", 160)
    content = _validate_text(content, "content", 20000)
    path = _target_path(brain_file)
    original = path.read_text(encoding="utf-8")
    if not original.strip():
        raise RuntimeError(f"Brain document is empty: {brain_file}")
    marker = f"## Learned topic: {topic}"
    if marker.casefold() in original.casefold():
        raise ValueError(f"Topic already exists in {brain_file}; choose a distinct topic to avoid accidental duplication")
    source_line = f"\n\nSource: {source_url}" if source_url else ""
    section = f"\n\n{marker}\n\nUpdated: {_now()}\n\n{content}{source_line}\n"
    _atomic_write(path, original.rstrip() + section)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    verification = reverify_all_brains()
    if not verification.get("ok"):
        _atomic_write(path, original)
        reverify_all_brains()
        _record("brain_topic_update", {"topic": topic, "brain_file": brain_file, "sha256": digest}, "error")
        raise RuntimeError("Brain update rolled back because integrity re-verification failed; inspect latest.json")
    details = {"topic": topic, "brain_file": brain_file, "sha256": digest, "source_url": source_url, "verified": True}
    _record("brain_topic_update", details)
    return {"ok": True, **details, "verification": verification["summary"]}

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0
        self.title_parts = []
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "article"}:
            self.parts.append("\n")
    def handle_data(self, data):
        if self.skip_depth:
            return
        clean = " ".join(data.split())
        if clean:
            self.parts.append(clean)
            if self.in_title:
                self.title_parts.append(clean)

def _validate_public_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("url must be a valid HTTPS URL no longer than 2048 characters")
    parsed = urlsplit(url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS source URLs without embedded credentials are allowed")
    if parsed.query or parsed.fragment:
        raise ValueError("Source URLs must not contain query parameters or fragments; use a public documentation URL")
    if parsed.port not in (None, 443):
        raise ValueError("Only the standard HTTPS port 443 is allowed")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or "." not in host:
        raise ValueError("Local or non-public hostnames are not allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise RuntimeError(f"DNS lookup failed for source host: {type(exc).__name__}") from exc
    if not addresses:
        raise RuntimeError("Source hostname did not resolve to an IP address")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            raise ValueError("Source resolves to a non-public IP address; request blocked")
    return parsed.geturl()

class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        resolved = urljoin(req.full_url, newurl)
        _validate_public_url(resolved)
        return super().redirect_request(req, fp, code, msg, headers, resolved)

def _download_source(url, timeout=DEFAULT_TIMEOUT):
    url = _validate_public_url(url)
    request = Request(url, headers={"User-Agent": "PersonalBotAgent/1.0 (knowledge retrieval)", "Accept": "text/html,text/plain,application/json"})
    opener = build_opener(ProxyHandler({}), _SafeRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise RuntimeError(f"Source returned HTTP {status}")
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "text/plain", "application/json"}:
                raise ValueError(f"Unsupported source content type: {content_type}")
            body = response.read(MAX_SOURCE_BYTES + 1)
            if len(body) > MAX_SOURCE_BYTES:
                raise ValueError("Source exceeds the 512 KiB retrieval limit")
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                decoded = body.decode(charset, errors="strict")
            except (LookupError, UnicodeDecodeError) as exc:
                raise ValueError("Source response is not valid supported text encoding") from exc
            return content_type, decoded, response.geturl()
    except HTTPError as exc:
        raise RuntimeError(f"Source returned HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise TimeoutError(f"Source request timed out after {timeout} seconds") from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise TimeoutError(f"Source request timed out after {timeout} seconds") from exc
        raise RuntimeError(f"Source network error: {type(reason).__name__}") from exc


def _extractive_summary(text, max_sentences=6):
    """Select salient source sentences deterministically; this is not fact-checking."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    if not sentences:
        return text[:4000]
    words = [re.findall(r"[A-Za-z0-9_+-]{3,}", sentence.casefold()) for sentence in sentences]
    frequencies = {}
    for tokens in words:
        for token in set(tokens):
            frequencies[token] = frequencies.get(token, 0) + 1
    ranked = []
    for index, tokens in enumerate(words):
        if not tokens:
            continue
        score = sum(1 + (frequencies[token] - 1) * 0.5 for token in set(tokens)) / (len(tokens) ** 0.5)
        ranked.append((score, index))
    selected = sorted(index for _, index in sorted(ranked, reverse=True)[:max_sentences])
    summary = " ".join(sentences[index] for index in selected)
    return summary[:6000] or text[:4000]

def update_from_url(topic, url, brain_file="research_live.md", timeout=DEFAULT_TIMEOUT):
    topic_hash = hashlib.sha256(topic.encode("utf-8", errors="replace")).hexdigest()[:12] if isinstance(topic, str) else "invalid"
    try:
        if os.getenv("ALLOW_LIVE_FETCH", "false").strip().lower() not in {"1", "true", "yes", "on"}:
            raise PermissionError("Live retrieval is disabled. Set ALLOW_LIVE_FETCH=true in the backend environment.")
        topic = _validate_text(topic, "topic", 160)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 2 <= timeout <= 30:
            raise ValueError("timeout must be an integer between 2 and 30 seconds")
        safe_url = _validate_public_url(url)
        content_type, body, final_url = _download_source(safe_url, timeout)
        if content_type == "text/html":
            parser = _TextExtractor()
            parser.feed(body)
            title = " ".join(parser.title_parts).strip()[:300]
            extracted = " ".join(" ".join(parser.parts).split())
        elif content_type == "application/json":
            parsed = json.loads(body)
            title = "JSON source"
            extracted = json.dumps(parsed, ensure_ascii=False, indent=2)
        else:
            title = ""
            extracted = body.strip()
        extracted = _validate_text(extracted, "source text", MAX_EXTRACTED_CHARS)
        summary_text = _extractive_summary(extracted)
        summary = (
            "Retrieval verification: HTTPS source, public DNS destination, successful HTTP response, and supported text content type. "
            "This transport validation does not independently fact-check the source.\n\n"
            + (f"Source title: {title}\n\n" if title else "")
            + "Extractive summary:\n" + summary_text
        )
        result = update_topic(topic, summary, brain_file=brain_file, source_url=final_url)
        result.update({"retrieved_at": _now(), "content_type": content_type, "characters_saved": len(summary), "source_characters": len(extracted)})
        _record("brain_online_update", {"topic": topic, "brain_file": brain_file, "source_host": urlsplit(final_url).hostname, "content_type": content_type, "characters_saved": len(summary), "sha256": result["sha256"]})
        return result
    except Exception as exc:
        _record("brain_online_update", {"topic_sha256": topic_hash, "error_type": type(exc).__name__, "error": str(exc)[:400]}, "error")
        raise
