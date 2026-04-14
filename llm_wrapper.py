import requests
import re
import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/generate"
MODEL_NAME = "phi"


def summarize_text(text, num_sentences=3):
    prompt = f"""
You are a strict academic summarizer.

Return EXACTLY {num_sentences} sentences.
Do not add commentary.
Do not ask questions.
Do not continue the conversation.
Only output the summary.

Text:
{text}
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 200
        }
    }

    response = requests.post(OLLAMA_URL, json=payload)
    result = response.json()["response"].strip()

    # --- Hard clamp to exact number of sentences ---
    sentences = re.split(r'(?<=[.!?]) +', result)
    clamped = " ".join(sentences[:num_sentences])

    return clamped


if __name__ == "__main__":
    sample_text = """
    Artificial intelligence (AI) represents a transformative branch of computer science
    dedicated to creating systems capable of performing tasks that typically require
    human intelligence such as learning, reasoning, and decision-making.
    """

    summary = summarize_text(sample_text, 3)
    print("\n--- SUMMARY ---\n")
    print(summary)
