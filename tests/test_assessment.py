import pytest
import json

from navigator.services import NavigatorService


def _model_questions(mode: str) -> str:
    if mode == "mcq":
        return json.dumps({"questions": [
            {
                "question": f"Python model question {index}",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "explanation": "Technical explanation",
            }
            for index in range(10)
        ]})
    return json.dumps({"questions": [
        {
            "question": f"Explain Python model concept {index}",
            "expected_keywords": ["python", "concept", "example"],
            "explanation": "Technical explanation",
        }
        for index in range(10)
    ]})


def test_topic_clicks_generate_distinct_sets_without_counting_attempts(tmp_path):
    service = NavigatorService(str(tmp_path / "assessment.db"))
    student = service.login_student("arun@college.edu", "secret")
    service._llm_call = lambda messages: "{}"

    first = service.create_topic_assessment(student.student_id, "Python")
    second = service.create_topic_assessment(student.student_id, "Python")

    assert len(first["questions"]) == len(second["questions"]) == 10
    assert [q["question"] for q in first["questions"]] != [q["question"] for q in second["questions"]]
    assert first["attempt"] == second["attempt"] == 1

    answers = {q["question_id"]: q["correct_answer"] for q in first["questions"]}
    result = service.submit_topic_assessment(student.student_id, first["test_id"], answers)
    assert result["status"] == "submitted"
    next_test = service.create_topic_assessment(student.student_id, "Python")
    assert next_test["attempt"] == 2
    service.store.close()


def test_voice_evaluation_requires_keywords_context_and_confidence():
    question = {
        "question": "What is a Python dictionary used for?",
        "expected_keywords": ["key", "value", "lookup"],
    }

    strong = NavigatorService._evaluate_voice_answer(
        question, "A dictionary maps a key to a value for lookup.", 0.9
    )
    weak_confidence = NavigatorService._evaluate_voice_answer(
        question, "A dictionary maps a key to a value for lookup.", 0.2
    )
    vague = NavigatorService._evaluate_voice_answer(question, "It stores things.", 0.9)

    assert strong["is_correct"] is True
    assert weak_confidence["is_correct"] is False
    assert vague["is_correct"] is False


def test_docker_fallback_is_technical_and_unique(tmp_path):
    service = NavigatorService(str(tmp_path / "docker-assessment.db"))
    questions = service._topic_questions("Docker", 22)

    assert len(questions) == 10
    assert len({question.question for question in questions}) == 10
    assert all(question.skill == "Docker" for question in questions)
    assert all(len(question.options) == 4 and question.correct_answer in question.options for question in questions)
    service.store.close()


def test_docker_speakai_fallback_is_unique_without_set_label(tmp_path):
    service = NavigatorService(str(tmp_path / "docker-voice.db"))
    questions = service._fallback_topic_concept_questions("Docker", 22)
    mcqs = service._topic_questions("Docker", 22)

    assert len(questions) == 10
    assert len({question["question"] for question in questions}) == 10
    assert len({question.question for question in mcqs}) == 10
    assert all(not question.question.startswith("Set ") for question in mcqs)
    service.store.close()


def test_submitted_mcq_contains_answer_feedback(tmp_path):
    service = NavigatorService(str(tmp_path / "feedback.db"))
    student = service.login_student("arun@college.edu", "secret")
    service._llm_call = lambda messages, **kwargs: "{}"
    test = service.create_topic_assessment(student.student_id, "Docker")
    answers = {test["questions"][0]["question_id"]: test["questions"][0]["correct_answer"]}
    answers.update({question["question_id"]: "wrong" for question in test["questions"][1:]})

    result = service.submit_topic_assessment(student.student_id, test["test_id"], answers)

    assert len(result["feedback"]) == 10
    assert result["feedback"][0]["is_correct"] is True
    assert result["feedback"][0]["correct_answer"] == test["questions"][0]["correct_answer"]
    service.store.close()


def test_mcq_and_speakai_each_consume_fresh_model_generation(tmp_path):
    service = NavigatorService(str(tmp_path / "model-assessment.db"))
    student = service.login_student("arun@college.edu", "secret")
    calls = []

    def model(messages, **kwargs):
        calls.append(messages[-1]["content"])
        return _model_questions("voice" if "voice assessment" in messages[0]["content"] else "mcq")

    service._llm_call = model
    mcq = service.create_topic_assessment(student.student_id, "Python", "mcq")
    voice = service.create_topic_assessment(student.student_id, "Python", "voice_concept")

    assert len(calls) == 2
    assert "Topic: Python" in calls[0] and "Topic: Python" in calls[1]
    assert mcq["questions"][0]["options"] == ["A", "B", "C", "D"]
    assert voice["questions"][0]["expected_keywords"] == ["python", "concept", "example"]
    service.store.close()
