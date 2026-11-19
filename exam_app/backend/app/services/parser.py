import re
import base64
import time
from app.services.llm import chat_json, is_configured, LLMError
from app.schemas import ParsedExam, ParsedQuestion, ParsedOption


PARSE_SYSTEM = """You are an exam question extraction assistant. You receive raw text extracted from a PDF that may contain questions, options, answer keys, explanations, or marking schemes.

Your job: extract the questions into structured JSON. Rules:
- Do NOT invent questions, options, answers, or explanations that are not present.
- Preserve page references when available (source_page).
- If an answer key is present, include it; otherwise set answer_key to null.
- If unsure, lower confidence and add a warning.
- Return ONLY a JSON object matching this schema:
{
  "title": string or null,
  "instructions": string or null,
  "questions": [
    {
      "qtype": "single_choice" | "multiple_select" | "numeric",
      "prompt": string,
      "options": [{"id": "A", "text": "..."}],
      "answer_key": string | list | number | null,
      "explanation": string or null,
      "points": number or null,
      "negative_points": number or null,
      "tolerance": number or null,
      "topic_tags": [string],  # 1-3 specific subtopics (e.g. "Eigenvalues", "Eigenvectors")
      "section": string or null,  # only if the PDF explicitly shows section headings
      "source_page": number or null,
      "confidence": number (0-1),
      "warnings": [string]
    }
  ],
  "warnings": [string]
}
- For numeric answers, answer_key is a number and tolerance a number (default 0.01 if not specified).
- For multiple_select, answer_key is a list of option ids.
- Do NOT include any other text.
"""


def parse_with_llm(text: str) -> ParsedExam:
    if not is_configured():
        raise LLMError("LLM not configured")
    trimmed = text[: settings_max_input()]
    messages = [
        {"role": "system", "content": PARSE_SYSTEM},
        {"role": "user", "content": f"Extract questions from this PDF text:\n\n{trimmed}"},
    ]
    from app.config import settings
    data = chat_json(messages, max_tokens=settings.LLM_MAX_OUTPUT_TOKENS)
    return ParsedExam.model_validate(data)


def settings_max_input() -> int:
    from app.config import settings
    return settings.LLM_MAX_INPUT_CHARS


def _is_header_line(line: str) -> bool:
    l = line.strip().lower()
    if not l:
        return True
    if l.startswith("--- page") or l.startswith("---page"):
        return True
    if "android app" in l or "ios app" in l or "pw website" in l:
        return True
    if "penpencil" in l or "finalize-question" in l:
        return True
    if l == "gate" or l.startswith("gate_dpp") or l.startswith("gate dpp"):
        return True
    if re.match(r"^\d+/\d+$", l):
        return True
    if re.match(r"^\d+/\d+,\d+:\d+\s*(am|pm)$", l):
        return True
    if "3/14/24" in l:
        return True
    if "engineering mathematics" in l or "data science and ai" in l:
        return True
    if "linear algebra" in l and len(l) < 40:
        return True
    if "dpp 03" in l and len(l) < 20:
        return True
    return False


