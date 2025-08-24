import base64
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import streamlit as st
from jinja2 import Template
from pydantic import BaseModel, Field, ValidationError

APP_DIR = Path(__file__).parent
VERSIONS_DIR = APP_DIR / "versions"
VERSIONS_DIR.mkdir(exist_ok=True)

class Experience(BaseModel):
    company: str = Field(..., description="Company name")
    role: str = Field(..., description="Job title")
    start: str = Field(..., description="Start date (e.g., Jan 2023)")
    end: str = Field(..., description="End date or 'Present'")
    bullets: List[str] = Field(default_factory=list, description="Achievements")

class Education(BaseModel):
    institution: str
    degree: str
    start: str
    end: str
    details: Optional[List[str]] = Field(default_factory=list)

class ResumeData(BaseModel):
    name: str = "Ada Lovelace"
    email: str = "ada@example.com"
    phone: str = "+1 (555) 123-4567"
    location: str = "Los Angeles, CA"
    website: Optional[str] = "https://adalovelace.dev"
    summary: str = (
        "Computing pioneer with a passion for elegant algorithms and practical impact."
    )
    skills: List[str] = Field(
        default_factory=lambda: [
            "Python",
            "C++",
            "Machine Learning",
            "Data Visualization",
            "Distributed Systems",
        ]
    )
    experience: List[Experience] = Field(
        default_factory=lambda: [
            Experience(
                company="Analytical Engine Labs",
                role="Software Engineer",
                start="Jan 2023",
                end="Present",
                bullets=[
                    "Designed data pipelines processing 10M+ events/day.",
                    "Led migration to typed APIs, reducing defects by 30%.",
                ],
            ),
            Experience(
                company="Math & Poetry Co.",
                role="Research Fellow",
                start="Sep 2021",
                end="Dec 2022",
                bullets=[
                    "Prototyped Bayesian models for sequence prediction.",
                    "Published 2 papers; presented at NeurIPS workshop.",
                ],
            ),
        ]
    )
    education: List[Education] = Field(
        default_factory=lambda: [
            Education(
                institution="USC",
                degree="M.S. Computer Science",
                start="2023",
                end="2025",
                details=["GPA: 3.9/4.0", "Coursework: ML, Systems, NLP"],
            ),
            Education(
                institution="Caltech",
                degree="B.S. Mathematics",
                start="2019",
                end="2023",
                details=["Honors in Pure Math", "Minor in CS"],
            ),
        ]
    )


DEFAULT_TEX = r"""
% !TEX program = xelatex
\documentclass[11pt]{article}
\usepackage[margin=0.8in]{geometry}
\usepackage{parskip}
\usepackage{enumitem}
\setlist[itemize]{noitemsep, topsep=0pt}
\usepackage[hidelinks]{hyperref}
\usepackage{titlesec}
\titleformat{\section}{\large\bfseries}{}{0em}{}
\titlespacing*{\section}{0pt}{6pt}{3pt}
\pagenumbering{gobble}

\newcommand{\sep}{\,\textbullet\,}

\begin{document}

{\LARGE {{ data.name }}}\\
\vspace{2pt}
{{ data.email }}\sep {{ data.phone }}\sep {{ data.location }}{% if data.website %}\sep \href{ {{ data.website }} }{ {{ data.website }} }{% endif %}

\vspace{8pt}
\section*{Summary}
{{ data.summary }}

\section*{Skills}
{\normalsize
{% for s in data.skills %}{{ s }}{% if not loop.last %}, {% endif %}{% endfor %}
}

\section*{Experience}
{% for e in data.experience %}
\textbf{ {{ e.role }} } -- {{ e.company }} \hfill { { e.start } -- { { e.end } } }\\
\begin{itemize}
  {% for b in e.bullets %}\item {{ b }}{% endfor %}
\end{itemize}
{% endfor %}

\section*{Education}
{% for ed in data.education %}
\textbf{ {{ ed.degree }} } -- {{ ed.institution }} \hfill { { ed.start } -- { { ed.end } } }\\
{% if ed.details %}
\begin{itemize}
  {% for d in ed.details %}\item {{ d }}{% endfor %}
\end{itemize}
{% endif %}
{% endfor %}

\end{document}
"""

# -----------------------------
# Helpers
# -----------------------------

def render_template_tex(data: ResumeData, template_text: str) -> str:
    template = Template(template_text)
    return template.render(data=json.loads(data.model_dump_json()))


