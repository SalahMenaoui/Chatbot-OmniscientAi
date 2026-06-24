"""
qa_test.py
Sends a list of test questions to the chatbot's system prompt via Claude API
and logs responses for manual review.

Usage:
    python tools/qa_test.py <client_name> [questions_file]

Example:
    python tools/qa_test.py acme_bakery
    python tools/qa_test.py acme_bakery custom_questions.txt

If no questions_file is provided, uses the default test suite below.

Reads:
  - clients/<client_name>/chatbot/config.json  (for system prompt)

Writes:
  - clients/<client_name>/qa_results.json
  - clients/<client_name>/qa_results.md   (human-readable)

Requires: ANTHROPIC_API_KEY in .env
"""

import sys
import json
import os
from datetime import datetime

try:
    import anthropic
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install anthropic python-dotenv")
    sys.exit(1)


load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

DEFAULT_QUESTIONS = [
    "What services do you offer?",
    "What are your opening hours?",
    "How much does it cost?",
    "Where are you located?",
    "How can I contact you?",
    "Do you have any promotions or discounts?",
    "Can I book an appointment online?",
    "What payment methods do you accept?",
    "Do you offer delivery or shipping?",
    "Tell me something completely unrelated to your business.",  # Should politely deflect
]


def run(client_name: str, questions_file: str | None = None) -> None:
    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client_dir  = os.path.join("clients", client_name)
    config_path = os.path.join(client_dir, "chatbot", "config.json")

    if not os.path.exists(config_path):
        print(f"ERROR: {config_path} not found. Run inject_prompt.py first.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    system_prompt = config.get("systemPrompt", "You are a helpful assistant.")
    bot_name      = config.get("botName", client_name)

    # Load questions
    if questions_file and os.path.exists(questions_file):
        with open(questions_file, "r", encoding="utf-8") as f:
            questions = [line.strip() for line in f if line.strip()]
    else:
        questions = DEFAULT_QUESTIONS

    print(f"[qa_test] Testing chatbot for: {client_name} ({bot_name})")
    print(f"  {len(questions)} questions to test. This will use API credits.")

    client   = anthropic.Anthropic(api_key=API_KEY)
    results  = []
    passed   = 0
    failed   = 0

    for i, question in enumerate(questions, 1):
        print(f"  [{i}/{len(questions)}] {question[:60]}...")
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",   # Use cheaper model for QA
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": question}],
            )
            answer = message.content[0].text.strip()
            results.append({
                "question": question,
                "answer":   answer,
                "status":   "ok",
                "tokens":   message.usage.output_tokens,
            })
            passed += 1
        except Exception as e:
            results.append({
                "question": question,
                "answer":   "",
                "status":   "error",
                "error":    str(e),
            })
            failed += 1
            print(f"    ERROR: {e}")

    # Save JSON results
    output = {
        "client":     client_name,
        "bot_name":   bot_name,
        "timestamp":  datetime.utcnow().isoformat(),
        "total":      len(questions),
        "passed":     passed,
        "failed":     failed,
        "results":    results,
    }

    json_path = os.path.join(client_dir, "qa_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Save readable markdown report
    md_path = os.path.join(client_dir, "qa_results.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# QA Results — {bot_name}\n\n")
        f.write(f"**Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  \n")
        f.write(f"**Results:** {passed}/{len(questions)} OK\n\n")
        f.write("---\n\n")
        for r in results:
            status_icon = "✅" if r["status"] == "ok" else "❌"
            f.write(f"### {status_icon} {r['question']}\n\n")
            if r["status"] == "ok":
                f.write(f"{r['answer']}\n\n")
            else:
                f.write(f"**ERROR:** {r.get('error', 'Unknown error')}\n\n")
            f.write("---\n\n")

    print(f"[qa_test] Done. {passed}/{len(questions)} passed.")
    print(f"  Results: {md_path}")

    if failed > 0:
        print(f"  WARNING: {failed} question(s) failed. Review qa_results.md.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/qa_test.py <client_name> [questions_file]")
        sys.exit(1)
    questions_file = sys.argv[2] if len(sys.argv) > 2 else None
    run(sys.argv[1], questions_file)