def _parse_answers(text: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    m = re.search(r"(?is)answer\s*key\b(.*?)(?:hints\s*&\s*solutions|text\s*solution|\Z)", text)
    section = m.group(1) if m else ""
    for raw in section.splitlines():
        line = raw.strip()
        if not line or _is_header_line(line):
            continue
        qnums = [int(x) for x in re.findall(r"Q\s*(\d+)", line, re.I)]
        if not qnums:
            continue
        val = re.sub(r"Q\s*\d+", "", line, flags=re.I).strip()
        m_letter = re.fullmatch(r"\(?([A-Da-d])\)?", val)
        if m_letter:
            for num in qnums:
                answers[num] = m_letter.group(1).upper()
            continue
        if val:
            converted = val
            m3 = re.search(r"-?\d+(?:\.\d+)?", val)
            if m3 and len(val) <= 20 and not any(c.isalpha() for c in val.replace("(", "").replace(")", "")):
                try:
                    converted = float(m3.group(0)) if "." in m3.group(0) else int(m3.group(0))
                except ValueError:
                    converted = val
            for num in qnums:
                answers[num] = converted
    return answers


def _parse_explanations(text: str) -> dict[int, str]:
    exps: dict[int, str] = {}
    for mm in re.finditer(r"Q\s*(\d+)\s*Text\s*Solution\s*:(.*?)(?=Q\s*\d+\s*Text\s*Solution\s*:|\Z)", text, re.S | re.I):
        num = int(mm.group(1))
        body = mm.group(2)
        lines = [ln for ln in body.splitlines() if not _is_header_line(ln)]
        body = "\n".join(lines).strip()
        if body:
            exps[num] = body
    return exps


def _parse_q_style(text: str) -> ParsedExam | None:
    full_text = text
    cut = len(text)
    for marker in ("answer key", "hints & solutions", "text solution", "hints and solutions"):
        i = text.lower().find(marker)
        if i != -1 and i < cut:
            cut = i
    q_text = text[:cut]

    answers = _parse_answers(full_text)
    exps = _parse_explanations(full_text)

    text2 = re.sub(r"(?<!\n)(Q\s*\d+)", r"\n\1", q_text)

    questions: list[dict] = []
    current = None
    for raw in text2.splitlines():
        line = raw.strip()
        if not line:
            if current is not None:
                current["lines"].append("")
            continue
        if _is_header_line(line):
            continue
        m = re.match(r"^Q\s*(\d+)\s*(.*)$", line, re.I)
        if m:
            if current is not None:
                questions.append(current)
            num = int(m.group(1))
            rest = m.group(2).strip()
            current = {"num": num, "lines": ([rest] if rest else [])}
        else:
            if current is not None:
                current["lines"].append(line)
            elif questions:
                questions[-1]["lines"].append(line)
    if current is not None:
        questions.append(current)

    if not questions:
        return None

    parsed_qs = []
    seen: set[int] = set()
    for q in questions:
        num = q["num"]
        if num in seen:
            continue
        seen.add(num)
        buf = "\n".join(q["lines"])
        markers = list(re.finditer(r"\(([A-D])\)", buf, re.I))
        prompt = buf
        options = []
        if markers:
            prompt = buf[: markers[0].start()].strip()
            for i, mm in enumerate(markers):
                oid = mm.group(1).upper()
                start = mm.end()
                end = markers[i + 1].start() if i + 1 < len(markers) else len(buf)
                opt_text = buf[start:end].strip().lstrip(" ,;:-")
                options.append(ParsedOption(id=oid, text=opt_text or oid))
        prompt = re.sub(r"\s+", " ", prompt).strip()
        if not prompt:
            prompt = f"Question {num}"

        ak = answers.get(num)
        if isinstance(ak, str):
            m2 = re.match(r"\(?([A-Da-d])\)?", ak, re.I)
            if m2 and options:
                ak = m2.group(1).upper()
            else:
                m3 = re.search(r"-?\d+(?:\.\d+)?", ak)
                if m3 and not options:
                    try:
                        ak = float(m3.group(0)) if "." in m3.group(0) else int(m3.group(0))
                    except ValueError:
                        pass

        qtype = "single_choice"
        tolerance = None
        if not options and isinstance(ak, (int, float)):
            qtype = "numeric"
            tolerance = 0.01

        parsed_qs.append(
            ParsedQuestion(
                qtype=qtype,
                prompt=prompt,
                options=options,
                answer_key=ak,
                explanation=exps.get(num),
                points=None,
                negative_points=None,
                tolerance=tolerance,
                topic_tags=[],
                source_page=None,
                confidence=0.5,
                warnings=["Parsed from scanned PDF via local OCR; review carefully."],
            )
        )

    if not parsed_qs:
        return None

    title = "Untitled Exam"
    for line in text.splitlines():
        if "DPP" in line.upper():
            t = line.strip()
            if 0 < len(t) < 60:
                title = t
                break

    return ParsedExam(title=title, instructions=None, questions=parsed_qs, warnings=[])


def extract_answer_key(text: str) -> dict[int, str]:
    """Extract answer key from ExamGOAL-style PDFs.
    Format: '1. A', '2. B, C', '3. 95', '4. 4.24 to 4.26'
    """
    ak = {}
    # Find the answer key section
    ak_start = text.find("Answer Key")
    if ak_start == -1:
        return ak
    ak_text = text[ak_start:]
    for line in ak_text.split('\n'):
        m = re.match(r'^\s*(\d+)\.\s*(.+)$', line.strip())
        if m:
            qnum = int(m.group(1))
            ans = m.group(2).strip()
            if 1 <= qnum <= 200 and ans:
                ak[qnum] = ans
    return ak


def strip_answer_key_section(text: str) -> str:
    """Remove the answer key section from the text."""
    ak_start = text.find("Answer Key")
    if ak_start == -1:
        return text
    # Find the start of the answer key section (look for "Answer Key" heading)
    # Keep everything before it
    return text[:ak_start]
    exam = _parse_q_style(text)
    if exam is not None:
        return exam
    warnings = ["LLM not configured; used heuristic parser. Review carefully."]
    questions = []
    lines = text.splitlines()
    current = None
    for line in lines:
        m = re.match(r"^\s*(?:Q\.?\s*)?(\d+)[\.\)]\s*(.+)", line)
        if m:
            if current:
                questions.append(current)
            current = {"prompt": m.group(2).strip(), "page": None}
        else:
            if current is not None and line.strip():
                current["prompt"] += " " + line.strip()
    if current:
        questions.append(current)

    parsed_qs = []
    for idx, q in enumerate(questions):
        parsed_qs.append(ParsedQuestion(
            qtype="single_choice",
            prompt=q["prompt"],
            options=[],
            answer_key=None,
            confidence=0.3,
            warnings=["Heuristic parse: options/answers not extracted; please edit."],
        ))
    if not parsed_qs:
        warnings.append("No questions detected heuristically.")
    return ParsedExam(title=None, instructions=None, questions=parsed_qs, warnings=warnings)



def heuristic_parse(text: str) -> ParsedExam:
    exam = _parse_q_style(text)
    if exam is not None:
        return exam
    warnings = ["LLM not configured; used heuristic parser. Review carefully."]
    questions = []
    lines = text.splitlines()
    current = None
    for line in lines:
        m = re.match(r"^\s*(?:Q\.?\s*)?(\d+)[\.\)]\s*(.+)", line)
        if m:
            if current:
                questions.append(current)
            current = {"prompt": m.group(2).strip(), "page": None}
        else:
            if current is not None and line.strip():
                current["prompt"] += " " + line.strip()
    if current:
        questions.append(current)

    parsed_qs = []
    for idx, q in enumerate(questions):
        parsed_qs.append(ParsedQuestion(
            qtype="single_choice",
            prompt=q["prompt"],
            options=[],
            answer_key=None,
            confidence=0.3,
            warnings=["Heuristic parse: options/answers not extracted; please edit."],
        ))
    if not parsed_qs:
        warnings.append("No questions detected heuristically.")
    return ParsedExam(title=None, instructions=None, questions=parsed_qs, warnings=warnings)


def parse_text(text: str) -> tuple[ParsedExam, list[str]]:
    warnings: list[str] = []
    # Extract answer key before stripping
    ak = extract_answer_key(text)
    # Strip answer key section from text to avoid parsing it as questions
    clean_text = strip_answer_key_section(text)
    try:
        if is_configured():
            exam = parse_with_llm(clean_text)
            # Apply answer keys
            if ak:
                _apply_answer_keys(exam, ak)
            return exam, warnings
    except Exception as e:
        warnings.append(f"LLM parse failed: {e}; falling back to heuristic.")
    exam = heuristic_parse(clean_text)
    if ak:
        _apply_answer_keys(exam, ak)
    exam.warnings = (exam.warnings or []) + warnings
    return exam, warnings


def _apply_answer_keys(exam: ParsedExam, ak: dict[int, str]) -> None:
    """Apply extracted answer keys to parsed questions by index."""
    for i, q in enumerate(exam.questions):
        qnum = i + 1
        if qnum in ak:
            ans = ak[qnum]
            if ',' in ans and not ans.replace(',', '').replace(' ', '').isdigit():
                q.answer_key = [a.strip() for a in ans.split(',')]
                q.qtype = "multiple_select"
            elif ans.strip('()').replace('.', '').replace(' ', '').isdigit() or '-' in ans and ans.replace('-', '').replace('.', '').isdigit():
                clean = ans.strip('()').strip()
                try:
                    q.answer_key = float(clean)
                    q.qtype = "numeric"
                except ValueError:
                    q.answer_key = clean
            else:
                q.answer_key = ans.strip()
                if q.qtype not in ("multiple_select", "numeric"):
                    q.qtype = "single_choice"


VISION_PARSE_SYSTEM = """You are an exam question extraction assistant. You receive images of pages from a PDF exam paper. Extract every question into structured JSON.

Rules:
- Do NOT invent questions, options, answers, or explanations.
- Only extract questions that are explicitly numbered (Q1, Q2, ...). Do not create questions from solution or hint text.
- For every question, extract ALL options (A, B, C, D, ...) if present. Never omit options.
- Read equations, matrices, fractions, and multi-column layouts carefully.
- Use LaTeX for math in prompts, options, and explanations (inline $...$, block $$...$$).
- Set topic_tags to 1-3 specific subtopics (e.g. "Eigenvalues", "Eigenvectors", "Matrices") for analysis.
- Set section only if the PDF explicitly shows section headings; otherwise null.
- Set answer_key only if an answer key is visible; otherwise null.
- Return valid JSON: escape every backslash in LaTeX as \\\\ (for example write \\\\begin{bmatrix} not \\begin{bmatrix}).
- If an answer key or solutions are visible, include answer_key and explanation for that question.
- Return ONLY a JSON object:
{
  "title": string or null,
  "instructions": string or null,
  "questions": [
    {
      "number": integer or null,
      "qtype": "single_choice" | "multiple_select" | "numeric",
      "prompt": string,
      "options": [{"id": "A", "text": "..."}],
      "answer_key": string | list | number | null,
      "explanation": string or null,
      "points": number or null,
      "negative_points": number or null,
      "tolerance": number or null,
      "topic_tags": [string],  # specific subtopics for analysis
      "section": string or null,  # only if the PDF explicitly shows section headings
      "confidence": number (0-1),
      "warnings": [string]
    }
  ],
  "warnings": [string]
}
- For numeric answers, answer_key is a number and tolerance a number (default 0.01).
- For multiple_select, answer_key is a list of option ids.
"""


def _render_page_images(pdf_path: str, max_width: int = 600) -> list[str]:
    try:
        import fitz
    except Exception as e:
        raise RuntimeError(f"PyMuPDF unavailable: {e}")
    doc = fitz.open(pdf_path)
    images: list[str] = []
    try:
        for page in doc:
            scale = max_width / max(page.rect.width, 1)
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)
            data = pix.tobytes("jpeg")
            images.append("data:image/jpeg;base64," + base64.b64encode(data).decode("ascii"))
    finally:
        doc.close()
    return images