def compile_tex_to_pdf(tex_source: str) -> tuple[Optional[bytes], str]:
    """Compile LaTeX to PDF, return (pdf_bytes, log_text)."""
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        tex_file = temp_dir / "main.tex"
        tex_file.write_text(tex_source, encoding="utf-8")

        # Prefer latexmk if available, else fall back to xelatex, then pdflatex
        engines = [
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
        ]
        used = None
        for cmd in engines:
            if shutil.which(cmd[0]):
                used = cmd
                break
        if not used:
            return None, (
                "No TeX engine found. Please install latexmk or xelatex/pdflatex and ensure it's on PATH."
            )

        try:
            proc = subprocess.run(
                used,
                cwd=temp_dir,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            log = proc.stdout
            pdf_path = temp_dir / "main.pdf"
            if proc.returncode == 0 and pdf_path.exists():
                return pdf_path.read_bytes(), log
            else:
                return None, log
        except Exception as e:
            return None, f"Compilation error: {e}"


def pdf_bytes_to_data_uri(pdf_bytes: bytes) -> str:
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return f"data:application/pdf;base64,{b64}"


def save_version(pdf_bytes: bytes, version_tag: str | None) -> Path:
    uid = str(uuid4())
    if version_tag:
        safe_tag = "".join(c for c in version_tag if c.isalnum() or c in ("-", "_"))
        filename = f"resume_{safe_tag}_{uid}.pdf"
    else:
        filename = f"resume_{uid}.pdf"
    out_path = VERSIONS_DIR / filename
    out_path.write_bytes(pdf_bytes)
    # Also save a small metadata JSON alongside
    meta = {
        "filename": filename,
        "created": datetime.now().isoformat(timespec="seconds"),
        "size_bytes": len(pdf_bytes),
    }
    (VERSIONS_DIR / f"{filename}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out_path


def list_versions() -> List[dict]:
    items = []
    if not VERSIONS_DIR.exists():
        return items
    for p in sorted(VERSIONS_DIR.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
        meta_path = VERSIONS_DIR / f"{p.name}.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        else:
            meta = {
                "filename": p.name,
                "created": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                "size_bytes": p.stat().st_size,
            }
        items.append(meta)
    return items

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Resume Viewer & Editor", page_icon="📄", layout="wide")

st.title("📄 Resume Viewer & Editor (LaTeX → PDF)")
st.caption("Edit via form or raw LaTeX. Compile and download PDFs with UUID-based names.")

with st.sidebar:
    st.header("Mode")
    mode = st.radio("Edit mode", options=["Form", "Raw LaTeX"], index=0, help="Choose to edit structured fields or directly edit LaTeX.")

    st.header("Versioning")
    version_tag = st.text_input("Optional version tag", placeholder="e.g., internship-2026")

    st.divider()
    st.header("Actions")
    compile_btn = st.button("⚙️ Compile → PDF", type="primary")

# State: template and data JSON
if "template_text" not in st.session_state:
    st.session_state["template_text"] = DEFAULT_TEX
if "data_json" not in st.session_state:
    st.session_state["data_json"] = ResumeData().model_dump_json(indent=2)

col_left, col_right = st.columns([1, 1])

with col_left:
    if mode == "Form":
        st.subheader("Resume Fields")
        # Load current JSON -> model for validation, then display widgets
        try:
            model = ResumeData(**json.loads(st.session_state["data_json"]))
        except Exception:
            # Reset if corrupted
            model = ResumeData()
            st.session_state["data_json"] = model.model_dump_json(indent=2)

        # Basic fields
        name = st.text_input("Full Name", value=model.name)
        email = st.text_input("Email", value=model.email)
        phone = st.text_input("Phone", value=model.phone)
        location = st.text_input("Location", value=model.location)
        website = st.text_input("Website (optional)", value=model.website or "")
        summary = st.text_area("Summary", value=model.summary, height=100)

        skills_str = st.text_area("Skills (comma-separated)", value=", ".join(model.skills), height=80)
        skills = [s.strip() for s in skills_str.split(",") if s.strip()]

        st.markdown("### Experience")
        exp_blocks: List[Experience] = []
        for i, e in enumerate(model.experience):
            with st.expander(f"Experience #{i+1}: {e.role} @ {e.company}", expanded=False):
                company = st.text_input(f"Company #{i+1}", value=e.company, key=f"exp_company_{i}")
                role = st.text_input(f"Role #{i+1}", value=e.role, key=f"exp_role_{i}")
                start = st.text_input(f"Start #{i+1}", value=e.start, key=f"exp_start_{i}")
                end = st.text_input(f"End #{i+1}", value=e.end, key=f"exp_end_{i}")
                bullets_str = st.text_area(
                    f"Bullets #{i+1} (one per line)", value="\n".join(e.bullets), key=f"exp_bullets_{i}", height=120
                )
                bullets = [b.strip() for b in bullets_str.splitlines() if b.strip()]
                exp_blocks.append(
                    Experience(company=company, role=role, start=start, end=end, bullets=bullets)
                )
        if st.button("➕ Add Experience"):
            model.experience.append(
                Experience(company="New Company", role="Title", start="", end="", bullets=["Achievement 1"])
            )
            st.session_state["data_json"] = model.model_dump_json(indent=2)
            st.rerun()

        st.markdown("### Education")
        edu_blocks: List[Education] = []
        for i, ed in enumerate(model.education):
            with st.expander(f"Education #{i+1}: {ed.degree} @ {ed.institution}", expanded=False):
                institution = st.text_input(f"Institution #{i+1}", value=ed.institution, key=f"edu_inst_{i}")
                degree = st.text_input(f"Degree #{i+1}", value=ed.degree, key=f"edu_degree_{i}")
                start = st.text_input(f"Start #{i+1}", value=ed.start, key=f"edu_start_{i}")
                end = st.text_input(f"End #{i+1}", value=ed.end, key=f"edu_end_{i}")
                details_str = st.text_area(
                    f"Details #{i+1} (one per line)", value="\n".join(ed.details or []), key=f"edu_details_{i}", height=100
                )
                details = [d.strip() for d in details_str.splitlines() if d.strip()]
                edu_blocks.append(
                    Education(institution=institution, degree=degree, start=start, end=end, details=details)
                )
        if st.button("➕ Add Education"):
            model.education.append(
                Education(institution="New University", degree="Degree", start="", end="", details=["Detail 1"])
            )
            st.session_state["data_json"] = model.model_dump_json(indent=2)
            st.rerun()

        # Save back to JSON state
        updated = ResumeData(
            name=name,
            email=email,
            phone=phone,
            location=location,
            website=website or None,
            summary=summary,
            skills=skills,
            experience=exp_blocks or model.experience,
            education=edu_blocks or model.education,
        )
        st.session_state["data_json"] = updated.model_dump_json(indent=2)

        st.divider()
        st.subheader("Raw JSON (advanced)")
        st.code(st.session_state["data_json"], language="json")

    else:
        st.subheader("Raw LaTeX Template (Jinja2)")
        template_text = st.text_area(
            "Edit LaTeX template",
            value=st.session_state["template_text"],
            height=600,
        )
        st.session_state["template_text"] = template_text
        st.markdown("Tip: Data is available as `data` in the template. Example: `{{ data.name }}`.")
        st.divider()
        st.subheader("Resume Data (JSON)")
        text = st.text_area("Edit JSON", value=st.session_state["data_json"], height=300)
        st.session_state["data_json"] = text

with col_right:
    st.subheader("Preview & Download")

    # Build LaTeX from current state
    try:
        parsed = ResumeData(**json.loads(st.session_state["data_json"]))
        validation_error = None
    except ValidationError as ve:
        parsed = None
        validation_error = ve

    if validation_error:
        st.error("Data validation error. Fix your JSON fields.")
        st.code(str(validation_error), language="text")
    else:
        tex_source = render_template_tex(parsed, st.session_state["template_text"])
        with st.expander("View generated LaTeX", expanded=False):
            st.code(tex_source, language="latex")

        # Compile on demand OR auto-compile when switching
        should_compile = compile_btn or st.session_state.get("_auto_compile_once") is None
        if should_compile:
            pdf_bytes, log = compile_tex_to_pdf(tex_source)
            st.session_state["_auto_compile_once"] = True
            st.session_state["_last_pdf"] = pdf_bytes
            st.session_state["_last_log"] = log
        else:
            pdf_bytes = st.session_state.get("_last_pdf")
            log = st.session_state.get("_last_log")

        if pdf_bytes:
            data_uri = pdf_bytes_to_data_uri(pdf_bytes)
            st.components.v1.html(
                f"""
                <div style='height:800px;border:1px solid #ddd;'>
                  <embed src='{data_uri}' type='application/pdf' width='100%' height='100%'/>
                </div>
                """,
                height=820,
            )

            # Save version and offer download
            if st.button("💾 Save Version (UUID filename)"):
                out_path = save_version(pdf_bytes, version_tag)
                st.success(f"Saved: {out_path.name}")

            # Always offer a direct download as well
            suggested_name = (
                f"resume_{version_tag}_{uuid4()}.pdf" if version_tag else f"resume_{uuid4()}.pdf"
            )
            st.download_button(
                label="⬇️ Download PDF (UUID)",
                data=pdf_bytes,
                file_name=suggested_name,
                mime="application/pdf",
            )
        else:
            st.warning("No PDF yet. Click 'Compile → PDF' to build. If it fails, check the log below.")

        with st.expander("Compiler Log"):
            st.code(st.session_state.get("_last_log") or "<no log>", language="text")

    st.divider()
    st.subheader("Previous Versions")
    versions = list_versions()
    if versions:
        for v in versions[:25]:  # show recent 25
            p = VERSIONS_DIR / v["filename"]
            size_kb = v["size_bytes"] // 1024
            colA, colB, colC = st.columns([3, 2, 2])
            colA.write(v["filename"])
            colB.write(v["created"])
            with open(p, "rb") as fh:
                colC.download_button("Download", data=fh.read(), file_name=v["filename"], mime="application/pdf")
    else:
        st.info("No saved versions yet.")

st.divider()
st.caption("Pro tip: Customize the LaTeX template for your preferred look (fonts, spacing, sections).")
