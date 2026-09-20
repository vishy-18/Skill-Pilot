import os
import pymupdf
from navigator.services import NavigatorService
from navigator.schema import StudentRegistration
from web.portal import extract_resume_text

test_db = "test_features_flow.db"
if os.path.exists(test_db):
    try:
        os.remove(test_db)
    except:
        pass

svc = NavigatorService(test_db)

# 1. Initial Resume
resume_v1 = """
Siddharth Raman
siddharth@example.com | +91 9444123456 | Bangalore, India | linkedin.com/in/siddharthr | github.com/siddharthr

SUMMARY
Software Engineer specializing in Python, Django, PostgreSQL, Docker and Microservices architecture.

TECHNICAL SKILLS
Languages: Python, SQL, C++, JavaScript
Frameworks: Django, FastAPI, React
Tools & Platforms: Docker, Git, Linux, PostgreSQL, AWS
Core: REST APIs, System Design, Data Structures & Algorithms

EDUCATION
B.Tech in Information Technology
National Institute of Technology Karnataka | 2020 - 2024 | CGPA: 8.75 / 10.0

EXPERIENCE
Software Engineer Intern | CloudScale Systems | Jan 2024 - Jun 2024 | Bangalore
- Engineered scalable microservice endpoints in Django and PostgreSQL.
- Reduced database query latency by 35% through query optimization and Redis caching.

PROJECTS
Event Horizon Streamer | Python, FastAPI, Docker, Redis
- Architected high-throughput message streaming service processing 10,000 events/sec.
- Integrated Docker container deployment with health monitoring.
"""

print("1. Registering student with initial resume...")
reg1 = StudentRegistration(
    name="Siddharth Raman",
    graduation_year=2024,
    college="NITK",
    department="IT",
    email="siddharth@example.com",
    password="Password123",
    education_level="B.Tech",
    cgpa=8.75,
    career_goal_role="Backend Developer",
    resume_text=resume_v1
)
student = svc.register_student(reg1)
svc.analyze_resume_and_gaps_with_llm(student.student_id)

builder_v1 = svc.extract_resume_fields_for_builder(student.student_id)
print("\n--- Builder V1 Initial Extraction ---")
print("Full Name:", builder_v1.get("full_name"))
print("Phone:", builder_v1.get("phone"))
print("Location:", builder_v1.get("location"))
print("Languages:", builder_v1.get("skills_languages"))
print("Frameworks:", builder_v1.get("skills_frameworks"))
print("Education:", builder_v1.get("education"))
print("Experience:", builder_v1.get("experience"))
print("Projects:", builder_v1.get("projects"))

assert builder_v1.get("phone") == "+91 9444123456", "Failed to extract phone"
assert "2020 - 2024" in builder_v1.get("education", [{}])[0].get("graduation_year", ""), "Failed to extract education dates"
assert "Jan 2024 - Jun 2024" in builder_v1.get("experience", [{}])[0].get("duration", ""), "Failed to extract experience dates"
assert builder_v1.get("projects", [{}])[0].get("title") == "Event Horizon Streamer", "Failed to extract project"

# 2. Update Resume (Simulating "Save and re-analyze" in Profile)
print("\n2. Updating resume with new version (Save & Re-analyze)...")
resume_v2 = """
Siddharth Raman
siddharth@example.com | +91 9444123456 | Hyderabad, India | linkedin.com/in/siddharthr | github.com/siddharthr

SUMMARY
Senior Backend Specialist with deep expertise in Go, Kubernetes, Kafka, gRPC, and Distributed Systems.

TECHNICAL SKILLS
Languages: Go, Python, SQL, Rust
Frameworks: gRPC, Gin, FastAPI
Tools & Platforms: Kubernetes, Docker, Kafka, PostgreSQL, AWS, Git
Core: Distributed Systems, System Design, Microservices, CI/CD

EDUCATION
M.Tech in Computer Science
IIT Hyderabad | 2024 - 2026 | CGPA: 9.20 / 10.0

EXPERIENCE
Distributed Systems Intern | HyperScale Labs | Jul 2024 - Dec 2024 | Hyderabad
- Designed distributed consensus protocols and leader election using Raft in Go.
- Orchestrated multi-region Kubernetes clusters handling 500k requests/minute.

PROJECTS
Raft Distributed KV Store | Go, gRPC, Kubernetes, Raft
- Built distributed transactional key-value store with consensus replication.
"""

svc.clear_ats_resume_draft(student.student_id)
svc.update_student_profile(student.student_id, {"resume_text": resume_v2, "education_level": "M.Tech", "cgpa": 9.2})
svc.analyze_resume_and_gaps_with_llm(student.student_id)
builder_v2 = svc.extract_resume_fields_for_builder(student.student_id)

print("\n--- Builder V2 After 'Save and re-analyze' ---")
print("Location:", builder_v2.get("location"))
print("Languages:", builder_v2.get("skills_languages"))
print("Education:", builder_v2.get("education"))
print("Experience:", builder_v2.get("experience"))
print("Projects:", builder_v2.get("projects"))

assert "2024 - 2026" in builder_v2.get("education", [{}])[0].get("graduation_year", ""), "Education dates did not update!"
assert "Jul 2024 - Dec 2024" in builder_v2.get("experience", [{}])[0].get("duration", ""), "Experience dates did not update!"
assert builder_v2.get("projects", [{}])[0].get("title") == "Raft Distributed KV Store", "Project title did not update!"
assert "IIT Hyderabad" in builder_v2.get("education", [{}])[0].get("institution", ""), "Institution did not update!"

# 3. Verify Empty Student has Zero Mock Fallbacks
print("\n3. Verifying Empty Resume Profile has ZERO fake mock placeholders...")
reg_empty = StudentRegistration(
    name="Clean Student",
    graduation_year=2027,
    college="College of Engineering Guindy",
    department="CSE",
    email="clean@ceg.edu",
    password="Password123",
    education_level="B.Tech",
    cgpa=8.5,
    career_goal_role="Software Engineering Intern",
    resume_text=""
)
s_empty = svc.register_student(reg_empty)
empty_builder = svc.extract_resume_fields_for_builder(s_empty.student_id)

print("Empty Student has_resume:", empty_builder.get("has_resume"))
print("Empty Student experience (must be empty list):", empty_builder.get("experience"))
print("Empty Student projects (must be empty list):", empty_builder.get("projects"))

assert empty_builder.get("has_resume") == False
assert empty_builder.get("experience") == []
assert empty_builder.get("projects") == []

# Cleanup
try:
    os.remove(test_db)
except:
    pass

print("\n=======================================================")
print(">>> ALL VERIFICATION TESTS PASSED 100% SUCCESSFULLY! <<<")
print("=======================================================")
