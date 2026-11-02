import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.interview import (
    InterviewScoreResponse,
    JDProfileSchema,
    ResumeProfileSchema,
    RoadmapItemSchema,
    RoadmapPhaseSchema,
    RoadmapResponse,
    SkillMatchSchema,
)

logger = logging.getLogger("roadmap_service")


class PersonalizedRoadmapService:
    """Builds a session-specific study plan from stored JD and interview evidence."""

    RESOURCE_CATALOG = {
        "python": ("Python Tutorial", "Python", "https://docs.python.org/3/tutorial/"),
        "java": ("Java Tutorials", "Oracle", "https://docs.oracle.com/javase/tutorial/"),
        "spring": ("Spring Boot Reference", "Spring", "https://docs.spring.io/spring-boot/reference/"),
        "react": ("Learn React", "React", "https://react.dev/learn"),
        "javascript": ("JavaScript Guide", "MDN", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"),
        "typescript": ("TypeScript Handbook", "TypeScript", "https://www.typescriptlang.org/docs/handbook/"),
        "node.js": ("Node.js Learn", "Node.js", "https://nodejs.org/en/learn"),
        "angular": ("Angular Documentation", "Angular", "https://angular.dev/overview"),
        "vue": ("Vue Guide", "Vue", "https://vuejs.org/guide/introduction.html"),
        "css": ("CSS Documentation", "MDN", "https://developer.mozilla.org/en-US/docs/Web/CSS"),
        "html": ("HTML Documentation", "MDN", "https://developer.mozilla.org/en-US/docs/Web/HTML"),
        "fastapi": ("FastAPI Tutorial", "FastAPI", "https://fastapi.tiangolo.com/tutorial/"),
        "django": ("Django Tutorial", "Django", "https://docs.djangoproject.com/en/stable/intro/tutorial01/"),
        "flask": ("Flask Tutorial", "Flask", "https://flask.palletsprojects.com/en/stable/tutorial/"),
        "sql": ("PostgreSQL Tutorial", "PostgreSQL", "https://www.postgresql.org/docs/current/tutorial.html"),
        "postgres": ("PostgreSQL Tutorial", "PostgreSQL", "https://www.postgresql.org/docs/current/tutorial.html"),
        "mysql": ("MySQL Documentation", "MySQL", "https://dev.mysql.com/doc/"),
        "rest": ("HTTP and REST", "MDN", "https://developer.mozilla.org/en-US/docs/Web/HTTP"),
        "api": ("HTTP and REST", "MDN", "https://developer.mozilla.org/en-US/docs/Web/HTTP"),
        "docker": ("Get Started", "Docker", "https://docs.docker.com/get-started/"),
        "kubernetes": ("Kubernetes Basics", "Kubernetes", "https://kubernetes.io/docs/tutorials/kubernetes-basics/"),
        "kafka": ("Kafka Documentation", "Apache Kafka", "https://kafka.apache.org/documentation/"),
        "redis": ("Redis Documentation", "Redis", "https://redis.io/docs/latest/"),
        "aws": ("AWS Skill Builder", "AWS", "https://skillbuilder.aws/"),
        "azure": ("Azure Documentation", "Microsoft", "https://learn.microsoft.com/en-us/azure/"),
        "gcp": ("Google Cloud Documentation", "Google Cloud", "https://cloud.google.com/docs"),
        "pandas": ("Getting started", "pandas", "https://pandas.pydata.org/docs/getting_started/index.html"),
        "numpy": ("NumPy Quickstart", "NumPy", "https://numpy.org/doc/stable/user/quickstart.html"),
        "scikit-learn": ("Getting Started", "scikit-learn", "https://scikit-learn.org/stable/getting_started.html"),
        "pytorch": ("Learn the Basics", "PyTorch", "https://pytorch.org/tutorials/beginner/basics/intro.html"),
        "tensorflow": ("Tutorials", "TensorFlow", "https://www.tensorflow.org/tutorials"),
        "machine learning": ("Getting Started", "scikit-learn", "https://scikit-learn.org/stable/getting_started.html"),
        "communication": ("Technical Writing Courses", "Google", "https://developers.google.com/tech-writing"),
        "fluency": ("Public Speaking Tips", "Toastmasters", "https://www.toastmasters.org/resources/public-speaking-tips"),
    }

    @staticmethod
    def _unique(values: List[str]) -> List[str]:
        unique: List[str] = []
        seen = set()
        for value in values:
            cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .,-")
            key = cleaned.casefold()
            if cleaned and key not in seen:
                seen.add(key)
                unique.append(cleaned)
        return unique

    @classmethod
    def _resources(cls, topic: str) -> List[Dict[str, str]]:
        topic_lower = topic.casefold()
        found = []
        seen_urls = set()
        for key, (title, provider, url) in cls.RESOURCE_CATALOG.items():
            if key in topic_lower and url not in seen_urls:
                seen_urls.add(url)
                found.append({
                    "title": title,
                    "provider": provider,
                    "url": url,
                    "resource_type": "official_documentation",
                })
        return found[:2]

    @staticmethod
    def _profile_text(profile: Optional[ResumeProfileSchema]) -> str:
        if not profile:
            return ""
        fields = (
            profile.technical_skills + profile.programming_languages + profile.frameworks
            + profile.databases + profile.tools + profile.areas_of_expertise
        )

        def collect_text(value: Any) -> List[str]:
            if isinstance(value, str):
                return [value]
            if isinstance(value, list):
                return [text for item in value for text in collect_text(item)]
            if isinstance(value, dict):
                return [text for item in value.values() for text in collect_text(item)]
            return []

        project_and_experience = (
            collect_text(profile.projects)
            + collect_text(profile.experience)
            + collect_text(profile.internships)
        )
        return " ".join(fields + project_and_experience).casefold()

    @classmethod
    def _topic_evidence(
        cls,
        topic: str,
        questions: List[Dict[str, Any]],
        resume_text: str,
        skill_match: Optional[SkillMatchSchema],
    ) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        def normalize(value: str) -> str:
            normalized = re.sub(r"\bapis\b", "api", value.casefold())
            return re.sub(r"[^a-z0-9+#.]+", " ", normalized).strip()

        topic_lower = normalize(topic)
        for question in questions:
            answer = str(question.get("candidate_answer") or "").strip()
            if not answer or answer.casefold() == "transcription unavailable":
                continue
            evidence_text = " ".join([
                str(question.get("question") or ""),
                answer,
                str(question.get("feedback") or ""),
            ]).casefold()
            if topic_lower not in normalize(evidence_text):
                continue
            try:
                technical_score = float(question.get("technical_score"))
            except (TypeError, ValueError):
                technical_score = None
            if technical_score is not None and technical_score < 70:
                return (
                    "demonstrated_weakness",
                    f"Question {question.get('order_number', '?')} directly covered {topic}; "
                    f"technical evaluation was {technical_score:.1f}%. {question.get('feedback') or ''}".strip(),
                    question,
                )
            if technical_score is not None and technical_score >= 80:
                return (
                    "demonstrated_strength",
                    f"Question {question.get('order_number', '?')} directly covered {topic}; "
                    f"technical evaluation was {technical_score:.1f}%.",
                    question,
                )
            return (
                "assessed_no_clear_gap",
                f"Question {question.get('order_number', '?')} covered {topic}; "
                "the available technical evaluation did not establish a clear weakness.",
                question,
            )

        if skill_match:
            if any(topic_lower == item.casefold() for item in skill_match.skill_gaps):
                return ("not_evidenced_in_resume", f"Resume-to-JD matching lists {topic} as a skill gap.", None)
            if any(topic_lower == item.casefold() for item in skill_match.matched_skills):
                return ("not_assessed", f"{topic} matched the resume but was not assessed by an interview answer.", None)
        resume_has_topic = bool(re.search(
            rf"(?<![a-z0-9]){re.escape(topic_lower)}(?![a-z0-9])",
            resume_text,
        )) if resume_text else False
        if resume_text and not resume_has_topic:
            return ("not_evidenced_in_resume", f"No evidence of {topic} was found in the parsed resume profile.", None)
        if resume_text:
            return ("not_assessed", f"The resume includes {topic}, but no interview answer assessed it.", None)
        return ("not_assessed", f"No interview answer assessed the JD requirement for {topic}.", None)

    @staticmethod
    def _item(
        topic: str,
        status: str,
        evidence: str,
        jd_requirement: Optional[str],
        *,
        priority: str,
        action: str,
        task: str,
        milestone: str,
        duration: str,
        study_plan: List[Dict[str, Any]],
        outcomes: Optional[List[str]] = None,
        criteria: Optional[List[str]] = None,
        resources: Optional[List[Dict[str, str]]] = None,
    ) -> RoadmapItemSchema:
        status_labels = {
            "demonstrated_weakness": "Demonstrated interview weakness",
            "not_evidenced_in_resume": "Not evidenced in resume",
            "not_assessed": "Not yet assessed",
            "demonstrated_strength": "Demonstrated strength",
            "assessed_no_clear_gap": "Assessed; no clear gap",
            "suggested_learning": "Suggested learning",
        }
        return RoadmapItemSchema(
            area=topic,
            problem=status_labels.get(status, status_labels["suggested_learning"]),
            recommended_action=action,
            practice_task=task,
            priority=priority,
            estimated_duration=duration,
            measurable_target=milestone,
            evidence_summary=evidence,
            learning_resources=resources or [],
            gap_status=status,
            jd_requirement=jd_requirement,
            candidate_evidence=evidence,
            learning_outcomes=outcomes or [],
            study_plan=study_plan,
            assessment_criteria=criteria or [],
        )

    @classmethod
    def generate_roadmap(
        cls,
        interview_id: int,
        user_id: int,
        score_data: InterviewScoreResponse,
        skill_match: Optional[SkillMatchSchema] = None,
        weaknesses: Optional[List[str]] = None,
        mistakes: Optional[List[Dict[str, Any]]] = None,
        job_role: Optional[str] = None,
        previous_scores: Optional[Dict[str, float]] = None,
        question_evidence: Optional[List[Dict[str, Any]]] = None,
        jd_profile: Optional[JDProfileSchema] = None,
        resume_profile: Optional[ResumeProfileSchema] = None,
    ) -> RoadmapResponse:
        questions = question_evidence or []
        mistakes = mistakes or []
        weaknesses = weaknesses or []
        target_role = (jd_profile.job_role if jd_profile and jd_profile.job_role else job_role) or "Target role"
        jd_available = bool(jd_profile and (
            jd_profile.required_skills
            or jd_profile.technologies
            or jd_profile.preferred_skills
            or jd_profile.responsibilities
        ))

        jd_skills: List[str] = []
        if jd_profile:
            jd_skills.extend(jd_profile.required_skills)
            jd_skills.extend(jd_profile.technologies)
            jd_skills.extend(jd_profile.preferred_skills)
        if jd_available and skill_match:
            jd_skills.extend(skill_match.skill_gaps)
            jd_skills.extend(skill_match.matched_skills)
        jd_skills = cls._unique(jd_skills)[:12]

        resume_text = cls._profile_text(resume_profile)
        topic_records = []
        for topic in jd_skills:
            status, evidence, question = cls._topic_evidence(topic, questions, resume_text, skill_match)
            topic_records.append({
                "topic": topic,
                "status": status,
                "evidence": evidence,
                "question": question,
                "jd_requirement": topic if jd_available else None,
            })

        priority_order = {
            "demonstrated_weakness": 0,
            "not_evidenced_in_resume": 1,
            "not_assessed": 2,
            "assessed_no_clear_gap": 3,
            "demonstrated_strength": 4,
        }
        topic_records.sort(key=lambda item: priority_order[item["status"]])
        prioritized = [item for item in topic_records if item["status"] in (
            "demonstrated_weakness", "not_evidenced_in_resume", "not_assessed"
        )]
        phase1_topics = prioritized[:2]

        phases: List[RoadmapPhaseSchema] = []
        if jd_available:
            phase1_items = [
                cls._item(
                    record["topic"], record["status"], record["evidence"], record["jd_requirement"],
                    priority="High" if record["status"] in ("demonstrated_weakness", "not_evidenced_in_resume") else "Medium",
                    action=f"Study the JD requirement for {record['topic']} using the linked documentation, then write a concise explanation of its purpose and core concepts.",
                    task=f"Implement a small {record['topic']} example and explain one design choice relevant to the target role.",
                    milestone=f"Complete a working example and answer a related interview question with at least 75% technical score.",
                    duration="3 days",
                    study_plan=[
                        {"day": 1, "activity": f"Read the official resource for {record['topic']} and summarize three core concepts."},
                        {"day": 2, "activity": f"Implement a minimal {record['topic']} example; record assumptions and trade-offs."},
                        {"day": 3, "activity": f"Explain the implementation aloud and answer one role-relevant question."},
                    ],
                    outcomes=[f"Explain the purpose and fundamental concepts of {record['topic']}.", f"Apply {record['topic']} in a small practical example."],
                    criteria=["Example runs or is technically coherent.", "Explanation names relevant concepts and one trade-off.", "Answer is supported by a concrete example."],
                    resources=cls._resources(record["topic"]),
                )
                for record in phase1_topics
            ]
            if not phase1_items:
                if topic_records:
                    requirement_list = ", ".join(record["topic"] for record in topic_records[:5])
                    phase1_items = [cls._item(
                        "JD competencies without an identified gap", "assessed_no_clear_gap",
                        "Available evidence did not establish a demonstrated weakness, missing resume evidence, or unassessed skill among the prioritized requirements.",
                        requirement_list, priority="Low",
                        action="Validate these competencies in a different practical scenario rather than treating demonstrated strengths as weaknesses.",
                        task=f"Choose one new use case for {requirement_list} and explain how your solution meets its requirements.",
                        milestone="Maintain at least 75% on comparable technical questions and demonstrate transfer to a new scenario.",
                        duration="1 day",
                        study_plan=[{"day": 1, "activity": f"Select a new JD-relevant scenario involving {requirement_list}; implement or outline it and review trade-offs."}],
                        criteria=["Use a distinct scenario.", "Record a comparable evaluation.", "Do not classify a demonstrated strength as a gap."],
                    )]
                else:
                    phase1_items = [cls._item(
                        "JD requirement review", "suggested_learning",
                        "The stored JD has no extracted skills to prioritize.", None,
                        priority="Medium",
                        action="Review the uploaded JD and identify the technical requirements that will be assessed.",
                        task="Create a checklist of the JD's explicit skills and map each to a resume example.",
                        milestone="Produce a checklist with a concrete evidence example or a learning gap for every listed requirement.",
                        duration="1 day",
                        study_plan=[{"day": 1, "activity": "Extract named skills and responsibilities from the uploaded JD; do not infer requirements that are not stated."}],
                        criteria=["Every listed skill is traceable to the JD.", "Resume evidence and unassessed requirements are clearly distinguished."],
                    )]
            phase1_title = "Immediate JD Skill-Gap Priorities"
            phase1_objective = f"Address the highest-priority requirements extracted from the {target_role} JD."
        else:
            phase1_items = []
            weakest_technical_question = next((
                question for question in questions
                if question.get("candidate_answer")
                and str(question.get("candidate_answer")).casefold() != "transcription unavailable"
                and question.get("technical_score") is not None
                and float(question["technical_score"]) < 70
            ), None)
            if weakest_technical_question:
                question_text = str(weakest_technical_question.get("question") or "Evaluated technical question")
                feedback = str(weakest_technical_question.get("feedback") or "Review the recorded technical evaluation.")
                phase1_items.append(cls._item(
                    f"Question {weakest_technical_question.get('order_number', '?')}: {question_text}",
                    "demonstrated_weakness",
                    feedback,
                    None,
                    priority="High",
                    action="Review the technical feedback, study the concepts explicitly named there, and prepare a corrected answer.",
                    task=f"Answer the same question again, addressing this feedback: {feedback}",
                    milestone="A new evaluation reaches at least 75% and addresses each feedback point.",
                    duration="2 days",
                    study_plan=[
                        {"day": 1, "activity": f"Break down the technical feedback for: {question_text}"},
                        {"day": 2, "activity": "Prepare and deliver a corrected answer; compare it with the original transcript."},
                    ],
                    criteria=["The revised answer addresses the actual evaluator feedback.", "No additional technical topic is assumed beyond the evidence."],
                ))
            communication = score_data.dimensions.get("communication")
            if communication and communication.is_available and communication.raw_score < 75:
                phase1_items.append(cls._item(
                    "Technical communication", "demonstrated_weakness",
                    f"Communication score was {communication.raw_score:.1f}%.",
                    None, priority="High",
                    action="Use a short context, explanation, example, and result structure when answering.",
                    task="Re-answer the lowest-scoring question in 90 seconds and compare the transcript with the original.",
                    milestone="Reach at least 75% communication score in a later interview.",
                    duration="3 days",
                    study_plan=[{"day": 1, "activity": "Review the original transcript and mark vague or incomplete phrases."},
                                {"day": 2, "activity": "Prepare a four-part answer outline for the weakest response."},
                                {"day": 3, "activity": "Record and review a concise 90-second response."}],
                    resources=cls._resources("communication"),
                ))
            phase1_items.append(cls._item(
                "Evidence-based interview review", "suggested_learning",
                "No readable uploaded JD is attached to this interview; the plan is general and does not claim JD-specific targeting.",
                None, priority="Medium",
                action="Use the actual question feedback in this report to select a topic before starting technical study.",
                task="Choose one evaluated question with a score below 70%, review its feedback, and write a corrected answer.",
                milestone="The corrected answer addresses every feedback point and achieves at least 75% on reassessment.",
                duration="2 days",
                study_plan=[{"day": 1, "activity": "Select the lowest-scoring evaluated answer and list the missing points from its feedback."},
                            {"day": 2, "activity": "Prepare and deliver a corrected answer; compare it against the original."}],
                criteria=["Topic is drawn from actual question feedback.", "No unassessed technical skill is labelled a failure."],
            ))
            phase1_title = "Immediate Interview Evidence Priorities"
            phase1_objective = "Address observable interview evidence without implying a JD-specific plan."
        phases.append(RoadmapPhaseSchema(
            phase_number=1, phase_title=f"Phase 1 — {phase1_title}",
            focus_objective=phase1_objective, items=phase1_items, estimated_duration_days=3,
        ))

        phase1_names = {item["topic"].casefold() for item in phase1_topics} if jd_available else set()
        remaining_topics = [record for record in topic_records if record["topic"].casefold() not in phase1_names]
        phase2_items: List[RoadmapItemSchema] = []
        for record in remaining_topics[:4]:
            status = record["status"]
            strength = status == "demonstrated_strength"
            phase2_items.append(cls._item(
                record["topic"], status, record["evidence"], record["jd_requirement"],
                priority="Low" if strength else "Medium",
                action=f"Follow the official {record['topic']} learning path in prerequisite order, then connect it to the responsibilities in the JD.",
                task=f"Complete one focused {record['topic']} exercise that demonstrates the requirement in a realistic use case.",
                milestone=f"Explain and demonstrate {record['topic']} without relying on notes; meet the assessment criteria below.",
                duration="5 days",
                study_plan=[
                    {"day": 1, "activity": f"Review {record['topic']} fundamentals and prerequisites."},
                    {"day": 2, "activity": f"Work through a basic {record['topic']} tutorial or official example."},
                    {"day": 3, "activity": f"Apply {record['topic']} to a small role-relevant scenario."},
                    {"day": 4, "activity": f"Test, debug, and document the example."},
                    {"day": 5, "activity": f"Summarize key decisions and answer a related technical question."},
                ],
                outcomes=[f"Apply the JD-listed {record['topic']} requirement.", "Explain the relevant implementation decisions."],
                criteria=["Exercise demonstrates the named requirement.", "Candidate can explain a key decision and trade-off."],
                resources=cls._resources(record["topic"]),
            ))
        if not phase2_items:
            if jd_available and topic_records:
                topic = topic_records[0]["topic"]
                phase2_items.append(cls._item(
                    f"{topic} reinforcement", "demonstrated_strength",
                    f"{topic} was already prioritized as a strength or assessed competency; this phase focuses on transfer rather than remediation.",
                    topic, priority="Low",
                    action=f"Apply {topic} to a different JD-relevant scenario and document the decision trade-offs.",
                    task=f"Extend the existing {topic} example with one new requirement from the JD.",
                    milestone="Complete the extension and explain why it satisfies the additional requirement.",
                    duration="3 days",
                    study_plan=[{"day": 1, "activity": f"Review the existing evidence for {topic}."},
                                {"day": 2, "activity": f"Extend the example to a distinct JD-relevant scenario."},
                                {"day": 3, "activity": "Review the result against the JD and explain the design trade-off."}],
                ))
            else:
                phase2_items.append(cls._item(
                    "Technical topic selection", "not_assessed",
                    "No JD skills or evaluated technical weakness were available to identify a specific technical syllabus.",
                    None, priority="Low",
                    action="Choose a technical topic from the role or a future JD before selecting learning material.",
                    task="Attach a JD or choose an explicit role requirement, then map it to one measurable exercise.",
                    milestone="Select a topic that can be traced to a role requirement or actual question feedback.",
                    duration="1 day",
                    study_plan=[{"day": 1, "activity": "Review interview questions and available role information; record which competencies remain unassessed."}],
                ))
        phases.append(RoadmapPhaseSchema(
            phase_number=2,
            phase_title=f"Phase 2 — {'Core JD Technical Learning' if jd_available else 'Core Learning (General Plan)'}",
            focus_objective=f"Build or reinforce specific competencies required for {target_role}." if jd_available else "Select future study topics from actual role requirements instead of assuming a fixed syllabus.",
            items=phase2_items,
            estimated_duration_days=5,
        ))

        phase3_items: List[RoadmapItemSchema] = []
        if jd_available and jd_skills:
            project_topics = [record["topic"] for record in prioritized[:3]]
            if not project_topics:
                project_topics = jd_skills[:3]
            project_label = ", ".join(project_topics)
            phase3_items.append(cls._item(
                f"Applied {target_role} practice",
                "suggested_learning",
                f"Practice project is scoped to extracted JD skills: {project_label}.",
                project_label, priority="Medium",
                action="Turn the selected JD requirements into one small, testable implementation rather than studying them only in isolation.",
                task=f"Build a focused project using {project_label}; include a short README explaining requirements, design, tests, and trade-offs.",
                milestone="Demonstrate the project in five minutes and map every implemented feature to a JD requirement.",
                duration="5 days",
                study_plan=[
                    {"day": 1, "activity": f"Define a minimal project scope from the JD requirements: {project_label}."},
                    {"day": 2, "activity": "Implement the core path and one representative use case."},
                    {"day": 3, "activity": "Add tests and handle one realistic edge case."},
                    {"day": 4, "activity": "Review correctness, document limitations, and prepare a concise demo."},
                    {"day": 5, "activity": "Present the implementation and explain decisions, evidence, and trade-offs."},
                ],
                outcomes=["Translate written requirements into a working example.", "Explain implementation choices with evidence."],
                criteria=["The project exercises at least one named JD requirement.", "A test or observable check verifies the core behavior.", "Explanation distinguishes implemented facts from assumptions."],
                resources=[resource for topic in project_topics for resource in cls._resources(topic)][:4],
            ))
        communication = score_data.dimensions.get("communication")
        fluency = score_data.dimensions.get("fluency")
        mistakes_summary = "; ".join(str(item.get("description", "")) for item in mistakes if item.get("description"))
        communication_weak = bool(communication and communication.is_available and communication.raw_score < 75)
        fluency_weak = bool((fluency and fluency.is_available and fluency.raw_score < 75) or mistakes_summary)
        if communication_weak or fluency_weak:
            metrics = []
            if communication_weak:
                metrics.append(f"communication score {communication.raw_score:.1f}%")
            if fluency_weak and fluency and fluency.is_available:
                metrics.append(f"fluency score {fluency.raw_score:.1f}%")
            evidence = ", ".join(metrics) or mistakes_summary
            phase3_items.append(cls._item(
                "Evidence-based answer delivery", "demonstrated_weakness",
                evidence, None, priority="Medium",
                action="Practise explaining the Phase 1/2 material using concise technical language and deliberate pacing.",
                task="Record three answers to questions actually covered in this interview; review clarity, pacing, and the recorded feedback.",
                milestone="Reach at least 75% in each available communication/fluency dimension and address the observed delivery mistake.",
                duration="3 days",
                study_plan=[{"day": 1, "activity": "Outline a response to a low-scoring question using evidence from the report."},
                            {"day": 2, "activity": "Record two timed answers and review the transcript for the measured issue."},
                            {"day": 3, "activity": "Record a final answer and compare it with the original baseline."}],
                resources=cls._resources("communication") + (cls._resources("fluency") if fluency_weak else []),
                criteria=["Response addresses the original feedback.", "Available communication and fluency scores improve from baseline."],
            ))
        if not phase3_items:
            phase3_items.append(cls._item(
                "Applied explanation practice", "suggested_learning",
                "No communication or fluency weakness was established by available evaluation metrics.",
                None, priority="Low",
                action="Use the practice material from the previous phases to explain a concrete implementation and its trade-offs.",
                task="Give a five-minute explanation of one completed exercise and answer two follow-up questions.",
                milestone="Explanation remains technically accurate and is supported by a working example.",
                duration="2 days",
                study_plan=[{"day": 1, "activity": "Prepare a short explanation from a completed role-relevant exercise."},
                            {"day": 2, "activity": "Deliver it without notes and verify accuracy against the implementation."}],
            ))
        phases.append(RoadmapPhaseSchema(
            phase_number=3, phase_title="Phase 3 — Applied Practice and Communication",
            focus_objective="Demonstrate learning through practical work; target communication or fluency only when the interview measured a weakness.",
            items=phase3_items, estimated_duration_days=5,
        ))

        mock_topics = [record for record in prioritized if record["status"] != "demonstrated_strength"][:3]
        mock_skill_names = [record["topic"] for record in mock_topics]
        weak_question = next((
            question for question in questions
            if question.get("candidate_answer")
            and str(question.get("candidate_answer")).casefold() != "transcription unavailable"
            and question.get("technical_score") is not None
            and float(question["technical_score"]) < 70
        ), None)
        if weak_question and not any(record["question"] is weak_question for record in prioritized):
            mock_skill_names.append(
                f"Question {weak_question.get('order_number', '?')}: {weak_question.get('question', 'technical question')}"
            )
        mock_scope = ", ".join(mock_skill_names) if mock_skill_names else (
            ", ".join(jd_skills[:3]) if jd_available else "the lowest-scoring evaluated questions"
        )
        mock_status = (
            "demonstrated_weakness" if weak_question
            else "not_assessed" if mock_skill_names
            else "suggested_learning"
        )
        phase4_item = cls._item(
            f"{target_role} mock interview practice",
            mock_status,
            f"Mock interview scope is based on {mock_scope}. Prioritize weak or untested competencies; avoid repeating already strong answers.",
            mock_scope if jd_available else None,
            priority="High" if mock_topics else "Medium",
            action="Run a focused mock interview using questions tied to the listed role requirements and this report's weakest evidence.",
            task=f"Complete a 30-minute mock session covering {mock_scope}; include one follow-up per topic and explain practical decisions.",
            milestone="Complete the session and record a technical evaluation for each targeted competency; compare scores with the baseline.",
            duration="2 days",
            study_plan=[{"day": 1, "activity": f"Prepare one new interview question each for: {mock_scope}."},
                        {"day": 2, "activity": "Complete the mock interview and log question-level scores and feedback."}],
            criteria=["Questions map to the JD or actual report evidence.", "Previously strong answers are not treated as gaps.", "Each competency receives an observable assessment."],
        )
        phases.append(RoadmapPhaseSchema(
            phase_number=4, phase_title=f"Phase 4 — {target_role} Mock Interview Preparation",
            focus_objective=f"Practise untested and weak competencies for {target_role}." if jd_available else "Practise the competencies actually assessed in this interview; request a JD for role-specific targeting.",
            items=[phase4_item], estimated_duration_days=2,
        ))

        previous_score = previous_scores.get("overall_score") if previous_scores else None
        phase5_evidence = (
            f"Current interview baseline: overall {score_data.overall_score:.1f}%."
            + (f" Previous interview overall: {float(previous_score):.1f}%." if previous_score is not None else " No previous completed interview was available.")
        )
        available_metrics = {
            name: round(dimension.raw_score, 1)
            for name, dimension in score_data.dimensions.items()
            if dimension.is_available
        }
        phases.append(RoadmapPhaseSchema(
            phase_number=5,
            phase_title="Phase 5 — Reassessment and Readiness",
            focus_objective="Measure change against this interview's baseline; make no readiness claim until new evidence is available.",
            items=[cls._item(
                "Targeted reassessment", "suggested_learning",
                phase5_evidence, ", ".join(jd_skills) if jd_available and jd_skills else None,
                priority="High",
                action="Repeat a comparable mock interview and practical task, then review each competency against its initial evidence.",
                task=f"Reassess the topics {mock_scope}; compare every available score with this interview's baseline.",
                milestone="Improve each targeted weak score by at least 5 points or reach 75%; retain baseline results when a metric is unavailable.",
                duration="1 day",
                study_plan=[{"day": 1, "activity": "Repeat a targeted practical assessment and mock interview; record scores, answer-level feedback, and metric availability."}],
                criteria=[
                    "Compare like-for-like question categories and practical tasks.",
                    "Report unavailable metrics as unavailable, not zero.",
                    "Set next learning priorities from new evidence; do not infer job readiness from this plan.",
                ],
            )],
            estimated_duration_days=1,
        ))

        if len(phases) != 5:
            logger.error("Roadmap generation produced %s phases for interview %s", len(phases), interview_id)
            raise ValueError("A personalized roadmap must contain exactly five phases.")

        return RoadmapResponse(
            interview_id=interview_id,
            user_id=user_id,
            overall_score=score_data.overall_score,
            readiness_level=score_data.readiness_level,
            phases=phases,
            created_at="",
            target_role=target_role,
            overall_learning_objective=(
                f"Develop and demonstrate the competencies needed for {target_role}, prioritizing the uploaded JD "
                "requirements and this interview's evidence."
                if jd_available else
                "This is a general plan based on available interview evidence; an uploaded readable JD is required for JD-specific targeting."
            ),
            jd_specific=jd_available,
            baseline_metrics=available_metrics,
            reassessment_plan={
                "comparison": "Compare like-for-like technical, communication, and fluency metrics with this interview baseline.",
                "previous_interview_available": bool(previous_scores),
                "metric_availability": {
                    name: bool(dimension.is_available)
                    for name, dimension in score_data.dimensions.items()
                },
                "previous_interview_overall": previous_score,
            },
        )
