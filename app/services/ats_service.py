"""ATS Intelligence and Document Parsing Service.

Handles resume text extraction, Gemini AI evaluation, and local fallback analysis.
"""

import io
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Common skill catalog used for local fallback extraction
SKILL_CATALOG = {
    # Programming Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "golang", "go",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "html", "css",
    "bash", "shell",
    # Frameworks & Libraries
    "react", "angular", "vue", "next.js", "node.js", "django", "flask", "fastapi",
    "spring boot", "express", "asp.net", "tailwind", "bootstrap", "redux",
    # Data Science & AI/ML
    "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
    "pandas", "numpy", "natural language processing", "nlp", "computer vision",
    "large language models", "llm", "generative ai", "langchain", "rag",
    "data analysis", "power bi", "tableau", "spark", "hadoop",
    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "ci/cd",
    "jenkins", "github actions", "terraform", "ansible", "linux", "git",
    "microservices", "rest api", "graphql",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "sqlite", "dynamodb",
    "elasticsearch", "cassandra", "oracle",
    # Software Engineering & Soft Skills
    "agile", "scrum", "system design", "unit testing", "integration testing",
    "object-oriented programming", "problem solving", "leadership",
    "communication", "cross-functional collaboration", "code review",
}

ROLE_SKILL_BENCHMARKS = {
    "software engineer": [
        "python", "java", "javascript", "sql", "git", "data structures",
        "algorithms", "rest api", "docker", "unit testing", "system design",
    ],
    "frontend": [
        "javascript", "typescript", "react", "html", "css", "vue", "tailwind",
        "next.js", "rest api", "git", "responsive design",
    ],
    "backend": [
        "python", "java", "node.js", "sql", "postgresql", "rest api", "docker",
        "redis", "microservices", "git", "system design",
    ],
    "fullstack": [
        "javascript", "react", "node.js", "python", "sql", "html", "css",
        "docker", "rest api", "git", "postgresql",
    ],
    "data scientist": [
        "python", "machine learning", "pandas", "numpy", "scikit-learn",
        "sql", "data analysis", "deep learning", "statistics", "data visualization",
    ],
    "ai engineer": [
        "python", "machine learning", "deep learning", "pytorch", "tensorflow",
        "llm", "generative ai", "langchain", "rag", "docker", "rest api",
    ],
    "devops": [
        "docker", "kubernetes", "aws", "ci/cd", "terraform", "linux",
        "github actions", "jenkins", "bash", "git", "monitoring",
    ],
    "data analyst": [
        "sql", "python", "power bi", "tableau", "data analysis",
        "excel", "statistics", "data visualization", "pandas",
    ],
}


def extract_text_from_file(file_storage) -> str:
    """Extracts plain text from an uploaded file (PDF or TXT).

    Args:
        file_storage: Werkzeug FileStorage object or file-like object.

    Returns:
        Cleaned text string extracted from the document.

    Raises:
        ValueError: If file is missing, unsupported, or contains no readable text.
    """
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("No valid file provided.")

    filename = file_storage.filename.lower()

    if filename.endswith(".pdf"):
        return _extract_from_pdf(file_storage)
    elif filename.endswith(".txt"):
        return _extract_from_txt(file_storage)
    else:
        raise ValueError(
            "Unsupported file format. Please upload a .pdf or .txt file."
        )


