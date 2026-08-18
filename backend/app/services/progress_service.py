import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from app.database.session import DatabaseSession
from app.schemas.interview import (
    ProgressResponse,
    ProgressTrendPointSchema,
    CategoryTrendSchema,
    InterviewComparisonResponse,
    DimensionComparisonSchema
)

logger = logging.getLogger("progress_service")

class ProgressAnalyticsService:
    """
    Tracks historical interview performance metrics, trend trajectories,
    and side-by-side interview comparisons for student placement preparation.
    """

    @classmethod
    def get_user_progress(cls, db: DatabaseSession, user_id: int) -> ProgressResponse:
        # Fetch all completed interviews with scores for user, ordered chronologically
        rows = db.fetchall(
            """
            SELECT i.id, i.interview_type, i.company_name, i.overall_score, i.created_at,
                   s.technical_score, s.communication_score, s.fluency_score, s.confidence_indicator
            FROM interviews i
            LEFT JOIN interview_scores s ON i.id = s.interview_id
            WHERE i.user_id = ? AND i.overall_score IS NOT NULL
            ORDER BY i.id ASC
            """,
            (user_id,)
        )

        if not rows:
            return ProgressResponse(
                interview_count=0,
                average_score=None,
                best_score=None,
                latest_score=None,
                total_score_improvement=None,
                trend_data=[],
                category_trends=[]
            )

        trend_data: List[ProgressTrendPointSchema] = []
        scores = []

        for r in rows:
            sc = float(r["overall_score"] or 0.0)
            scores.append(sc)
            trend_data.append(
                ProgressTrendPointSchema(
                    interview_id=r["id"],
                    date=r["created_at"] or "",
                    interview_type=r["interview_type"],
                    company_name=r["company_name"],
                    overall_score=round(sc, 1),
                    technical_score=round(float(r["technical_score"] or sc), 1),
                    communication_score=round(float(r["communication_score"] or sc), 1),
                    fluency_score=round(float(r["fluency_score"] or sc), 1),
                    confidence_indicator=round(float(r["confidence_indicator"] or sc), 1),
                )
            )

        interview_count = len(scores)
        avg_score = round(sum(scores) / interview_count, 1)
        best_score = round(max(scores), 1)
        latest_score = round(scores[-1], 1)
        
        total_improvement = round(scores[-1] - scores[0], 1) if interview_count > 1 else 0.0

        # Compute Category Trends (Initial vs Latest)
        category_trends: List[CategoryTrendSchema] = []
        if trend_data:
            first = trend_data[0]
            last = trend_data[-1]

            cats = [
                ("Overall Score", first.overall_score, last.overall_score),
                ("Technical Knowledge", first.technical_score, last.technical_score),
                ("Communication", first.communication_score, last.communication_score),
                ("Fluency", first.fluency_score, last.fluency_score),
                ("Confidence Indicator", first.confidence_indicator, last.confidence_indicator),
            ]

            for name, init_val, last_val in cats:
                category_trends.append(
                    CategoryTrendSchema(
                        category_name=name,
                        initial_score=init_val,
                        latest_score=last_val,
                        delta=round(last_val - init_val, 1)
                    )
                )

        return ProgressResponse(
            interview_count=interview_count,
            average_score=avg_score,
            best_score=best_score,
            latest_score=latest_score,
            total_score_improvement=total_improvement,
            trend_data=trend_data,
            category_trends=category_trends
        )

    @classmethod
    def compare_interviews(
        cls,
        db: DatabaseSession,
        user_id: int,
        first_id: int,
        second_id: int
    ) -> InterviewComparisonResponse:
        # Fetch both interviews and ensure user owns both
        r1 = db.fetchone(
            """
            SELECT i.id, i.created_at, i.overall_score,
                   s.technical_score, s.communication_score, s.fluency_score,
                   s.eye_contact_score, s.posture_score, s.confidence_indicator
            FROM interviews i
            LEFT JOIN interview_scores s ON i.id = s.interview_id
            WHERE i.id = ? AND i.user_id = ?
            """,
            (first_id, user_id)
        )
        r2 = db.fetchone(
            """
            SELECT i.id, i.created_at, i.overall_score,
                   s.technical_score, s.communication_score, s.fluency_score,
                   s.eye_contact_score, s.posture_score, s.confidence_indicator
            FROM interviews i
            LEFT JOIN interview_scores s ON i.id = s.interview_id
            WHERE i.id = ? AND i.user_id = ?
            """,
            (second_id, user_id)
        )

        if not r1 or not r2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both interview sessions not found or you do not have permission to compare them."
            )

        o1 = float(r1["overall_score"] or 0.0)
        o2 = float(r2["overall_score"] or 0.0)
        overall_delta = round(o2 - o1, 1)

        dim_specs = [
            ("Technical Knowledge", float(r1["technical_score"] or o1), float(r2["technical_score"] or o2)),
            ("Communication", float(r1["communication_score"] or o1), float(r2["communication_score"] or o2)),
            ("Fluency", float(r1["fluency_score"] or o1), float(r2["fluency_score"] or o2)),
            ("Eye Contact Proxy", float(r1["eye_contact_score"] or 75.0), float(r2["eye_contact_score"] or 75.0)),
            ("Posture & Professional Behaviour", float(r1["posture_score"] or 75.0), float(r2["posture_score"] or 75.0)),
            ("Confidence Indicator", float(r1["confidence_indicator"] or o1), float(r2["confidence_indicator"] or o2)),
        ]

        dim_comparisons: List[DimensionComparisonSchema] = []
        improved: List[str] = []
        declined: List[str] = []
        unchanged: List[str] = []

        for name, val1, val2 in dim_specs:
            d = round(val2 - val1, 1)
            if d > 0:
                stat = "Improved"
                improved.append(f"{name} (+{d}%)")
            elif d < 0:
                stat = "Declined"
                declined.append(f"{name} ({d}%)")
            else:
                stat = "Unchanged"
                unchanged.append(name)

            dim_comparisons.append(
                DimensionComparisonSchema(
                    dimension_name=name,
                    first_score=round(val1, 1),
                    second_score=round(val2, 1),
                    delta=d,
                    status=stat
                )
            )

        overall_status = "Improved" if overall_delta > 0 else ("Declined" if overall_delta < 0 else "Unchanged")

        return InterviewComparisonResponse(
            first_interview_id=first_id,
            first_interview_date=r1["created_at"] or "",
            first_overall_score=round(o1, 1),
            second_interview_id=second_id,
            second_interview_date=r2["created_at"] or "",
            second_overall_score=round(o2, 1),
            overall_delta=overall_delta,
            overall_status=overall_status,
            dimension_comparisons=dim_comparisons,
            improved_areas=improved,
            declined_areas=declined,
            unchanged_areas=unchanged
        )
