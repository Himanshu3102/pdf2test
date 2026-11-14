"""Create a clean demo exam so the GATE-style UI has realistic content.

Run from the backend directory:
    python seed_demo_exam.py
"""

from app.db import SessionLocal
from app.models import Exam, Question

SETTINGS = {
    "mode": "exam",
    "duration_minutes": 180,
    "marking": {
        "correct": 1.0,
        "incorrect": -0.33,
        "unanswered": 0.0,
        "partial_credit": False,
    },
    "allow_hints": False,
}

QUESTIONS = [
    {
        "qtype": "single_choice",
        "prompt": "A jar contains three marbles numbered 1, 2, and 3. If two marbles are drawn without replacement, what is the probability that the sum of the numbers is 5?",
        "options": [
            {"id": "A", "text": "1/6"},
            {"id": "B", "text": "1/3"},
            {"id": "C", "text": "1/2"},
            {"id": "D", "text": "2/3"},
        ],
        "answer_key": "B",
        "explanation": "The possible draws are (1,2), (1,3), (2,1), (2,3), (3,1), (3,2). Two of them, (2,3) and (3,2), sum to 5, so P = 2/6 = 1/3.",
        "points": 1.0,
        "negative_points": -0.33,
        "topic_tags": ["General Aptitude", "Probability"],
    },
    {
        "qtype": "single_choice",
        "prompt": "Two fair dice are rolled. What is the probability that the sum of the faces is 7?",
        "options": [
            {"id": "A", "text": "1/12"},
            {"id": "B", "text": "1/6"},
            {"id": "C", "text": "5/36"},
            {"id": "D", "text": "7/36"},
        ],
        "answer_key": "B",
        "explanation": "There are 6 favourable outcomes out of 36: (1,6), (2,5), (3,4), (4,3), (5,2), (6,1). P = 6/36 = 1/6.",
        "points": 1.0,
        "negative_points": -0.33,
        "topic_tags": ["General Aptitude", "Probability"],
    },
    {
        "qtype": "single_choice",
        "prompt": "Three fair coins are tossed together. What is the probability of getting exactly two heads?",
        "options": [
            {"id": "A", "text": "1/8"},
            {"id": "B", "text": "1/4"},
            {"id": "C", "text": "3/8"},
            {"id": "D", "text": "1/2"},
        ],
        "answer_key": "C",
        "explanation": "Exactly two heads occur in HHT, HTH and THH — 3 of the 8 equally likely outcomes, so P = 3/8.",
        "points": 2.0,
        "negative_points": -0.66,
        "topic_tags": ["Probability"],
    },
    {
        "qtype": "multiple_select",
        "prompt": "A and B are two events such that P(A) = 0.5 and P(B) = 0.3. Which of the following statements are correct if A and B are mutually exclusive?",
        "options": [
            {"id": "A", "text": "P(A ∩ B) = 0"},
            {"id": "B", "text": "P(A ∪ B) = 0.8"},
            {"id": "C", "text": "P(A ∩ B) = 0.15"},
            {"id": "D", "text": "P(neither A nor B) = 0.2"},
        ],
        "answer_key": ["A", "B", "D"],
        "explanation": "Mutually exclusive events cannot occur together, so P(A ∩ B) = 0. Then P(A ∪ B) = 0.8 and P(neither) = 1 − 0.8 = 0.2.",
        "points": 2.0,
        "negative_points": 0.0,
        "topic_tags": ["Data Science and AI", "Probability"],
    },
    {
        "qtype": "numeric",
        "prompt": "A test for a disease is 99% accurate in both directions, and 0.3% of the population has the disease. If a person tests positive, what is the probability that they actually have the disease? Give your answer as a decimal rounded to three places.",
        "options": [],
        "answer_key": 0.229,
        "explanation": "By Bayes' theorem: P(D|+) = (0.99 × 0.003) / (0.99 × 0.003 + 0.01 × 0.997) ≈ 0.229.",
        "points": 2.0,
        "negative_points": 0.0,
        "tolerance": 0.01,
        "topic_tags": ["Data Science and AI", "Probability"],
    },
    {
        "qtype": "single_choice",
        "prompt": "In how many ways can the letters of the word REGULATIONS be arranged so that there are exactly four letters between R and E?",
        "options": [
            {"id": "A", "text": "6/55"},
            {"id": "B", "text": "3/55"},
            {"id": "C", "text": "49/55"},
            {"id": "D", "text": "None of these"},
        ],
        "answer_key": "A",
        "explanation": "There are 11 letters and hence 11! arrangements. R and E can occupy six pairs of positions, in either order, with the remaining 9 letters arranged in 9! ways. The required probability is (2 × 6 × 9!) / 11! = 6/55.",
        "points": 1.0,
        "negative_points": -0.33,
        "topic_tags": ["General Aptitude", "Combinatorics"],
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        exam = Exam(
            title="DA Data Science and Artificial Intelligence Mock",
            instructions=(
                "The test contains 6 questions and has a total duration of 180 minutes. "
                "Questions 1, 2, 3 and 6 are MCQ; question 4 is MSQ; question 5 is NAT. "
                "Use the question palette on the right to navigate between questions."
            ),
            status="published",
            settings=SETTINGS,
            settings_confirmed=True,
        )
        db.add(exam)
        db.flush()
        for idx, data in enumerate(QUESTIONS):
            db.add(
                Question(
                    exam_id=exam.id,
                    order_index=idx,
                    review_status="approved",
                    **data,
                )
            )
        db.commit()
        print(exam.id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
