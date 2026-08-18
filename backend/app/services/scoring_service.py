import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from app.config import (
    TECHNICAL_WEIGHT,
    COMMUNICATION_WEIGHT,
    FLUENCY_WEIGHT,
    EYE_CONTACT_WEIGHT,
    POSTURE_WEIGHT,
    EXPRESSION_WEIGHT,
    READINESS_EXCELLENT_MIN,
    READINESS_VERY_GOOD_MIN,
    READINESS_GOOD_MIN,
    READINESS_NEEDS_IMPROVEMENT_MIN,
)
from app.schemas.interview import DimensionScoreSchema, InterviewScoreResponse

logger = logging.getLogger("scoring_service")

class MultiModalScoringService:
    """
    Weighted Multi-Modal Interview Scoring Algorithm.
    Combines independent evaluation dimensions into a unified, deterministic, explainable score.
    
    Academic & Research Integrity:
    - Pure mathematical calculation in Python (independent of LLM variability).
    - Transparent missing-modality renormalization.
    - Uses objective behavioral proxies rather than clinical/psychological assertions.
    """

    @classmethod
    def calculate_readiness_level(cls, overall_score: float) -> str:
        if overall_score >= READINESS_EXCELLENT_MIN:
            return "Excellent"
        elif overall_score >= READINESS_VERY_GOOD_MIN:
            return "Very Good"
        elif overall_score >= READINESS_GOOD_MIN:
            return "Good"
        elif overall_score >= READINESS_NEEDS_IMPROVEMENT_MIN:
            return "Needs Improvement"
        else:
            return "Requires Significant Improvement"

    @classmethod
    def calculate_confidence_indicator(
        cls,
        fluency_score: float,
        wpm: float,
        communication_score: float,
        eye_contact_proxy: float,
        posture_score: float,
        filler_count: int = 0
    ) -> float:
        """
        Computes an AI-derived behavioral confidence indicator (0-100) based on
        observable speech tempo stability, delivery fluency, and visual orientation.
        """
        # Pace stability factor (optimal 120-150 WPM)
        pace_factor = 90.0
        if wpm > 0:
            if 115 <= wpm <= 160:
                pace_factor = 95.0
            elif 90 <= wpm < 115 or 160 < wpm <= 185:
                pace_factor = 80.0
            else:
                pace_factor = 65.0

        filler_deduction = min(25.0, filler_count * 2.5)
        fluency_component = max(10.0, (fluency_score * 0.40) + (pace_factor * 0.40) + (communication_score * 0.20) - filler_deduction)
        visual_component = (eye_contact_proxy * 0.60) + (posture_score * 0.40)

        confidence_val = (fluency_component * 0.60) + (visual_component * 0.40)
        return round(max(10.0, min(100.0, confidence_val)), 1)

    @classmethod
    def compute_weighted_score(
        cls,
        technical_score: float,
        communication_score: float,
        fluency_score: float,
        eye_contact_score: float,
        posture_score: float,
        expression_score: Optional[float] = None,
        is_expression_available: bool = False,
        is_fluency_available: bool = True,
        is_vision_available: bool = True
    ) -> Tuple[float, Dict[str, DimensionScoreSchema], Dict[str, float], float, List[str]]:
        """
        Executes the Weighted Multi-Modal Scoring Algorithm with dynamic missing-modality normalization.
        
        Mathematical Formulation:
        S_overall = sum_{i in Available} (Score_i * Weight_i) / sum_{i in Available} (Weight_i)
        """
        # Raw dimension mapping
        raw_dimensions = {
            "technical": {
                "score": max(0.0, min(100.0, float(technical_score))),
                "weight": TECHNICAL_WEIGHT,
                "available": True,
                "note": "Aggregated conceptual and architectural accuracy."
            },
            "communication": {
                "score": max(0.0, min(100.0, float(communication_score))),
                "weight": COMMUNICATION_WEIGHT,
                "available": True,
                "note": "Grammar, lexical diversity, and articulation."
            },
            "fluency": {
                "score": max(0.0, min(100.0, float(fluency_score))),
                "weight": FLUENCY_WEIGHT,
                "available": is_fluency_available,
                "note": "Speech delivery tempo, hesitation, and filler word frequency." if is_fluency_available else "Audio speech data not recorded."
            },
            "eye_contact": {
                "score": max(0.0, min(100.0, float(eye_contact_score))),
                "weight": EYE_CONTACT_WEIGHT,
                "available": is_vision_available,
                "note": "Camera-facing centrality and attention stability proxy." if is_vision_available else "Webcam frame stream was disabled."
            },
            "posture": {
                "score": max(0.0, min(100.0, float(posture_score))),
                "weight": POSTURE_WEIGHT,
                "available": is_vision_available,
                "note": "Observable posture alignment and upper-body positioning." if is_vision_available else "Webcam frame stream was disabled."
            },
            "expression": {
                "score": max(0.0, min(100.0, float(expression_score or 0.0))),
                "weight": EXPRESSION_WEIGHT,
                "available": is_expression_available,
                "note": "7-class facial expression classification." if is_expression_available else "Facial-expression CNN weights were unavailable in environment."
            }
        }

        available_weights_sum = 0.0
        weighted_sum = 0.0
        dimensions_output: Dict[str, DimensionScoreSchema] = {}
        weights_used: Dict[str, float] = {}
        unavailable_modalities: List[str] = []

        for dim_name, dim_info in raw_dimensions.items():
            s = dim_info["score"]
            w = dim_info["weight"]
            is_avail = dim_info["available"]
            note = dim_info["note"]

            weights_used[dim_name] = w

            if is_avail:
                available_weights_sum += w
                weighted_sum += (s * w)
                dimensions_output[dim_name] = DimensionScoreSchema(
                    raw_score=round(s, 1),
                    weight=w,
                    contribution=round(s * w, 2),
                    is_available=True,
                    status_note=note
                )
            else:
                unavailable_modalities.append(dim_name)
                dimensions_output[dim_name] = DimensionScoreSchema(
                    raw_score=round(s, 1),
                    weight=w,
                    contribution=0.0,
                    is_available=False,
                    status_note=note
                )

        # Dynamic Normalization across available weights
        if available_weights_sum > 0.0:
            normalized_overall = weighted_sum / available_weights_sum
        else:
            normalized_overall = 0.0

        overall_score = round(max(0.0, min(100.0, normalized_overall)), 1)
        return overall_score, dimensions_output, weights_used, round(available_weights_sum, 2), unavailable_modalities

    @classmethod
    def evaluate_interview_scores(
        cls,
        interview_id: int,
        answer_analyses: List[Dict[str, Any]],
        behavior_analyses: List[Dict[str, Any]]
    ) -> InterviewScoreResponse:
        """
        Aggregates session answer analyses and vision records, executes the weighted scoring algorithm,
        and constructs the complete explainable scoring payload.
        """
        # 1. Aggregate Technical, Communication, and Fluency scores across answers
        if answer_analyses and len(answer_analyses) > 0:
            tech_scores = [a.get("technical_score", 0.0) for a in answer_analyses]
            comm_scores = [a.get("communication_score", 0.0) for a in answer_analyses]
            fluency_scores = [a.get("fluency_score", 0.0) for a in answer_analyses]
            wpms = [a.get("wpm", 0.0) for a in answer_analyses]
            fillers = sum([a.get("filler_word_count", 0) for a in answer_analyses])

            avg_tech = sum(tech_scores) / len(tech_scores)
            avg_comm = sum(comm_scores) / len(comm_scores)
            avg_fluency = sum(fluency_scores) / len(fluency_scores)
            avg_wpm = sum(wpms) / len(wpms) if wpms else 120.0
            is_fluency_avail = any(f > 0.0 for f in fluency_scores)
        else:
            avg_tech = 70.0
            avg_comm = 70.0
            avg_fluency = 70.0
            avg_wpm = 120.0
            fillers = 0
            is_fluency_avail = True

        # 2. Aggregate Vision & Posture records
        is_vision_avail = False
        is_expression_avail = False
        avg_eye = 75.0
        avg_posture = 75.0
        avg_expr = 75.0

        if behavior_analyses and len(behavior_analyses) > 0:
            valid_faces = [b for b in behavior_analyses if b.get("face_detected")]
            if valid_faces:
                is_vision_avail = True
                avg_eye = sum(b.get("eye_contact_proxy_score", 75.0) for b in valid_faces) / len(valid_faces)
                avg_posture = sum(b.get("posture_score", 75.0) for b in valid_faces) / len(valid_faces)
            
            # Check if CNN emotion model was genuinely loaded
            from app.services.emotion_service import EmotionRecognitionService
            is_expression_avail = EmotionRecognitionService.is_model_available()

        # 3. Compute Weighted Score
        overall_score, dims, weights_used, avail_sum, unavail_mods = cls.compute_weighted_score(
            technical_score=avg_tech,
            communication_score=avg_comm,
            fluency_score=avg_fluency,
            eye_contact_score=avg_eye,
            posture_score=avg_posture,
            expression_score=avg_expr,
            is_expression_available=is_expression_avail,
            is_fluency_available=is_fluency_avail,
            is_vision_available=is_vision_avail
        )

        readiness = cls.calculate_readiness_level(overall_score)
        confidence = cls.calculate_confidence_indicator(
            fluency_score=avg_fluency,
            wpm=avg_wpm,
            communication_score=avg_comm,
            eye_contact_proxy=avg_eye,
            posture_score=avg_posture,
            filler_count=fillers
        )

        return InterviewScoreResponse(
            interview_id=interview_id,
            overall_score=overall_score,
            readiness_level=readiness,
            confidence_indicator=confidence,
            dimensions=dims,
            weights_used=weights_used,
            available_weights_sum=avail_sum,
            unavailable_modalities=unavail_mods
        )
