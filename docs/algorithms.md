# AI Mock Interview System – Algorithms, Mathematical Formulations & Academic Models

This document presents the complete mathematical formulations, algorithmic logic, and evaluation metrics for the **Weighted Multi-Modal Interview Scoring Algorithm** and its supporting sub-systems.

---

## 1. Algorithmic Overview & Responsibility Separation

| Subsystem | Nature | Method / Formulation | Module |
|---|---|---|---|
| **Skill Matching & Gap Analysis** | Deterministic Algorithmic | Alias normalization + Set intersection & Jaccard overlap | `matching_service.py` |
| **Speech Fluency & WPM** | Statistical NLP | Tempo ratio + Disfluency penalty function | `fluency_service.py` |
| **Communication Scoring** | Linguistic Analysis | Lexical diversity + Syntactic structure analysis | `communication_service.py` |
| **Technical Correctness & Depth** | Semantic Evaluation | Concept coverage + Trade-off depth scoring | `answer_evaluation_service.py` |
| **Eye-Contact Proxy Metric** | Geometric Computer Vision | Face bounding box centrality & aspect ratio | `vision_service.py` |
| **Posture Evaluation** | Geometric Computer Vision | Vertical scale & alignment proxy | `vision_service.py` |
| **Facial Expression Classifier** | Deep Learning CNN | 7-class FER2013 convolution pipeline | `emotion_service.py` |
| **Weighted Multi-Modal Scoring** | Deterministic Optimization | Available-weight normalized multi-criteria weighting | `scoring_service.py` |
| **Progress Trend Trajectory** | Longitudinal Statistical | Chronological regression and dimension delta tracking | `progress_service.py` |
| **Personalized Roadmap Prioritization** | Multi-Phase Heuristic | Skill-gap and weakness priority matrix | `roadmap_service.py` |

---

## 2. Weighted Multi-Modal Interview Scoring Algorithm

### 2.1 Theoretical Formulation
The primary scoring algorithm integrates six independent dimensions of interview performance:

1. **Technical Knowledge ($T$)**: Default weight $w_T = 0.40$ (40%)
2. **Communication ($C$)**: Default weight $w_C = 0.20$ (20%)
3. **Fluency ($F$)**: Default weight $w_F = 0.15$ (15%)
4. **Eye-Contact Proxy ($E$)**: Default weight $w_E = 0.10$ (10%)
5. **Posture & Professional Behaviour ($P$)**: Default weight $w_P = 0.10$ (10%)
6. **Facial Expression / Behavioural Stability ($X$)**: Default weight $w_X = 0.05$ (5%)

Total standard weight: $\sum_{i \in \text{All}} w_i = 0.40 + 0.20 + 0.15 + 0.10 + 0.10 + 0.05 = 1.00$ (100%).

### 2.2 Missing-Modality Normalization Formula
When a physical modality or model is unavailable in the environment (e.g. Webcam disabled by student, or FER2013 CNN weights missing), the score is calculated by dynamically normalizing across the subset of available modalities $\mathcal{A} \subseteq \{T, C, F, E, P, X\}$:

$$\text{Overall Score } S_{overall} = \frac{\sum_{i \in \mathcal{A}} \left( S_i \times w_i \right)}{\sum_{i \in \mathcal{A}} w_i}$$

Where:
- $S_i \in [0, 100]$ is the measured score for dimension $i$.
- $w_i$ is the assigned weight for dimension $i$.
- $\sum_{i \in \mathcal{A}} w_i$ is the sum of weights for available modalities.

This ensures that technical environment unavailability never unfairly penalizes the student.

---

### 2.3 Comprehensive Numerical Example

#### Full 6-Modality Session:
- Technical Knowledge: $T = 80$
- Communication: $C = 75$
- Fluency: $F = 70$
- Eye-Contact Proxy: $E = 85$
- Posture: $P = 80$
- Facial Expression: $X = 72$

