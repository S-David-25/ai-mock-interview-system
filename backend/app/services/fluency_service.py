import re
import logging
from typing import List, Dict, Any, Tuple
from app.schemas.interview import FluencyEvaluationSchema

logger = logging.getLogger("fluency_service")

# Standard speech performance filler words and multi-word disfluencies
FILLER_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(um+)\b", "um"),
    (r"\b(uh+)\b", "uh"),
    (r"\b(er+)\b", "er"),
    (r"\b(ah+)\b", "ah"),
    (r"\b(like)\b", "like"),
    (r"\b(actually)\b", "actually"),
    (r"\b(basically)\b", "basically"),
    (r"\b(you know)\b", "you know"),
    (r"\b(i mean)\b", "i mean"),
    (r"\b(sort of)\b", "sort of"),
    (r"\b(kind of)\b", "kind of"),
    (r"\b(literally)\b", "literally"),
    (r"\b(to be honest)\b", "to be honest"),
]

class FluencyService:
    """
    Speech performance evaluation analyzing speech tempo (WPM), hesitation patterns,
    filler frequency, and utterance continuity.
    
    Academic Note: This is an objective speech-performance metric and must NOT be used
    as a measure of candidate intelligence, personality, or psychological confidence.
    """

    @staticmethod
    def analyze_fluency(transcript: str, duration_seconds: float = 0.0) -> FluencyEvaluationSchema:
        if not transcript or not transcript.strip():
            return FluencyEvaluationSchema(
                fluency_score=0.0,
                wpm=0.0,
                speaking_duration=0.0,
                filler_word_count=0,
                filler_words=[],
                repeated_words=[]
            )

        text = transcript.strip()
        words = text.split()
        total_words = len(words)

        # Fallback duration if missing
        if duration_seconds <= 0.0:
            # Average normal speaking rate ~ 130 WPM (2.17 words/sec)
            duration_seconds = max(1.0, round(total_words / 2.17, 1))

        duration_minutes = max(duration_seconds / 60.0, 0.05)
        wpm = round(total_words / duration_minutes, 1)

        # 1. Detect filler words
        text_lower = text.lower()
        found_fillers: List[str] = []
        filler_count = 0

        for pattern, display in FILLER_PATTERNS:
            matches = re.findall(pattern, text_lower)
            if matches:
                count = len(matches)
                filler_count += count
                found_fillers.extend([display] * count)

        # 2. Detect immediate word repetitions (e.g. "we we", "the the")
        repeated_words: List[str] = []
        for i in range(len(words) - 1):
            w1 = re.sub(r'[^\w]', '', words[i].lower())
            w2 = re.sub(r'[^\w]', '', words[i+1].lower())
            if w1 and w2 and w1 == w2 and len(w1) > 1:
                repeated_words.append(w1)

        # 3. Calculate Fluency Score (0 - 100)
        # Optimal speaking rate is 120 - 160 WPM
        pace_penalty = 0.0
        if wpm < 90:
            pace_penalty = min(30.0, (90 - wpm) * 0.5)
        elif wpm > 180:
            pace_penalty = min(25.0, (wpm - 180) * 0.4)

        # Filler penalty: percentage of filler words
        filler_ratio = (filler_count / max(total_words, 1)) * 100.0
        filler_penalty = min(40.0, filler_ratio * 4.0)

        # Repetition penalty
        repeat_penalty = min(20.0, len(repeated_words) * 5.0)

        base_score = 95.0 - pace_penalty - filler_penalty - repeat_penalty
        fluency_score = round(max(10.0, min(100.0, base_score)), 1)

        return FluencyEvaluationSchema(
            fluency_score=fluency_score,
            wpm=wpm,
            speaking_duration=round(duration_seconds, 1),
            filler_word_count=filler_count,
            filler_words=found_fillers[:10],
            repeated_words=repeated_words[:5]
        )
