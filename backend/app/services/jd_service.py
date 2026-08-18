import re
import logging
from typing import Dict, Any, List
from app.schemas.interview import JDProfileSchema
from app.services.gemini_service import GeminiService

logger = logging.getLogger("jd_service")

class JDService:
    """
    Extracts structured hiring criteria and required competencies from Job Descriptions.
    """

    @staticmethod
    async def analyze_jd(jd_text: str, default_company: str = "", default_role: str = "") -> JDProfileSchema:
        if not jd_text or not jd_text.strip():
            raise ValueError("Job Description text is empty.")

        if GeminiService.is_configured():
            try:
                system_instruction = (
                    "You are a technical recruiter. Extract structured hiring requirements from the Job Description text.\n"
                    "DO NOT invent requirements not mentioned in the text."
                )
                prompt = (
                    f"Analyze this Job Description:\n\n"
                    f"--- JD START ---\n{jd_text}\n--- JD END ---\n\n"
                    f"Fallback Company: {default_company}\nFallback Role: {default_role}\n\n"
                    f"Required JSON structure:\n"
                    f"{{\n"
                    f'  "company": "{default_company or "Target Company"}",\n'
                    f'  "job_role": "{default_role or "Software Engineer"}",\n'
                    f'  "required_skills": ["..."],\n'
                    f'  "preferred_skills": ["..."],\n'
                    f'  "responsibilities": ["..."],\n'
                    f'  "technologies": ["..."],\n'
                    f'  "experience_requirements": ["..."],\n'
                    f'  "soft_skills": ["..."],\n'
                    f'  "important_keywords": ["..."]\n'
                    f"}}"
                )
                result = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_model=JDProfileSchema
                )
                return JDProfileSchema(**result)
            except Exception as e:
                logger.warning(f"Gemini JD analysis failed ({e}). Using deterministic extractor.")

        return JDService._deterministic_extract(jd_text, default_company, default_role)

    @staticmethod
    def validate_jd(text: str) -> Dict[str, Any]:
        """Heuristic validation for Job Description content.
        Uses structural JD signals and candidate-specific resume markers.
        Returns:
            {"is_valid": bool, "document_type": "job_description"|"resume"|"unknown", "confidence": float, "reasons": [str]}
        """
        reasons = []
        if not text or not text.strip():
            return {"is_valid": False, "document_type": "unknown", "confidence": 0.0, "reasons": ["Empty or unreadable document"]}

        lower = text.lower()
        text_norm = re.sub(r"\s+", " ", text.strip())

        jd_score = 0.0
        resume_score = 0.0

        jd_checks = [
            (bool(re.search(r"\b(job title|position|role overview|software engineer|software developer|senior .* engineer|role\s*:\s*)\b", lower)), 0.22, "Contains a clear job title or role indicator"),
            (bool(re.search(r"\b(role overview|about the role|what you will do|what you'll do|you will|you'll|responsible for|key responsibilities|job responsibilities|duties)\b", lower)), 0.25, "Contains responsibilities or role overview language"),
            (bool(re.search(r"\b(minimum qualifications|preferred qualifications|requirements|qualifications|must have|nice to have|required skills|responsibilities)\b", lower)), 0.25, "Contains job requirements or qualifications section"),
            (bool(re.search(r"\b(experience with|years of experience|at least \d+ years|minimum \d+ years|degree required|bachelor.*degree|master.*degree|phd|experience required)\b", lower)), 0.12, "Mentions experience or degree requirements"),
            (bool(re.search(r"\b(coding skills|technical skills|programming languages|data structures|algorithms|cloud computing|distributed systems|software design|system design)\b", lower)), 0.12, "Mentions technical skills or coding abilities"),
            (bool(re.search(r"\b(company|about us|about google|team|hiring|join our team|we are looking for)\b", lower)), 0.10, "Contains company or hiring context"),
            (bool(re.search(r"\b(you are expected to|you will contribute|what you bring|preferred qualifications|must have)\b", lower)), 0.10, "Contains applicant expectation and qualification language"),
            (bool(re.search(r"\b(personal projects|past internships|internships|preferred qualifications)\b", lower)), 0.05, "Contains job-context project/internship language"),
        ]

        resume_checks = [
            (bool(re.search(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", lower)), 0.35, "Contains candidate email address"),
            (bool(re.search(r"\b\+?\d[\d\s().-]{7,}\d\b", lower)), 0.25, "Contains phone number or contact details"),
            (bool(re.search(r"\b(linkedin\.com|github\.com|portfolio|personal website|resume)\b", lower)), 0.25, "Contains personal profile link or portfolio"),
            (bool(re.search(r"\b(career objective|professional summary|objective)\b", lower)), 0.30, "Contains candidate objective or summary"),
            (bool(re.search(r"\b(work experience\b|employment history|professional experience)\b", lower)), 0.30, "Contains chronological employment history structure"),
            (bool(re.search(r"\b(education:\s*|b\.tech\s+in|btech\s+in|m\.tech\s+in|master\s+of|bachelor\s+of|university|college|school)\b", lower)), 0.25, "Contains candidate education history structure"),
            (bool(re.search(r"\b(references\b|awards\b|certifications\b|licenses\b)\b", lower)), 0.20, "Contains candidate credential or reference listing"),
            (bool(re.search(r"\b(projects?\s*:\s*|project\s*\d*\s*:\s*|personal projects?\b)\b", lower)), 0.10, "Contains a candidate project list"),
        ]

        for matched, weight, reason in jd_checks:
            if matched:
                jd_score += weight
                reasons.append(reason)

        for matched, weight, reason in resume_checks:
            if matched:
                resume_score += weight
                reasons.append(f"Resume-like indicator: {reason}")

        # Strong structural JD sections should dominate generic words.
        strong_jd_structure = sum(
            1 for pattern in [
                r"\b(role overview|about the role|overview)\b",
                r"\b(key responsibilities|responsibilities|duties)\b",
                r"\b(minimum qualifications|preferred qualifications|requirements|qualifications)\b",
                r"\b(what you will do|what you'll do|you will)\b",
            ]
            if re.search(pattern, lower)
        )

        # Penalize a short candidate summary that only contains generic skills terminology but no JD structure.
        if jd_score < 0.5 and resume_score < 0.4 and strong_jd_structure >= 2:
            jd_score += 0.25

        # Strong JD structure should override a few generic resume-like words.
        if strong_jd_structure >= 2 and jd_score >= 0.5:
            resume_score = max(0.0, resume_score - 0.35)

        confidence = min(1.0, max(0.0, jd_score - resume_score))
        is_valid = (jd_score >= 0.6 and jd_score >= resume_score + 0.2) or (strong_jd_structure >= 2 and jd_score >= 0.5 and resume_score < 0.5)
        doc_type = "job_description" if is_valid else ("resume" if resume_score > jd_score else "unknown")

        if not reasons:
            reasons.append("Document does not contain recognisable job description structure")

        # Ensure reasons remain readable and not overly noisy.
        unique_reasons = []
        for reason in reasons:
            if reason not in unique_reasons:
                unique_reasons.append(reason)

        return {
            "is_valid": bool(is_valid),
            "document_type": doc_type,
            "confidence": round(confidence, 2),
            "reasons": unique_reasons[:8]
        }

    @staticmethod
    def _deterministic_extract(text: str, default_company: str, default_role: str) -> JDProfileSchema:
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        tech_pool = [
            "python", "java", "c++", "c#", "javascript", "typescript", "go", "sql",
            "react", "angular", "node.js", "express", "django", "fastapi", "spring", "spring boot",
            "postgresql", "mysql", "mongodb", "redis",
            "docker", "kubernetes", "aws", "azure", "gcp", "git", "ci/cd", "rest api", "microservices", "graphql"
        ]
        soft_skills_pool = [
            "communication", "teamwork", "problem solving", "analytical skills",
            "leadership", "adaptability", "critical thinking", "agile", "scrum"
        ]

        text_lower = text.lower()
        found_tech = [t.title() if len(t) > 3 else t.upper() for t in tech_pool if re.search(r'\b' + re.escape(t) + r'\b', text_lower)]
        found_soft = [s.title() for s in soft_skills_pool if re.search(r'\b' + re.escape(s) + r'\b', text_lower)]

        responsibilities = []
        exp_reqs = []

        for line in lines:
            ll = line.lower()
            if any(k in ll for k in ["year", "years", "experience", "degree", "bachelor", "master"]):
                if len(exp_reqs) < 3 and len(line) < 120:
                    exp_reqs.append(line)
            if any(k in ll for k in ["build", "develop", "design", "maintain", "collaborate", "implement", "responsible"]):
                if len(responsibilities) < 4 and len(line) < 140:
                    responsibilities.append(line)

        return JDProfileSchema(
            company=default_company or "Target Company",
            job_role=default_role or "Software Engineer",
            required_skills=found_tech[:6] or ["Data Structures", "Algorithms", "Object-Oriented Design"],
            preferred_skills=found_tech[6:10] or ["Cloud Computing", "REST APIs"],
            responsibilities=responsibilities[:4] or ["Design and develop software components", "Collaborate with cross-functional teams"],
            technologies=found_tech or ["Core Programming", "SQL"],
            experience_requirements=exp_reqs[:3] or ["Fresh graduate or 0-2 years of relevant experience"],
            soft_skills=found_soft or ["Problem Solving", "Team Communication"],
            important_keywords=list(dict.fromkeys(found_tech + found_soft))[:10]
        )