def _extract_from_pdf(file_storage) -> str:
    """Extracts text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf package is required for PDF parsing. Install with 'pip install pypdf'."
        )

    try:
        # Seek to beginning in case file pointer was moved
        file_storage.seek(0)
        reader = PdfReader(file_storage)

        if len(reader.pages) == 0:
            raise ValueError("The uploaded PDF file is empty.")

        extracted_text = []
        for index, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                extracted_text.append(page_text)

        full_text = "\n".join(extracted_text).strip()
        if not full_text:
            raise ValueError(
                "Could not extract text from the PDF. It may be a scanned image or protected."
            )

        return _clean_text(full_text)
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Error parsing PDF file: {str(e)}")


def _extract_from_txt(file_storage) -> str:
    """Extracts text from a plain text file."""
    try:
        file_storage.seek(0)
        content = file_storage.read()
        if isinstance(content, bytes):
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
        else:
            text = str(content)

        cleaned = _clean_text(text)
        if not cleaned:
            raise ValueError("The uploaded text file is empty.")
        return cleaned
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Error reading text file: {str(e)}")


def _clean_text(text: str) -> str:
    """Normalizes whitespace and removes control characters."""
    if not text:
        return ""
    # Replace carriage returns with standard newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse multiple consecutive blank lines into double newline
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def analyze_resume(
    resume_text: str,
    target_role: str,
    job_description: str = "",
    api_key: str = "",
) -> Dict[str, Any]:
    """Coordinates resume analysis using Google Gemini or the local fallback.

    Args:
        resume_text: Text content of the resume.
        target_role: Desired job title.
        job_description: Optional detailed job requirements.
        api_key: Google Gemini API key if configured.

    Returns:
        Dictionary containing match_score, skills breakdown, strengths, etc.
    """
    resume_text = _clean_text(resume_text)
    if not resume_text:
        raise ValueError("Resume text cannot be empty.")

    target_role = target_role.strip() if target_role else "Software Professional"
    job_description = _clean_text(job_description)

    # Attempt Gemini analysis if API key is provided
    if api_key:
        try:
            return analyze_resume_with_gemini(
                resume_text=resume_text,
                target_role=target_role,
                job_description=job_description,
                api_key=api_key,
            )
        except Exception as e:
            logger.warning(
                f"Gemini API call encountered an error: {e}. Falling back to local analyzer."
            )
            return fallback_offline_analysis(
                resume_text=resume_text,
                target_role=target_role,
                job_description=job_description,
                warning_message=f"Gemini AI was unavailable ({str(e)}). Report generated using local rule-based analysis.",
            )

    # Fallback to local rule-based analysis
    return fallback_offline_analysis(
        resume_text=resume_text,
        target_role=target_role,
        job_description=job_description,
    )


def analyze_resume_with_gemini(
    resume_text: str,
    target_role: str,
    job_description: str,
    api_key: str,
) -> Dict[str, Any]:
    """Performs deep ATS analysis using Google Gemini 3.8 Flash with structured JSON output."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError(
            "google-genai package is required. Install with 'pip install google-genai'."
        )

    client = genai.Client(api_key=api_key)

    system_instruction = (
        "You are an expert Technical Recruiter and Applicant Tracking System (ATS) algorithm specialist. "
        "Your task is to analyze candidate resumes with high precision, compare them against target job roles "
        "and job descriptions, calculate an honest ATS match score (0 to 100), extract matched skills, identify missing critical "
        "skills, assess resume strengths and weaknesses, and deliver concrete, actionable formatting and content advice."
    )

    prompt = f"""
Please analyze the following resume for the target role: "{target_role}".

TARGET ROLE:
{target_role}

JOB DESCRIPTION / REQUIREMENTS (if provided):
{job_description or "None provided. Evaluate against standard industry expectations for " + target_role}

CANDIDATE RESUME:
\"\"\"
{resume_text}
\"\"\"

Analyze the resume thoroughly:
1. Extract the candidate's name (or "Candidate" if not found).
2. Calculate an ATS match score from 0 to 100 based on technical qualifications, relevant experience, keywords, and structural quality.
3. List skills clearly present in the resume that match the role.
4. List critical skills required or expected for the role that are missing from the resume.
5. Provide 3-5 concrete strengths (e.g. quantified achievements, strong tech stack, clear trajectory).
6. Provide 3-5 concrete weaknesses or red flags (e.g. missing metrics, vague bullet points, outdated tech, formatting gaps).
7. Provide actionable recommendations to improve the ATS ranking.
8. Provide specific formatting and keyword suggestions.
"""

    response_schema = {
        "type": "OBJECT",
        "required": [
            "candidate_name",
            "detected_role",
            "match_score",
            "summary",
            "matched_skills",
            "missing_skills",
            "strengths",
            "weaknesses",
            "recommendations",
            "formatting_advice",
        ],
        "properties": {
            "candidate_name": {"type": "STRING"},
            "detected_role": {"type": "STRING"},
            "match_score": {"type": "INTEGER"},
            "summary": {"type": "STRING"},
            "matched_skills": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
            "missing_skills": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
            "strengths": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
            "weaknesses": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
            "recommendations": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
            "formatting_advice": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
        },
    }

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_json_schema=response_schema,
            temperature=0.2,
        ),
    )

    data = json.loads(response.text)
    data["engine_mode"] = "gemini"
    data["model_used"] = "gemini-3.8-flash"
    # Ensure score is within valid bounds
    data["match_score"] = max(0, min(100, int(data.get("match_score", 50))))
    return data


