"""
Seed script — run once:
    python seed.py
"""
import asyncio
from app.db.session import SessionLocal
from app.models import (
    Department, Subject, Topic, LearningMaterial, Question,
    ExamCategory, Difficulty,
)

DEPARTMENTS = [
    {"slug": "science", "name": "Science", "description": "Physics, Chemistry, Biology & more", "display_order": 1},
    {"slug": "commercial", "name": "Commercial", "description": "Economics, Commerce, Accounting", "display_order": 2},
    {"slug": "art", "name": "Art", "description": "Literature, History, Government", "display_order": 3},
]

SUBJECTS = {
    "science": [
        ("mathematics", "Mathematics"),
        ("english-language", "English Language"),
        ("physics", "Physics"),
        ("chemistry", "Chemistry"),
        ("biology", "Biology"),
        ("further-mathematics", "Further Mathematics"),
        ("agricultural-science", "Agricultural Science"),
        ("computer-studies", "Computer Studies"),
        ("geography", "Geography"),
    ],
    "commercial": [
        ("mathematics", "Mathematics"),
        ("english-language", "English Language"),
        ("economics", "Economics"),
        ("commerce", "Commerce"),
        ("financial-accounting", "Financial Accounting"),
        ("government", "Government"),
        ("business-studies", "Business Studies"),
    ],
    "art": [
        ("english-language", "English Language"),
        ("mathematics", "Mathematics"),
        ("literature-in-english", "Literature in English"),
        ("government", "Government"),
        ("history", "History"),
        ("crs", "CRS"),
        ("irs", "IRS"),
        ("civic-education", "Civic Education"),
    ],
}

# Sample topics per subject (all subjects get these for a quick demo)
TOPICS = [
    "Number Bases", "Fractions", "Percentages", "Ratio and Proportion",
    "Indices", "Logarithms", "Algebra", "Linear Equations",
    "Simultaneous Equations", "Quadratic Equations", "Geometry",
    "Trigonometry", "Statistics", "Probability", "Mensuration", "Sets", "Functions",
]

async def main():
    async with SessionLocal() as db:
        for d in DEPARTMENTS:
            existing = await db.scalar(
                __import__("sqlalchemy").select(Department).where(Department.slug == d["slug"])
            )
            if existing:
                print(f"  ⏭  department {d['slug']}")
                continue
            dept = Department(**d)
            db.add(dept)
            await db.flush()
            print(f"  ✓ department {d['slug']}")

            for slug, name in SUBJECTS[d["slug"]]:
                subj = Subject(
                    department_id=dept.id,
                    slug=slug,
                    name=name,
                    display_order=0,
                )
                db.add(subj)
                await db.flush()
                print(f"    ✓ subject {name}")

                for i, t_title in enumerate(TOPICS, start=1):
                    t_slug = t_title.lower().replace(" ", "-")
                    topic = Topic(
                        subject_id=subj.id,
                        slug=t_slug,
                        title=t_title,
                        summary=f"An introduction to {t_title}.",
                        display_order=i,
                        price_kobo=200_000,
                        is_free_preview=(i == 1),
                    )
                    db.add(topic)
                    await db.flush()

                    # First topic of the first subject gets content; others placeholder
                    if subj.slug == "mathematics" and i == 1:
                        db.add(LearningMaterial(
                            topic_id=topic.id,
                            content_blocks={
                                "blocks": [
                                    {"type": "intro", "text": "Number bases are the foundation of all numeral systems."},
                                    {"type": "objectives", "items": [
                                        "Understand base-10, base-2 and base-8",
                                        "Convert between bases",
                                        "Perform arithmetic in various bases",
                                    ]},
                                    {"type": "explanation", "text":
                                        "A number base is the number of distinct digits used to represent numbers. "
                                        "Base 10 uses 0–9, base 2 uses 0–1, base 8 uses 0–7."},
                                    {"type": "example", "question": "Convert 45₁₀ to base 2.",
                                     "steps": ["45 ÷ 2 = 22 r1", "22 ÷ 2 = 11 r0", "11 ÷ 2 = 5 r1",
                                               "5 ÷ 2 = 2 r1", "2 ÷ 2 = 1 r0", "1 ÷ 2 = 0 r1"],
                                     "answer": "101101₂"},
                                    {"type": "summary", "text": "Always read remainders bottom-to-top when converting to binary."},
                                ]
                            },
                        ))

        await db.commit()
        print("\n✅ Seed complete.")

if __name__ == "__main__":
    asyncio.run(main())