import re
import logging
from typing import Dict, Any, List
from app.schemas.interview import ResumeProfileSchema
from app.services.gemini_service import GeminiService

logger = logging.getLogger("resume_service")

class ResumeService:
    """
    Extracts structured professional profile attributes from parsed Resume text.
    Uses Gemini when configured, with a robust deterministic NLP fallback.
    """

    @staticmethod
    async def analyze_resume(resume_text: str) -> ResumeProfileSchema:
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text is empty. Cannot perform analysis.")

        if GeminiService.is_configured():
            try:
                system_instruction = (
                    "You are an expert HR and Placement Officer. Extract factual profile data from the candidate's resume.\n"
                    "RULES:\n"
                    "1. Only extract information explicitly supported by the resume text. DO NOT invent or assume details.\n"
                    "2. Return pure structured JSON matching the requested fields.\n"
                    "3. If a field is not present, return an empty list, empty object, or null for that field — do NOT populate defaults.\n"
                )
                prompt = (
                    f"Analyze the following resume text and extract structured profile attributes:\n\n"
                    f"--- RESUME START ---\n{resume_text}\n--- RESUME END ---\n\n"
                    f"Required JSON structure:\n"
                    f"{{\n"
                    f'  "candidate_name": "...",\n'
                    f'  "contact_information": {{"email": "...", "phone": "...", "links": []}},\n'
                    f'  "education": ["..."],\n'
                    f'  "technical_skills": ["..."],\n'
                    f'  "programming_languages": ["..."],\n'
                    f'  "frameworks": ["..."],\n'
                    f'  "databases": ["..."],\n'
                    f'  "tools": ["..."],\n'
                    f'  "projects": [{{"name":"...","description":"...","technologies":[],"responsibilities":[],"outcomes":[]}}],\n'
                    f'  "certifications": ["..."],\n'
                    f'  "achievements": ["..."],\n'
                    f'  "experience": [{{"company":"...","role":"...","duration":"...","responsibilities":[],"technologies":[],"achievements":[]}}],\n'
                    f'  "internships": [],\n'
                    f'  "areas_of_expertise": ["..."],\n'
                    f'  "soft_skills": [],\n'
                    f'  "languages_known": []\n'
                    f"}}"
                )
                result = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_model=ResumeProfileSchema
                )
                return ResumeProfileSchema(**result)
            except Exception as e:
                logger.warning(f"Gemini resume analysis failed or unavailable ({e}). Using deterministic NLP extractor.")

        return ResumeService._deterministic_extract(resume_text)

    @staticmethod
    def _deterministic_extract(text: str) -> ResumeProfileSchema:
        """Conservative deterministic extraction. Does NOT invent missing data — returns empty lists/objects when not found."""
        # Basic cleaning: normalize whitespace but preserve line breaks and bullets
        cleaned = re.sub(r"\r\n|\r", "\n", text)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)  # collapse 3+ blank lines
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

        lines = [line.rstrip() for line in cleaned.split('\n')]

        # Candidate name: look for lines like 'Name: X' or top-most line that looks like a name
        candidate_name = ""
        for l in lines[:8]:
            if not l.strip():
                continue
            m = re.match(r"^name\s*[:\-]\s*(.+)$", l, re.IGNORECASE)
            if m:
                candidate_name = m.group(1).strip()
                break
            # heuristics: first line with 2-4 words and no contact markers
            if 1 < len(l.split()) <= 4 and not re.search(r"\b(phone|email|@|www\.|linkedin|github)\b", l, re.IGNORECASE):
                candidate_name = l.strip()
                break

        # Contact extraction
        contact = {"email": [], "phone": [], "links": []}
        # emails
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        contact["email"] = list(dict.fromkeys(emails))
        # phones (simple patterns)
        phones = re.findall(r"(?:\+?\d{1,3}[\s-]?)?(?:\(\d{2,4}\)[\s-]?|\d{2,4}[\s-])?\d{3,4}[\s-]?\d{3,4}", text)
        contact["phone"] = [p.strip() for p in list(dict.fromkeys(phones))]
        # links (linkedin, github, portfolio)
        links = re.findall(r"https?://[^\s,;]+", text)
        for l in links:
            if any(k in l.lower() for k in ("linkedin", "github", "behance", "dribbble", "portfolio")):
                contact["links"].append(l)

        # Section detection: map heading keywords to their lines
        headings = {
            "education": ["education", "academics", "qualification", "qualifications"],
            "projects": ["project", "projects", "academic projects"],
            "certifications": ["certification", "certifications", "certificate"],
            "experience": ["experience", "work experience", "employment", "professional experience", "roles"],
            "skills": ["skills", "technical skills", "skills & technologies", "key skills"],
            "achievements": ["achievement", "achievements", "awards", "honors"],
            "languages": ["languages", "languages known"],
            "internships": ["internship", "internships"]
        }

        sections = {k: [] for k in headings.keys()}
        curr = None
        for line in lines:
            l = line.strip()
            if not l:
                # preserve blank line as separator
                if curr:
                    sections[curr].append("")
                continue
            lowered = l.lower()
            found_heading = False
            for key, kws in headings.items():
                for kw in kws:
                    # exact heading or line that starts with heading
                    if re.match(rf"^{re.escape(kw)}\b[:\-]?$", lowered) or lowered.startswith(kw + ":") or lowered == kw:
                        curr = key
                        found_heading = True
                        break
                if found_heading:
                    break
            if not found_heading:
                if curr:
                    sections[curr].append(l)

        # Known technology lists for fallback matching
        known_langs = ["python", "java", "c\+\+", "c#", "c", "javascript", "typescript", "ruby", "go", "golang", "rust", "php", "kotlin", "swift", "sql", "r", "html", "css"]
        known_frameworks = ["react", "react.js", "angular", "vue", "vue.js", "django", "flask", "fastapi", "spring", "spring boot", "express", "node.js", "next.js", "asp.net", "laravel", "rails"]
        known_databases = ["postgresql", "postgres", "mysql", "mongodb", "sqlite", "redis", "oracle", "mariadb", "cassandra", "dynamodb"]
        known_tools = ["git", "github", "docker", "kubernetes", "aws", "azure", "gcp", "linux", "jenkins", "jira", "postman", "figma", "vscode"]

        text_lower = text.lower()

        # Skills: prefer explicit Skills section; otherwise derive from known lists
        technical_skills = []
        programming_languages = []
        frameworks = []
        databases = []
        tools = []

        if sections.get("skills"):
            skill_lines = [ln for ln in sections["skills"] if ln.strip()]
            skill_text = "\n".join(skill_lines)
            # split by commas, bullets, pipes, semicolons
            parts = re.split(r"[\n,;•\-\|]\s*", skill_text)
            parts = [p.strip() for p in parts if p and len(p) <= 60]
            for p in parts:
                pl = p.lower()
                # classifying heuristics
                if any(re.search(rf"\b{fw}\b", pl) for fw in known_frameworks):
                    frameworks.append(p)
                elif any(re.search(rf"\b{db}\b", pl) for db in known_databases):
                    databases.append(p)
                elif any(re.search(rf"\b{t}\b", pl) for t in known_tools):
                    tools.append(p)
                else:
                    technical_skills.append(p)
        else:
            # fallback: scan text for known tokens (conservative)
            for token in known_langs:
                if re.search(rf"\b{token}\b", text_lower):
                    display = token.upper() if len(token) <= 2 else token.title()
                    programming_languages.append(display)
            for token in known_frameworks:
                if re.search(rf"\b{re.escape(token)}\b", text_lower):
                    frameworks.append(token.title())
            for token in known_databases:
                if re.search(rf"\b{re.escape(token)}\b", text_lower):
                    databases.append(token.title())
            for token in known_tools:
                if re.search(rf"\b{re.escape(token)}\b", text_lower):
                    tools.append(token.title())
            # treat programming_languages as part of technical_skills as well
            technical_skills = list(dict.fromkeys(programming_languages + frameworks + databases + tools))

        # Projects: parse project section into blocks separated by blank lines
        projects_struct = []
        proj_lines = [l for l in sections.get("projects", [])]
        if proj_lines:
            blocks = []
            block = []
            for l in proj_lines:
                if not l.strip():
                    if block:
                        blocks.append(block)
                        block = []
                else:
                    block.append(l)
            if block:
                blocks.append(block)

            for b in blocks:
                name = ""
                description = ""
                technologies = []
                responsibilities = []
                outcomes = []
                # heuristics: first line could be name (short) or title
                if b:
                    first = b[0]
                    if len(first.split()) <= 8 and not first.endswith(":"):
                        name = first.strip()
                        description = " ".join(b[1:]).strip()
                    else:
                        description = " ".join(b).strip()
                # detect techs inside description using known lists
                for token in (known_langs + known_frameworks + known_databases + known_tools):
                    if re.search(rf"\b{token}\b", description.lower()):
                        t = token.upper() if len(token) <= 2 else token.title()
                        if t not in technologies:
                            technologies.append(t)

                # responsibilities: lines starting with verbs or bullet markers
                for line in b:
                    if re.match(r"^(?:- |• |\* )", line) or re.match(r"^(Designed|Implemented|Led|Created|Developed|Maintained|Built)\b", line, re.IGNORECASE):
                        responsibilities.append(line.strip("-•* "))
                    # outcomes: look for words like 'resulted in', 'reduced', 'improved', 'increased'
                    if re.search(r"\b(resulted in|reduced|improved|increased|decreased|achieved)\b", line, re.IGNORECASE):
                        outcomes.append(line.strip())

                projects_struct.append({
                    "name": name or None,
                    "description": description or None,
                    "technologies": technologies,
                    "responsibilities": responsibilities,
                    "outcomes": outcomes
                })

        # Experience: parse experience section into entries by blank-line separated blocks
        exp_struct = []
        exp_lines = [l for l in sections.get("experience", [])]
        if exp_lines:
            blocks = []
            block = []
            for l in exp_lines:
                if not l.strip():
                    if block:
                        blocks.append(block)
                        block = []
                else:
                    block.append(l)
            if block:
                blocks.append(block)

            for b in blocks:
                company = None
                role = None
                duration = None
                responsibilities = []
                technologies = []
                achievements_e = []

                # try to parse header line e.g. 'Company - Role (Duration)'
                header = b[0]
                # look for parentheses containing years/duration
                m = re.match(r"^(?P<header>.+?)\s*[\-–—\|]\s*(?P<role>.+?)\s*(?:\((?P<dur>.+?)\))?$", header)
                if m:
                    company = m.group('header').strip()
                    role = m.group('role').strip()
                    if m.group('dur'):
                        duration = m.group('dur').strip()
                else:
                    # fallback try 'Role at Company, Duration'
                    m2 = re.match(r"^(?P<role>.+?)\s+at\s+(?P<company>.+?)(?:,\s*(?P<dur>.+))?$", header, re.IGNORECASE)
                    if m2:
                        role = m2.group('role').strip()
                        company = m2.group('company').strip()
                        if m2.group('dur'):
                            duration = m2.group('dur').strip()

                # rest lines: responsibilities/achievements
                for line in b[1:]:
                    if re.match(r"^(?:- |• |\* )", line):
                        responsibilities.append(line.strip("-•* "))
                    if re.search(r"\b(resulted in|reduced|improved|increased|achieved)\b", line, re.IGNORECASE):
                        achievements_e.append(line.strip())
                    # detect tech mentions
                    for token in (known_langs + known_frameworks + known_databases + known_tools):
                        if re.search(rf"\b{token}\b", line.lower()):
                            t = token.upper() if len(token) <= 2 else token.title()
                            if t not in technologies:
                                technologies.append(t)

                exp_struct.append({
                    "company": company,
                    "role": role,
                    "duration": duration,
                    "responsibilities": responsibilities,
                    "technologies": technologies,
                    "achievements": achievements_e
                })

        # Education and certifications/achievements are already captured in sections
        education = [l for l in sections.get("education", []) if l.strip()]
        certifications = [l for l in sections.get("certifications", []) if l.strip()]
        achievements = [l for l in sections.get("achievements", []) if l.strip()]

        # Languages and internships
        languages_known = []
        if sections.get("languages"):
            lang_lines = [ln for ln in sections["languages"] if ln.strip()]
            # split by commas
            parts = re.split(r"[\n,;]\s*", "\n".join(lang_lines))
            languages_known = [p.strip() for p in parts if p.strip()]

        internships = []
        if sections.get("internships"):
            # similar parsing to experience
            blocks = []
            block = []
            for l in sections.get("internships"):
                if not l.strip():
                    if block:
                        blocks.append(block)
                        block = []
                else:
                    block.append(l)
            if block:
                blocks.append(block)
            for b in blocks:
                internships.append({"text": " ".join(b).strip()})

        # Soft skills: try to find 'soft skills' heading or look for common soft-skill words
        soft_skills = []
        if sections.get("skills"):
            # if skills section contains 'communication', 'team', etc, extract as soft skills heuristically
            for ln in sections.get("skills"):
                if re.search(r"communication|team|leadership|collaborat|problem solving|adaptab|time management", ln, re.IGNORECASE):
                    # split by commas
                    parts = re.split(r"[\n,;]\s*", ln)
                    for p in parts:
                        if re.search(r"communication|team|leadership|problem solving|adaptab|time management", p, re.IGNORECASE):
                            soft_skills.append(p.strip())

        # Areas of expertise: derive conservatively from found tech tokens
        areas = []
        if programming_languages:
            areas.append(f"Software Engineering ({', '.join(programming_languages[:3])})")
        if frameworks:
            areas.append(f"Web/Application Development ({', '.join(frameworks[:2])})")
        if databases:
            areas.append(f"Database Management ({', '.join(databases[:2])})")

        # Final structure - do NOT invent defaults; return empty lists/None where appropriate
        profile = ResumeProfileSchema(
            candidate_name=candidate_name or "",
            contact_information=contact,
            education=education,
            technical_skills=technical_skills,
            programming_languages=programming_languages,
            frameworks=frameworks,
            databases=databases,
            tools=tools,
            projects=projects_struct,
            certifications=certifications,
            achievements=achievements,
            experience=exp_struct,
            internships=internships,
            areas_of_expertise=areas,
            soft_skills=soft_skills,
            languages_known=languages_known
        )

        return profile

    @staticmethod
    def validate_resume(text: str) -> Dict[str, Any]:
        """Heuristic validation producing a confidence score and reasons.
        Returns: { is_valid: bool, document_type: 'resume'|'unknown', confidence: float, reasons: [str] }
        """
        reasons = []
        score = 0.0
        # quick checks
        if not text or not text.strip():
            return {"is_valid": False, "document_type": "unknown", "confidence": 0.0, "reasons": ["Empty or unreadable document"]}

        lower = text.lower()
        # indicators
        indicators = {
            "has_contact": bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)) or bool(re.search(r"\b(phone|contact)\b", lower)),
            "has_education": bool(re.search(r"\b(education|bachelor|master|degree|university|college|graduat)\b", lower)),
            "has_skills": bool(re.search(r"\b(skills?|technical skills|programming languages)\b", lower)) or bool(re.search(r"\b(python|java|javascript|sql|react|fastapi|django)\b", lower)),
            "has_projects": bool(re.search(r"\b(projects?|project)\b", lower)) or bool(re.search(r"\b(system|project|application|website)\b", lower)),
            "has_experience": bool(re.search(r"\b(experience|internship|worked at|employed|employment)\b", lower)),
            "has_certifications": bool(re.search(r"\b(certification|certified|certificate)\b", lower))
        }

        # accumulate score
        if indicators["has_contact"]:
            score += 0.25
            reasons.append("Contains contact information (email/phone)")
        if indicators["has_education"]:
            score += 0.2
            reasons.append("Contains education section or degree keywords")
        if indicators["has_skills"]:
            score += 0.2
            reasons.append("Contains skills or programming language mentions")
        if indicators["has_projects"]:
            score += 0.15
            reasons.append("Contains project section or project-like descriptions")
        if indicators["has_experience"]:
            score += 0.15
            reasons.append("Mentions work experience or internships")
        if indicators["has_certifications"]:
            score += 0.05
            reasons.append("Mentions certifications")

        confidence = min(1.0, score)
        is_valid = confidence >= 0.4 and (indicators["has_contact"] or indicators["has_skills"])

        doc_type = "resume" if is_valid else "unknown"
        if not reasons:
            reasons.append("Document does not contain recognisable resume indicators")

        return {"is_valid": is_valid, "document_type": doc_type, "confidence": round(confidence, 2), "reasons": reasons}