def fallback_offline_analysis(
    resume_text: str,
    target_role: str,
    job_description: str = "",
    warning_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Local rule-based ATS analysis when Gemini API is unconfigured or unavailable."""
    resume_lower = resume_text.lower()
    jd_lower = job_description.lower() if job_description else ""
    role_lower = target_role.lower()

    # 1. Detect candidate name from top lines
    candidate_name = _extract_name_heuristic(resume_text)

    # 2. Extract skills found in resume
    found_resume_skills = set()
    for skill in SKILL_CATALOG:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, resume_lower):
            found_resume_skills.add(skill.title())

    # 3. Determine expected skills from JD or role benchmarks
    expected_skills = set()
    if jd_lower:
        for skill in SKILL_CATALOG:
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, jd_lower):
                expected_skills.add(skill.title())

    # Fallback to role benchmark if JD has few detected skills
    if len(expected_skills) < 4:
        for role_key, skills in ROLE_SKILL_BENCHMARKS.items():
            if role_key in role_lower:
                expected_skills.update(s.title() for s in skills)
                break
        if not expected_skills:
            # Default general benchmark
            expected_skills.update(
                s.title() for s in ROLE_SKILL_BENCHMARKS["software engineer"]
            )

    matched_skills = sorted(list(found_resume_skills.intersection(expected_skills)))
    missing_skills = sorted(list(expected_skills.difference(found_resume_skills)))

    # 4. Content & Structural Checks
    has_email = bool(re.search(r"[\w\.-]+@[\w\.-]+", resume_text))
    has_phone = bool(re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", resume_text))
    has_linkedin = "linkedin.com" in resume_lower or "github.com" in resume_lower
    has_experience = any(
        kw in resume_lower for kw in ["experience", "employment", "work history"]
    )
    has_education = any(
        kw in resume_lower for kw in ["education", "degree", "university", "bachelor", "master"]
    )
    has_projects = any(
        kw in resume_lower for kw in ["projects", "portfolio", "key achievements"]
    )
    has_metrics = bool(re.search(r"\b\d+%\b|\$\d+|\b\d+\s*users\b|\b\d+\s*percent\b", resume_lower))

    # 5. Calculate Score
    # Base skill match ratio (up to 55 points)
    if expected_skills:
        skill_ratio = len(matched_skills) / len(expected_skills)
        skill_score = min(55, int(skill_ratio * 55))
    else:
        skill_score = 30

    # Structural points (up to 30 points)
    structure_score = 0
    if has_experience:
        structure_score += 10
    if has_education:
        structure_score += 6
    if has_projects:
        structure_score += 6
    if has_email:
        structure_score += 4
    if has_phone:
        structure_score += 4

    # Metrics & Impact points (up to 15 points)
    impact_score = 15 if has_metrics else 5

    total_score = min(98, max(25, skill_score + structure_score + impact_score))

    # 6. Generate Strengths, Weaknesses & Recommendations
    strengths = []
    weaknesses = []
    recommendations = []
    formatting_advice = []

    if matched_skills:
        sample = ", ".join(matched_skills[:4])
        strengths.append(f"Demonstrates relevant competencies in {sample}.")
    if has_experience:
        strengths.append("Contains a clear, dedicated professional experience section.")
    if has_projects:
        strengths.append("Highlights practical project or portfolio work.")
    if has_metrics:
        strengths.append("Incorporates quantifiable metrics and measurable outcomes.")
    else:
        weaknesses.append("Lacks quantifiable metrics (e.g. '% improvements', 'revenue growth', 'user scale').")

    if missing_skills:
        sample_missing = ", ".join(missing_skills[:4])
        weaknesses.append(f"Key industry technologies for {target_role} were not identified: {sample_missing}.")
        recommendations.append(
            f"Add relevant experience, certifications, or projects highlighting: {sample_missing}."
        )

    if not has_linkedin:
        weaknesses.append("Missing links to professional profiles (GitHub, LinkedIn, or personal portfolio).")
        recommendations.append("Include your LinkedIn profile and relevant GitHub repository links in the header.")

    if not has_metrics:
        recommendations.append(
            "Use the Google XYZ formula in your bullet points: 'Accomplished [X] as measured by [Y] by doing [Z]'."
        )

    formatting_advice.append("Use standard headings (Experience, Education, Skills) so ATS parsers index sections accurately.")
    formatting_advice.append("Avoid multi-column tables, graphics, or text boxes that can disrupt automated parsers.")
    formatting_advice.append("Ensure date formats are consistent (e.g., 'Jan 2023 - Present').")

    summary = (
        f"Candidate's resume matches approximately {len(matched_skills)} core technical skills for "
        f"'{target_role}'. {len(missing_skills)} relevant skills are currently missing from the profile."
    )

    result = {
        "candidate_name": candidate_name,
        "detected_role": target_role,
        "match_score": total_score,
        "summary": summary,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "formatting_advice": formatting_advice,
        "engine_mode": "local",
    }
    if warning_message:
        result["engine_warning"] = warning_message

    return result


def _extract_name_heuristic(text: str) -> str:
    """Extracts likely candidate name from top lines of resume text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:5]:
        # Exclude headers, contact info, emails, urls
        if any(c in line for c in ["@", "http", "www.", "/", "+", "(", "|"]):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.isalpha() or "-" in w for w in words):
            # Check length of words
            if all(len(w) >= 2 for w in words):
                return line.title()
    return "Candidate"
