import re
import logging
from typing import List, Dict, Set, Tuple, Optional
from app.schemas.interview import ResumeProfileSchema, JDProfileSchema, SkillMatchSchema

logger = logging.getLogger("matching_service")

# Technology and skill alias mapping dictionary for normalization
TECH_ALIASES: Dict[str, str] = {
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "express": "express.js",
    "expressjs": "express.js",
    "express.js": "express.js",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "postgresql database": "postgresql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "spring": "spring boot",
    "springboot": "spring boot",
    "spring boot": "spring boot",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "docker": "docker",
    "aws": "amazon web services",
    "amazon web services": "amazon web services",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "google cloud platform": "google cloud platform",
    "azure": "microsoft azure",
    "microsoft azure": "microsoft azure",
    "sql": "sql",
    "rest": "rest api",
    "rest api": "rest api",
    "restful api": "rest api",
    "restful apis": "rest api",
    "git": "git",
    "github": "git",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "dsa": "data structures and algorithms",
    "data structures": "data structures and algorithms",
    "algorithms": "data structures and algorithms",
    "data structures & algorithms": "data structures and algorithms",
    "data structures and algorithms": "data structures and algorithms",
    "oop": "object oriented programming",
    "oops": "object oriented programming",
    "object-oriented programming": "object oriented programming",
}

RELATED_CLUSTERS: Dict[str, Set[str]] = {
    "javascript": {"typescript", "react", "node.js", "express.js", "frontend"},
    "python": {"django", "flask", "fastapi", "machine learning", "data science"},
    "java": {"spring boot", "hibernate", "microservices", "object oriented programming"},
    "sql": {"postgresql", "mysql", "databases", "query optimization"},
    "docker": {"kubernetes", "ci/cd", "devops", "cloud"},
    "rest api": {"backend", "microservices", "fastapi", "express.js", "spring boot"},
}

class SkillMatchingService:
    """
    Deterministically matches Resume skills with Job Description requirements.
    Normalizes aliases, whitespace, punctuation, identifies skill gaps, and computes match scores.
    Completely independent of Gemini.
    """

    @staticmethod
    def normalize_skill(skill: str) -> str:
        """Normalizes skill string by stripping punctuation, extra whitespace, and resolving known aliases."""
        if not skill:
            return ""
        s = skill.lower().strip()
        s = re.sub(r'[\(\)\[\]\{\},;]', '', s)
        s = re.sub(r'\s+', ' ', s)
        return TECH_ALIASES.get(s, s)

    @classmethod
    def match_skills(
        cls,
        resume: ResumeProfileSchema,
        jd: Optional[JDProfileSchema] = None
    ) -> SkillMatchSchema:
        # Collect and normalize all candidate skills
        candidate_raw = (
            resume.technical_skills +
            resume.programming_languages +
            resume.frameworks +
            resume.databases +
            resume.tools +
            resume.areas_of_expertise
        )
        candidate_skills_norm: Dict[str, str] = {} # norm -> original display
        for s in candidate_raw:
            norm = cls.normalize_skill(s)
            if norm and norm not in candidate_skills_norm:
                candidate_skills_norm[norm] = s.strip()

        if not jd:
            # General Interview - all extracted candidate skills are matched
            matched = list(candidate_skills_norm.values())
            return SkillMatchSchema(
                matched_skills=matched,
                skill_gaps=[],
                related_skills=[],
                priority_skills=matched[:5],
                match_percentage=100.0
            )

        # Collect and normalize JD required & preferred skills
        jd_required = jd.required_skills or []
        jd_preferred = jd.preferred_skills or []
        jd_technologies = jd.technologies or []

        all_jd_raw = list(dict.fromkeys(jd_required + jd_preferred + jd_technologies))
        jd_skills_norm: Dict[str, str] = {} # norm -> original display
        for s in all_jd_raw:
            norm = cls.normalize_skill(s)
            if norm and norm not in jd_skills_norm:
                jd_skills_norm[norm] = s.strip()

        matched_list: List[str] = []
        gaps_list: List[str] = []
        related_list: List[str] = []

        # Find direct matches and gaps
        for norm_jd, orig_jd in jd_skills_norm.items():
            if norm_jd in candidate_skills_norm:
                matched_list.append(orig_jd)
            else:
                # Check for substring / token overlap (e.g. "PostgreSQL Database" vs "PostgreSQL")
                partial_match = False
                for norm_cand in candidate_skills_norm.keys():
                    if norm_jd in norm_cand or norm_cand in norm_jd:
                        matched_list.append(orig_jd)
                        partial_match = True
                        break
                if not partial_match:
                    gaps_list.append(orig_jd)

        # Find related skills based on candidate profile
        for norm_cand in candidate_skills_norm.keys():
            cluster = RELATED_CLUSTERS.get(norm_cand, set())
            for gap_norm in [cls.normalize_skill(g) for g in gaps_list]:
                if gap_norm in cluster:
                    related_display = jd_skills_norm.get(gap_norm, gap_norm.title())
                    if related_display not in related_list:
                        related_list.append(related_display)

        # Priority skills (skills in required list that are matched or key gaps)
        priority = [s for s in (matched_list + gaps_list) if any(s.lower() == req.lower() for req in jd_required)]
        if not priority:
            priority = matched_list[:3] + gaps_list[:2]

        total_jd = len(jd_skills_norm)
        match_percentage = round((len(matched_list) / max(total_jd, 1)) * 100, 1)

        return SkillMatchSchema(
            matched_skills=matched_list,
            skill_gaps=gaps_list,
            related_skills=related_list,
            priority_skills=priority[:6],
            match_percentage=min(100.0, match_percentage)
        )