$$\begin{aligned}
S_{overall} &= (80 \times 0.40) + (75 \times 0.20) + (70 \times 0.15) + (85 \times 0.10) + (80 \times 0.10) + (72 \times 0.05) \\
&= 32.0 + 15.0 + 10.5 + 8.5 + 8.0 + 3.6 \\
&= \mathbf{77.6} \quad (\text{Readiness Level: Good})
\end{aligned}$$

#### Missing Facial Expression Modality Session:
- $T = 80, C = 75, F = 70, E = 85, P = 80$
- Facial Expression ($X$): *Unavailable* ($\text{Weight} = 0.05$)
- Available Weights Sum: $\sum_{i \in \mathcal{A}} w_i = 0.40 + 0.20 + 0.15 + 0.10 + 0.10 = 0.95$

$$\begin{aligned}
\text{Raw Weighted Sum} &= (80 \times 0.40) + (75 \times 0.20) + (70 \times 0.15) + (85 \times 0.10) + (80 \times 0.10) \\
&= 32.0 + 15.0 + 10.5 + 8.5 + 8.0 = 74.0 \\
S_{overall} &= \frac{74.0}{0.95} \approx \mathbf{77.9} \quad (\text{Readiness Level: Good})
\end{aligned}$$

---

## 3. Interview Readiness Level Classification

The final numerical score ($0–100$) maps to student placement readiness tiers:

$$\text{Readiness Level} = \begin{cases} 
\text{Excellent} & \text{if } S_{overall} \ge 90.0 \\
\text{Very Good} & \text{if } 80.0 \le S_{overall} < 90.0 \\
\text{Good} & \text{if } 70.0 \le S_{overall} < 80.0 \\
\text{Needs Improvement} & \text{if } 60.0 \le S_{overall} < 70.0 \\
\text{Requires Significant Improvement} & \text{if } S_{overall} < 60.0 
\end{cases}$$

---

## 4. Behavioral Confidence Indicator

Formulated as an AI-derived behavioral metric based on observable vocal pacing stability, lexical continuity, and visual orientation:

$$\text{Confidence Indicator} = 0.60 \times S_{\text{vocal\_stability}} + 0.40 \times S_{\text{visual\_orientation}}$$

Where:
- $S_{\text{vocal\_stability}} = (0.40 \times S_{\text{fluency}}) + (0.40 \times S_{\text{pace\_factor}}) + (0.20 \times S_{\text{comm}}) - P_{\text{filler}}$
- $S_{\text{visual\_orientation}} = (0.60 \times S_{\text{eye\_contact}}) + (0.40 \times S_{\text{posture}})$

*Academic Note: This is an observable behavioral indicator and does NOT constitute a clinical psychological assessment.*

---

## 5. Technology Alias Normalization & Jaccard Skill Matching

Given candidate normalized skill set $C$ and job description normalized requirement set $J$:
$$\text{Matched Skills } M = C \cap J$$
$$\text{Skill Gaps } G = J \setminus C$$
$$\text{Jaccard Similarity } J(C, J) = \frac{|C \cap J|}{|C \cup J|}$$
$$\text{Match Percentage} = \min\left(100.0, \frac{|M|}{\max(|J|, 1)} \times 100\right)$$

---

## 6. Longitudinal Progress Trend & Delta Tracking

For multiple completed sessions ordered chronologically: $I_1, I_2, \dots, I_N$:
$$\text{Overall Improvement } \Delta = S_{overall}(I_N) - S_{overall}(I_1)$$
$$\text{Session-over-Session Delta } \Delta_{recent} = S_{overall}(I_N) - S_{overall}(I_{N-1})$$
$$\text{Dimension Delta } \Delta_{dim} = S_{dim}(I_N) - S_{dim}(I_1)$$
$$\text{Trajectory Classification} = \begin{cases} \text{Improved} & \text{if } \Delta > 0 \\ \text{Declined} & \text{if } \Delta < 0 \\ \text{Unchanged} & \text{if } \Delta = 0 \end{cases}$$
