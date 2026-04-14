from neo4j import GraphDatabase
from collections import defaultdict

# -----------------------------
# CONFIG
# -----------------------------
URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "12345678"

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))


# -----------------------------
# Helper: Run Query
# -----------------------------
def run_query(query, params=None):
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


# -----------------------------
# Load Student Info
# -----------------------------
def load_student(student_name):

    spec_query = """
    MATCH (s:Student {name:$name})-[:INTENDS]->(sp)
    RETURN sp.code AS specialization
    """

    spec_result = run_query(spec_query, {"name": student_name})
    specialization = spec_result[0]["specialization"]

    completed_query = """
    MATCH (s:Student {name:$name})-[:TOOK]->(c)
    RETURN c.code AS code
    """

    completed_result = run_query(completed_query, {"name": student_name})
    completed = {row["code"] for row in completed_result}

    return specialization, completed


# -----------------------------
# Load Required Courses
# -----------------------------
def load_required_courses(specialization):

    query = """
    MATCH (c:Course)-[:PART_OF]->(rg:RequirementGroup)
    OPTIONAL MATCH (c)-[:BELONGS_TO]->(sp:Specialization)
    RETURN c.code AS code,
           collect(DISTINCT rg.name) AS groups
    """

    results = run_query(query)

    required_set = set()
    group_map = defaultdict(list)

    for row in results:
        code = row["code"]
        groups = row["groups"]

        for group in groups:

            if group == "UNIVERSITY_MANDATORY":
                required_set.add(code)

            elif group == "UNIVERSITY_CHOOSE_2":
                required_set.add(code)

            elif group == "FACULTY_CORE":
                required_set.add(code)

            elif group == "FACULTY_CHOOSE_3":
                required_set.add(code)

            elif group == f"{specialization}_CORE":
                required_set.add(code)

            elif group == f"{specialization}_ELECTIVE":
                required_set.add(code)

            group_map[group].append(code)

    return required_set, group_map


# -----------------------------
# Load Course Metadata
# -----------------------------
def load_course_metadata():

    query = """
    MATCH (c:Course)
    OPTIONAL MATCH (c)-[:REQUIRES]->(p)
    RETURN c.code AS code,
           c.semester AS semester,
           c.level_requirement AS level,
           collect(p.code) AS prereqs
    """

    results = run_query(query)

    course_data = {}

    for row in results:
        code = row["code"]
        semester = row["semester"]
        level = row["level"]
        prereqs = [p for p in row["prereqs"] if p is not None]

        course_data[code] = {
            "semester": semester,
            "level": level,
            "prereqs": prereqs
        }

    return course_data


# -----------------------------
# Get Eligible Courses
# -----------------------------
def get_eligible_courses(remaining, completed, course_data, semester_number, year_number):

    eligible = []

    for course in remaining:

        if course not in course_data:
            continue

        data = course_data[course]

        # Semester rule
        if data["semester"] not in [str(semester_number), "x"]:
            continue

        # Level rule
        if data["level"] == 4 and year_number < 4:
            continue

        # Prerequisite rule
        if not set(data["prereqs"]).issubset(completed):
            continue

        eligible.append(course)

    return eligible


# -----------------------------
# Generate 4 Semester Plan
# -----------------------------
def generate_4_semester_plan(student_name):

    spec, completed = load_student(student_name)
    required_set, group_map = load_required_courses(spec)
    course_data = load_course_metadata()

    remaining = required_set - completed

    plan = {}
    current_year = 3

    semester_pattern = [1, 2, 1, 2]

    for i in range(4):

        semester_number = semester_pattern[i]
        semester_label = f"Year {current_year} - Semester {semester_number}"

        eligible = get_eligible_courses(
            remaining,
            completed,
            course_data,
            semester_number,
            current_year
        )

        # Simple strategy: take first 6 eligible
        selected = eligible[:6]

        plan[semester_label] = selected

        # Update completed and remaining
        completed.update(selected)
        remaining -= set(selected)

        # Move to next year after semester 2
        if semester_number == 2:
            current_year += 1

    return plan


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":

    student_name = "Ali"

    plan = generate_4_semester_plan(student_name)

    for semester, courses in plan.items():
        print("\n", semester)
        print("Courses:", courses)
        print("Count:", len(courses))
