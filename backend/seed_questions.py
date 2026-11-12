import asyncio
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Subject, Question, ExamCategory, Difficulty

QUESTIONS = [
    {
        "text": "Solve for x: 2x + 5 = 15",
        "options": [{"key": "A", "text": "5"}, {"key": "B", "text": "10"}, {"key": "C", "text": "15"}, {"key": "D", "text": "20"}],
        "correct": "A",
        "explanation": "2x = 15 - 5 => 2x = 10 => x = 5."
    },
    {
        "text": "What is the value of 3! (3 factorial)?",
        "options": [{"key": "A", "text": "3"}, {"key": "B", "text": "6"}, {"key": "C", "text": "9"}, {"key": "D", "text": "12"}],
        "correct": "B",
        "explanation": "3! = 3 × 2 × 1 = 6."
    },
    {
        "text": "Convert 45 (base 10) to base 2.",
        "options": [{"key": "A", "text": "101101"}, {"key": "B", "text": "110011"}, {"key": "C", "text": "111000"}, {"key": "D", "text": "100101"}],
        "correct": "A",
        "explanation": "Divide by 2 repeatedly: 45 = 101101 in binary."
    },
    {
        "text": "If a triangle has angles 90°, 45°, and x, what is x?",
        "options": [{"key": "A", "text": "30°"}, {"key": "B", "text": "45°"}, {"key": "C", "text": "60°"}, {"key": "D", "text": "90°"}],
        "correct": "B",
        "explanation": "Sum of angles in a triangle is 180°. 180 - 90 - 45 = 45."
    },
    {
        "text": "What is the probability of rolling a 3 on a standard 6-sided die?",
        "options": [{"key": "A", "text": "1/2"}, {"key": "B", "text": "1/3"}, {"key": "C", "text": "1/6"}, {"key": "D", "text": "1/4"}],
        "correct": "C",
        "explanation": "There is only one '3' out of six possible numbers. So, 1/6."
    }
]

async def main():
    async with SessionLocal() as db:
        # Find Mathematics subject
        math = await db.scalar(select(Subject).where(Subject.slug == "mathematics"))
        if not math:
            print("Mathematics subject not found. Did you run seed.py?")
            return

        print("Adding questions...")
        for q in QUESTIONS:
            # Check if already exists to avoid duplicates
            exists = await db.scalar(select(Question).where(Question.question_text == q["text"]))
            if not exists:
                db.add(Question(
                    subject_id=math.id,
                    exam_category=ExamCategory.JAMB,
                    question_text=q["text"],
                    options=q["options"],
                    correct_key=q["correct"],
                    explanation=q["explanation"],
                    difficulty=Difficulty.MEDIUM
                ))
        
        await db.commit()
        print("✅ Questions added successfully!")

if __name__ == "__main__":
    asyncio.run(main())