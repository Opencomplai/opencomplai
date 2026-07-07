import openai
from fastapi import APIRouter

router = APIRouter()

client = openai.Client()


def chat(user_message: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_message}],
    )
    return response.choices[0].message.content


def score_applicant(features):
    import joblib

    model = joblib.load("model.pkl")
    return model.predict_proba(features)
