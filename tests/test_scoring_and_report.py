import unittest
from app.schemas.interview import (
    InterviewScoreResponse,
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
)
from app.services.scoring_service import MultiModalScoringService
from app.services.roadmap_service import PersonalizedRoadmapService
from app.services.progress_service import ProgressAnalyticsService

class TestScoringAndReportLogic(unittest.TestCase):

    def test_01_exact_mathematical_scoring_formula(self):
        """
        Exact test specified in prompt:
        T=80, C=75, F=70, E=85, P=80, X=72
        Weights: 0.40, 0.20, 0.15, 0.10, 0.10, 0.05
        80(0.40) + 75(0.20) + 70(0.15) + 85(0.10) + 80(0.10) + 72(0.05)
        = 32.0 + 15.0 + 10.5 + 8.5 + 8.0 + 3.6 = 77.6
        """
        overall, dims, weights, avail_sum, unavail = MultiModalScoringService.compute_weighted_score(
            technical_score=80.0,
            communication_score=75.0,
            fluency_score=70.0,
            eye_contact_score=85.0,
            posture_score=80.0,
            expression_score=72.0,
            is_expression_available=True,
            is_fluency_available=True,
            is_vision_available=True
        )

        self.assertEqual(overall, 77.6)
        self.assertEqual(avail_sum, 1.0)
        self.assertEqual(len(unavail), 0)
        self.assertEqual(dims["technical"].contribution, 32.0)
        self.assertEqual(dims["communication"].contribution, 15.0)
        self.assertEqual(dims["fluency"].contribution, 10.5)
        self.assertEqual(dims["eye_contact"].contribution, 8.5)
        self.assertEqual(dims["posture"].contribution, 8.0)
        self.assertEqual(dims["expression"].contribution, 3.6)

    def test_02_missing_modality_normalization(self):
        """
        Missing modality test:
        T=80, C=75, F=70, E=85, P=80, Expression is unavailable.
        Available weights sum = 0.95
        Weighted sum = 74.0
        Normalized score = 74.0 / 0.95 = 77.8947... -> 77.9
        """
        overall, dims, weights, avail_sum, unavail = MultiModalScoringService.compute_weighted_score(
            technical_score=80.0,
            communication_score=75.0,
            fluency_score=70.0,
            eye_contact_score=85.0,
            posture_score=80.0,
            expression_score=0.0,
            is_expression_available=False,
            is_fluency_available=True,
            is_vision_available=True
        )

        self.assertEqual(overall, 77.9)
        self.assertEqual(avail_sum, 0.95)
        self.assertIn("expression", unavail)
        self.assertFalse(dims["expression"].is_available)
        self.assertEqual(dims["expression"].contribution, 0.0)

    def test_03_readiness_level_thresholds(self):
        self.assertEqual(MultiModalScoringService.calculate_readiness_level(95.0), "Excellent")
        self.assertEqual(MultiModalScoringService.calculate_readiness_level(84.0), "Very Good")
        self.assertEqual(MultiModalScoringService.calculate_readiness_level(73.0), "Good")
        self.assertEqual(MultiModalScoringService.calculate_readiness_level(65.0), "Needs Improvement")
        self.assertEqual(MultiModalScoringService.calculate_readiness_level(52.0), "Requires Significant Improvement")

    def test_04_confidence_indicator_calculation(self):
        conf = MultiModalScoringService.calculate_confidence_indicator(
            fluency_score=85.0,
            wpm=135.0,
            communication_score=82.0,
            eye_contact_proxy=88.0,
            posture_score=85.0,
            filler_count=1
        )
        self.assertGreaterEqual(conf, 70.0)
        self.assertLessEqual(conf, 100.0)

    def test_05_personalized_5_phase_roadmap(self):
        score_resp = InterviewScoreResponse(
            interview_id=1,
            overall_score=78.0,
            readiness_level="Good",
            confidence_indicator=76.0,
            dimensions={},
            weights_used={},
            available_weights_sum=1.0,
            unavailable_modalities=[]
        )
        skill_match = SkillMatchSchema(
            matched_skills=["Python", "FastAPI"],
            skill_gaps=["Spring Boot", "Kafka"],
            priority_skills=["Spring Boot"],
            match_percentage=65.0
        )

        roadmap = PersonalizedRoadmapService.generate_roadmap(
            interview_id=1,
            user_id=42,
            score_data=score_resp,
            skill_match=skill_match,
            weaknesses=["Needs deeper system design knowledge"],
            job_role="Backend Developer"
        )

        self.assertEqual(len(roadmap.phases), 5)
        self.assertIn("Phase 1", roadmap.phases[0].phase_title)
        self.assertIn("Phase 2", roadmap.phases[1].phase_title)
        self.assertIn("Phase 3", roadmap.phases[2].phase_title)
        self.assertIn("Phase 4", roadmap.phases[3].phase_title)
        self.assertIn("Phase 5", roadmap.phases[4].phase_title)

        # Verify skill gap is integrated into technical phase
        phase2_items = roadmap.phases[1].items
        self.assertTrue(any("Spring Boot" in item.area for item in phase2_items))

if __name__ == "__main__":
    unittest.main()
