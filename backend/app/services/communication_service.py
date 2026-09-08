import re
import logging
from typing import Dict, Any
from app.schemas.interview import CommunicationEvaluationSchema
from app.services.gemini_service import GeminiService

logger = logging.getLogger("communication_service")

class CommunicationService:
    """
    Evaluates transcript for grammatical structure, vocabulary diversity,
    conciseness, clarity, and articulation.
    """

    @staticmethod
    async def evaluate_communication(transcript: str, question_context: str = "") -> CommunicationEvaluationSchema:
        if not transcript or not transcript.strip():
            return CommunicationEvaluationSchema(
                grammar_score=0.0,
                vocabulary_score=0.0,
                clarity_score=0.0,
                communication_score=0.0,
                feedback="No spoken transcript recorded to evaluate."
            )

        if GeminiService.is_configured():
            try:
                system_instruction = (
                    "You are a professional communication and linguistic assessment evaluator.\n"
                    "Evaluate the candidate's spoken response on:\n"
                    "1. Grammar and sentence correctness (0-100)\n"
                    "2. Vocabulary richness and professional phrasing (0-100)\n"
                    "3. Clarity and articulation (0-100)\n"
                    "Return constructive feedback and strict JSON numbers between 0 and 100."
                )
                prompt = (
                    f"Interview Question Context: {question_context}\n\n"
                    f"Candidate Transcript:\n\"{transcript}\"\n\n"
                    f"Required JSON structure:\n"
                    f"{{\n"
                    f'  "grammar_score": 85.0,\n'
                    f'  "vocabulary_score": 80.0,\n'
                    f'  "clarity_score": 88.0,\n'
                    f'  "communication_score": 84.3,\n'
                    f'  "feedback": "Concise analysis of communication strengths and actionable tips."\n'
                    f"}}"
                )
                result = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.2,
                    purpose="Communication Evaluation"
                )
                g_score = max(0.0, min(100.0, float(result.get("grammar_score", 75.0))))
                v_score = max(0.0, min(100.0, float(result.get("vocabulary_score", 75.0))))
                c_score = max(0.0, min(100.0, float(result.get("clarity_score", 75.0))))
                comm_score = max(0.0, min(100.0, float(result.get("communication_score", (g_score + v_score + c_score) / 3.0))))

                return CommunicationEvaluationSchema(
                    grammar_score=round(g_score, 1),
                    vocabulary_score=round(v_score, 1),
                    clarity_score=round(c_score, 1),
                    communication_score=round(comm_score, 1),
                    feedback=result.get("feedback", "Good professional articulation.")
                )
            except Exception as e:
                logger.warning(f"Gemini communication eval failed ({e}). Using NLP evaluator.")

        return CommunicationService._deterministic_eval(transcript)

    @staticmethod
    def _deterministic_eval(transcript: str) -> CommunicationEvaluationSchema:
        words = transcript.strip().split()
        total_words = len(words)

        if total_words < 5:
            return CommunicationEvaluationSchema(
                grammar_score=50.0,
                vocabulary_score=45.0,
                clarity_score=50.0,
                communication_score=48.3,
                feedback="Response was very brief. Elaborating with structured examples will strengthen communication impact."
            )

        # Unique vocabulary ratio
        unique_words = len(set([w.lower() for w in words]))
        lexical_diversity = (unique_words / total_words)

        # Average word length
        avg_word_len = sum(len(w) for w in words) / total_words

        # Scores calculation
        vocab_score = round(min(100.0, max(40.0, 50.0 + (lexical_diversity * 40.0) + (avg_word_len * 3.0))), 1)
        grammar_score = 85.0
        if re.search(r'\b(i is|they is|he are|we was|dont got)\b', transcript.lower()):
            grammar_score -= 15.0

        clarity_score = round(min(100.0, max(50.0, 70.0 + min(25.0, total_words * 0.4))), 1)
        comm_score = round((grammar_score * 0.35) + (vocab_score * 0.35) + (clarity_score * 0.30), 1)

        feedback = (
            f"Demonstrated good verbal articulation with a lexical diversity of {int(lexical_diversity * 100)}%. "
            "Continuing to use precise domain terminology will further elevate clarity."
        )

        return CommunicationEvaluationSchema(
            grammar_score=grammar_score,
            vocabulary_score=vocab_score,
            clarity_score=clarity_score,
            communication_score=comm_score,
            feedback=feedback
        )
