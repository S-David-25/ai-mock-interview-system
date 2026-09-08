import logging
from typing import Dict, Any, List, Optional
from app.schemas.interview import TechnicalEvaluationSchema
from app.services.gemini_service import GeminiService

logger = logging.getLogger("answer_evaluation_service")

class AnswerEvaluationService:
    """
    Evaluates technical correctness, relevance, completeness, and conceptual depth
    of candidate answers in relation to the specific question and expected focus areas.
    """

    @staticmethod
    async def evaluate_technical_answer(
        question_text: str,
        question_category: str,
        expected_focus: List[str],
        candidate_answer: str,
        role_context: Optional[str] = None
    ) -> TechnicalEvaluationSchema:
        if not candidate_answer or not candidate_answer.strip():
            return TechnicalEvaluationSchema(
                technical_score=0.0,
                correctness=0.0,
                relevance=0.0,
                completeness=0.0,
                depth=0.0,
                feedback="No answer provided for evaluation."
            )

        if GeminiService.is_configured():
            try:
                system_instruction = (
                    "You are a Principal Software Engineer evaluating a candidate's placement interview response.\n"
                    "Evaluate rigorously against technical correctness, depth, relevance, and expected focus.\n"
                    "Scores must be numeric between 0 and 100."
                )
                prompt = (
                    f"Question Category: {question_category}\n"
                    f"Question: {question_text}\n"
                    f"Expected Key Focus Points: {', '.join(expected_focus)}\n"
                    f"Target Role: {role_context or 'Software Engineer'}\n\n"
                    f"Candidate Answer:\n\"{candidate_answer}\"\n\n"
                    f"Required JSON structure:\n"
                    f"{{\n"
                    f'  "correctness": 88.0,\n'
                    f'  "relevance": 90.0,\n'
                    f'  "completeness": 82.0,\n'
                    f'  "depth": 80.0,\n'
                    f'  "technical_score": 85.0,\n'
                    f'  "feedback": "Actionable technical assessment of what was answered well and what trade-offs were missing."\n'
                    f"}}"
                )
                result = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.2,
                    purpose="Technical Evaluation"
                )
                corr = max(0.0, min(100.0, float(result.get("correctness", 75.0))))
                rel = max(0.0, min(100.0, float(result.get("relevance", 75.0))))
                comp = max(0.0, min(100.0, float(result.get("completeness", 70.0))))
                dep = max(0.0, min(100.0, float(result.get("depth", 70.0))))
                tech_score = max(0.0, min(100.0, float(result.get("technical_score", (corr*0.35 + rel*0.25 + comp*0.20 + dep*0.20)))))

                return TechnicalEvaluationSchema(
                    correctness=round(corr, 1),
                    relevance=round(rel, 1),
                    completeness=round(comp, 1),
                    depth=round(dep, 1),
                    technical_score=round(tech_score, 1),
                    feedback=result.get("feedback", "Solid technical explanation.")
                )
            except Exception as e:
                logger.warning(f"Gemini answer evaluation failed ({e}). Using NLP evaluator.")

        return AnswerEvaluationService._deterministic_eval(question_text, expected_focus, candidate_answer)

    @staticmethod
    def _deterministic_eval(
        question: str,
        expected_focus: List[str],
        candidate_answer: str
    ) -> TechnicalEvaluationSchema:
        words = candidate_answer.lower().split()
        total_words = len(words)

        if total_words < 6:
            return TechnicalEvaluationSchema(
                technical_score=35.0,
                correctness=40.0,
                relevance=50.0,
                completeness=25.0,
                depth=25.0,
                feedback="Response was very brief. Explaining underlying mechanisms and design decisions will improve the technical evaluation."
            )

        # Measure coverage of expected focus areas
        ans_lower = candidate_answer.lower()
        matched_focus = 0
        for focus in expected_focus:
            focus_words = focus.lower().split()
            if any(fw in ans_lower for fw in focus_words if len(fw) > 3):
                matched_focus += 1

        coverage_ratio = (matched_focus / max(len(expected_focus), 1))

        relevance = round(min(100.0, max(50.0, 60.0 + (coverage_ratio * 35.0))), 1)
        completeness = round(min(100.0, max(40.0, 45.0 + (coverage_ratio * 45.0) + min(15.0, total_words * 0.15))), 1)
        depth = round(min(100.0, max(40.0, 50.0 + min(40.0, total_words * 0.4))), 1)
        correctness = round(min(100.0, (relevance * 0.5) + (depth * 0.5)), 1)

        technical_score = round(
            (correctness * 0.35) + (relevance * 0.25) + (completeness * 0.20) + (depth * 0.20),
            1
        )

        feedback = (
            f"Addressed {matched_focus} of {len(expected_focus)} key conceptual areas. "
            "Good structural approach; incorporating specific trade-offs and runtime complexities will add further technical depth."
        )

        return TechnicalEvaluationSchema(
            technical_score=technical_score,
            correctness=correctness,
            relevance=relevance,
            completeness=completeness,
            depth=depth,
            feedback=feedback
        )