def _render_page(pdf_path: str, page_index: int, max_width: int = 600,
                 clip_ratio: tuple[float, float] | None = None) -> str:
    """Render one page (optionally a vertical slice) as a data URL."""
    import fitz
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        rect = page.rect
        clip = None
        if clip_ratio is not None:
            y0, y1 = clip_ratio
            clip = fitz.Rect(rect.x0, rect.y0 + rect.height * y0,
                             rect.x1, rect.y0 + rect.height * y1)
        scale = max_width / max(rect.width, 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip)
        return "data:image/jpeg;base64," + base64.b64encode(pix.tobytes("jpeg")).decode("ascii")
    finally:
        doc.close()


def _vision_parse_images(images: list[str], prompt: str = "Extract all questions from these pages. Return JSON only.") -> dict:
    from app.config import settings
    content: list[dict] = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": img}})
    messages = [
        {"role": "system", "content": VISION_PARSE_SYSTEM},
        {"role": "user", "content": content},
    ]
    return chat_json(messages, max_tokens=min(settings.LLM_MAX_OUTPUT_TOKENS, 8192), timeout=300)


def _text_parse_page(page_text: str) -> dict:
    from app.config import settings
    prompt = (
        "The following is the text layer of one page of a GATE exam paper. "
        "Extract every question on the page and return JSON only. Rebuild LaTeX "
        "($...$) for symbols and formulas that are identifiable from the text.\n\n"
        + page_text
    )
    messages = [
        {"role": "system", "content": VISION_PARSE_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    return chat_json(messages, max_tokens=min(settings.LLM_MAX_OUTPUT_TOKENS, 8192), timeout=180)


def _is_recitation_error(err: Exception) -> bool:
    text = str(err).upper()
    return "RECITATION" in text or "EMPTY LLM RESPONSE" in text


def _question_key(q: dict) -> str:
    num = q.get("number")
    if num is not None:
        return f"n:{num}"
    prompt = re.sub(r"\s+", " ", str(q.get("prompt") or "")).strip().lower()
    return "p:" + prompt[:120]


def _dedupe_questions(questions: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for q in questions:
        key = _question_key(q)
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def _clean_prompt(prompt: str) -> str:
    prompt = (prompt or "").strip()
    prompt = re.sub(r'^\.?\s*MCQ\s*\([^)]*\)\s*', '', prompt)
    prompt = re.sub(r'^\.?\s*NAT\s*', '', prompt)
    prompt = re.sub(r'^\.?\s*MSQ\s*\([^)]*\)\s*', '', prompt)
    return prompt.strip()


def _apply_answer_key(q: dict, ans: str) -> None:
    ans = (ans or "").strip()
    if not ans:
        return
    m = re.match(r"^([-−]?[\d.]+)\s*(?:to|–|-)\s*([-−]?[\d.]+)$", ans)
    if m:
        lo = float(m.group(1).replace("−", "-"))
        hi = float(m.group(2).replace("−", "-"))
        q["answer_key"] = round((lo + hi) / 2, 6)
        q["tolerance"] = round(abs(hi - lo) / 2, 6)
        q["qtype"] = "numeric"
        return
    if "," in ans and not ans.replace(",", "").replace(" ", "").isdigit():
        q["answer_key"] = [a.strip() for a in ans.split(",") if a.strip()]
        q["qtype"] = "multiple_select"
        return
    if re.fullmatch(r"[A-D]", ans):
        q["answer_key"] = ans
        if q.get("qtype") not in ("multiple_select", "numeric"):
            q["qtype"] = "single_choice"
        return
    clean = ans.strip("()").strip().replace("−", "-")
    try:
        value = float(clean)
        q["answer_key"] = value
        q["qtype"] = "numeric"
        q["tolerance"] = 0.01 if "." in clean else 0.0
    except ValueError:
        q["answer_key"] = ans


def _extract_page(pdf_path: str, page_index: int, page_text: str) -> tuple[list[dict], list[str], dict]:
    """Parse one page: full image, then halves, then text layer."""
    warnings: list[str] = []
    try:
        data = _vision_parse_images([_render_page(pdf_path, page_index)])
        qs = data.get("questions") or []
        for q in qs:
            q.setdefault("source_page", page_index + 1)
        if qs:
            return qs, warnings, {"title": data.get("title"), "instructions": data.get("instructions")}
    except Exception as e:
        warnings.append(f"page {page_index + 1}: vision failed: {str(e)[:160]}")
        if not _is_recitation_error(e):
            # Try the text layer before giving up on this page.
            pass

    # Recitation filter or empty output: parse the two halves separately.
    try:
        top = _vision_parse_images(
            [_render_page(pdf_path, page_index, clip_ratio=(0.04, 0.56))],
            prompt="Extract all questions visible in this part of the page. Return JSON only.",
        )
        bottom = _vision_parse_images(
            [_render_page(pdf_path, page_index, clip_ratio=(0.44, 0.98))],
            prompt="Extract all questions visible in this part of the page. Return JSON only.",
        )
        qs = _dedupe_questions((top.get("questions") or []) + (bottom.get("questions") or []))
        for q in qs:
            q.setdefault("source_page", page_index + 1)
        if qs:
            return qs, warnings, {"title": top.get("title") or bottom.get("title"),
                                  "instructions": top.get("instructions") or bottom.get("instructions")}
    except Exception as e:
        warnings.append(f"page {page_index + 1}: split vision failed: {str(e)[:160]}")

    if page_text.strip():
        try:
            data = _text_parse_page(page_text)
            qs = data.get("questions") or []
            for q in qs:
                q.setdefault("source_page", page_index + 1)
            if qs:
                return qs, warnings, {"title": data.get("title"), "instructions": data.get("instructions")}
        except Exception as e:
            warnings.append(f"page {page_index + 1}: text fallback failed: {str(e)[:160]}")

    warnings.append(f"page {page_index + 1}: no questions extracted")
    return [], warnings, {}


def parse_pdf_with_vision(pdf_path: str, workers: int = 1, batch_size: int = 5) -> ParsedExam:
    if not is_configured():
        raise LLMError("LLM not configured")
    import fitz
    # Detect answer key page and extract answer keys
    ak: dict[int, str] = {}
    ak_page_idx = None
    page_texts: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for i in range(len(doc)):
            page_text = doc[i].get_text()
            page_texts.append(page_text)
            if ak_page_idx is None and "Answer Key" in page_text and re.search(r'^\s*1\.\s*[A-D]', page_text, re.M):
                ak_page_idx = i
                ak = extract_answer_key(page_text)
    finally:
        doc.close()

    page_indexes = [i for i in range(len(page_texts)) if i != ak_page_idx]
    if not page_indexes:
        raise LLMError("No pages to parse")

    chunks = [page_indexes[i:i + batch_size] for i in range(0, len(page_indexes), batch_size)]
    all_questions: list[dict] = []
    warnings: list[str] = []
    title = None
    instructions = None

    def parse_chunk(chunk: list[int]) -> tuple[list[dict], list[str], dict]:
        try:
            images = [_render_page(pdf_path, i) for i in chunk]
            data = _vision_parse_images(images)
            qs = data.get("questions") or []
            if not qs:
                raise LLMError("Empty chunk response")
            return qs, [], {"title": data.get("title"), "instructions": data.get("instructions")}
        except Exception as e:
            # Chunk failed (recitation filter, overload, truncation). Retry page by page.
            warnings_local = [f"pages {chunk[0] + 1}-{chunk[-1] + 1}: chunk failed: {str(e)[:140]}"]
            qs_all: list[dict] = []
            meta: dict = {}
            for idx in chunk:
                qs, ws, page_meta = _extract_page(pdf_path, idx, page_texts[idx])
                qs_all.extend(qs)
                warnings_local.extend(ws)
                if not meta:
                    meta = page_meta
            return qs_all, warnings_local, meta

    if workers and workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(parse_chunk, chunks))
    else:
        results = [parse_chunk(c) for c in chunks]

    for qs, ws, meta in results:
        all_questions.extend(qs)
        warnings.extend(ws)
        if title is None and meta.get("title"):
            title = meta["title"]
        if instructions is None and meta.get("instructions"):
            instructions = meta["instructions"]

    for q in all_questions:
        if isinstance(q.get("prompt"), str):
            q["prompt"] = _clean_prompt(q["prompt"])

    # Apply answer keys by question order
    if ak:
        for i, q in enumerate(all_questions):
            if i + 1 in ak:
                _apply_answer_key(q, ak[i + 1])

    questions = [ParsedQuestion.model_validate(q) for q in all_questions]
    return ParsedExam(title=title, instructions=instructions, questions=questions, warnings=warnings)
