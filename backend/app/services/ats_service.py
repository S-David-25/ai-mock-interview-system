import re
from typing import Dict, Any, List
from app.schemas.interview import ResumeProfileSchema, JDProfileSchema
from app.services.matching_service import SkillMatchingService
from app.config import (
    # ATS weights default
    TECHNICAL_WEIGHT, 
    # reuse some existing config names for clarity if present
)

# Define ATS-specific weights here (defaults). These can be overridden via environment if desired.
ATS_WEIGHTS = {
    "technical_skills": 0.40,
    "keywords": 0.20,
    "experience": 0.15,
    "role_alignment": 0.15,
    "education": 0.10,
}

class ATSService:
    """Deterministic ATS-style scoring based on Resume and JD structured data.
    The algorithm is explainable and reproducible.
    """

    @staticmethod
    def _normalize_list(items: List[str]) -> List[str]:
        out = []
        for it in items or []:
            if not it:
                continue
            s = re.sub(r"[\W_]+", " ", it).strip().lower()
            out.append(s)
        return list(dict.fromkeys(out))

    @staticmethod
    def compute_ats(
        resume: ResumeProfileSchema,
        jd: JDProfileSchema,
        company: str = "",
        role: str = "",
        skill_match: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Return an ATS analysis dict with components and the final score (0-100).
        Uses deterministic heuristics based on structured fields.
        """
        # Normalize
        resume_skills = ATSService._normalize_list(
            (resume.technical_skills or []) + (resume.programming_languages or []) + (resume.frameworks or []) + (resume.databases or []) + (resume.tools or [])
        )
        jd_skills = ATSService._normalize_list((jd.required_skills or []) + (jd.preferred_skills or []) + (jd.technologies or []))
        jd_keywords = ATSService._normalize_list(jd.important_keywords or [])

        # Skill matching - reuse matching_service percentage when available
        skill_match_pct = 0.0
        matched_skills = []
        missing_skills = []
        if skill_match:
            try:
                skill_match_pct = float(skill_match.get('match_percentage') or 0.0)
                matched_skills = skill_match.get('matched_skills', [])
                missing_skills = skill_match.get('skill_gaps', [])
            except Exception:
                skill_match_pct = 0.0

        # Keyword coverage: fraction of JD keywords found in resume text/fields
        project_text = []
        for project in resume.projects or []:
            if isinstance(project, dict):
                p_name = project.get("name") or ""
                p_desc = project.get("description") or ""
                project_text.extend([str(p_name), str(p_desc)])
            elif hasattr(project, "name"):
                project_text.extend([str(getattr(project, "name", "") or ""), str(getattr(project, "description", "") or "")])

        experience_text = []
        for exp in resume.experience or []:
            if isinstance(exp, dict):
                e_role = exp.get("role") or ""
                e_comp = exp.get("company") or ""
                e_resp = exp.get("responsibilities") or []
                if isinstance(e_resp, list):
                    e_resp = " ".join(str(r) for r in e_resp if r)
                experience_text.extend([str(e_role), str(e_comp), str(e_resp)])
            elif hasattr(exp, "role"):
                e_resp = getattr(exp, "responsibilities", []) or []
                if isinstance(e_resp, list):
                    e_resp = " ".join(str(r) for r in e_resp if r)
                experience_text.extend([str(getattr(exp, "role", "") or ""), str(getattr(exp, "company", "") or ""), str(e_resp)])

        resume_text_fields = " ".join(filter(None, [
            str(resume.candidate_name or ""),
            " ".join(str(s) for s in resume_skills if s),
            " ".join(str(a) for a in (resume.areas_of_expertise or []) if a),
            " ".join(str(s) for s in (resume.soft_skills or []) if s),
            " ".join(str(p) for p in project_text if p),
            " ".join(str(e) for e in experience_text if e),
        ]))
        resume_text_l = resume_text_fields.lower()
        matched_keywords = []
        for kw in jd_keywords:
            if kw and kw in resume_text_l:
                matched_keywords.append(kw)
        keyword_coverage = round((len(matched_keywords) / max(1, len(jd_keywords))) * 100, 1) if jd_keywords else 100.0

        # Experience match heuristic
        exp_match_pct = 0.0
        if jd.experience_requirements:
            # if resume has any experience entries, give partial/full credit based on presence
            if resume.experience and len(resume.experience) > 0:
                exp_match_pct = 85.0
            else:
                exp_match_pct = 20.0
        else:
            exp_match_pct = 100.0

        # Education match heuristic
        edu_match_pct = 0.0
        if jd.experience_requirements and any(re.search(r"degree|bachelor|master|phd|b\.tech|btech|m\.tech|msc", k.lower()) for k in jd.experience_requirements):
            if resume.education and len(resume.education) > 0:
                edu_match_pct = 100.0
            else:
                edu_match_pct = 20.0
        else:
            edu_match_pct = 100.0

        # Role alignment: check if job role appears in candidate experience roles or job_role similarity
        role_align_pct = 0.0
        target_role = (role or jd.job_role or "").lower()
        found_role = False
        if target_role:
            for e in (resume.experience or []):
                if isinstance(e, dict):
                    role_field = (e.get('role') or "").lower()
                    if role_field and target_role in role_field:
                        found_role = True
                        break
            if not found_role:
                resume_text_l = " ".join(filter(None, [
                    resume.candidate_name,
                    " ".join(resume.areas_of_expertise or []),
                    " ".join(resume.soft_skills or []),
                    " ".join([exp.get('role', '') for exp in (resume.experience or []) if isinstance(exp, dict)]),
                ])).lower()
                if target_role in resume_text_l:
                    found_role = True
        role_align_pct = 100.0 if found_role else 40.0 if resume.experience else 0.0

        # Compute weighted score
        w = ATS_WEIGHTS
        technical_component = (skill_match_pct or 0.0) * w['technical_skills']
        keyword_component = (keyword_coverage or 0.0) * w['keywords']
        experience_component = (exp_match_pct or 0.0) * w['experience']
        role_component = (role_align_pct or 0.0) * w['role_alignment']
        education_component = (edu_match_pct or 0.0) * w['education']

        raw_score = technical_component + keyword_component + experience_component + role_component + education_component
        # normalize to 0-100
        final_score = min(100, round(raw_score, 1))

        # score label
        if final_score >= 85:
            label = "Excellent"
        elif final_score >= 70:
            label = "Good"
        elif final_score >= 50:
            label = "Fair"
        else:
            label = "Poor"

        recommendations = []
        # Simple actionable recommendations
        if missing_skills:
            recommendations.append(f"Consider adding or highlighting experience with: {', '.join(missing_skills[:6])}.")
        if keyword_coverage < 70:
            recommendations.append("Increase keyword coverage from the Job Description in your summary or skills.")
        if role_align_pct < 50:
            recommendations.append("Highlight role-relevant responsibilities or project experience matching the target role.")

        ats = {
            "ats_score": final_score,
            "score_label": label,
            "technical_component": round((skill_match_pct or 0.0), 1),
            "keyword_coverage": keyword_coverage,
            "experience_match": round(exp_match_pct, 1),
            "education_match": round(edu_match_pct, 1),
            "role_alignment": round(role_align_pct, 1),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "matched_keywords": matched_keywords,
            "recommendations": recommendations,
        }

        return ats
