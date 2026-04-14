from neo4j import GraphDatabase
from collections import defaultdict
import math
import os

# -----------------------------
# CONFIG
# -----------------------------
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))


def run_query(query, params=None):
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


# -----------------------------
# Load Student
# -----------------------------
def load_student(student_name):

    spec_query = """
    MATCH (s:Student {name:$name})-[:INTENDS]->(sp)
    RETURN sp.code AS specialization
    """
    spec = run_query(spec_query, {"name": student_name})[0]["specialization"]

    completed_query = """
    MATCH (s:Student {name:$name})-[:TOOK]->(c)
    RETURN c.code AS code
    """
    completed = {r["code"] for r in run_query(completed_query, {"name": student_name})}

    return spec, completed


# -----------------------------
# Load Course Metadata
# -----------------------------
def load_course_metadata():

    query = """
    MATCH (c:Course)
    OPTIONAL MATCH (c)-[:REQUIRES]->(p)
    OPTIONAL MATCH (c)-[:PART_OF]->(rg)
    RETURN c.code AS code,
           c.semester AS semester,
           c.level_requirement AS level,
           collect(DISTINCT p.code) AS prereqs,
           collect(DISTINCT rg.name) AS groups
    """

    results = run_query(query)

    course_data = {}

    for row in results:
        course_data[row["code"]] = {
            "semester": row["semester"],
            "level": row["level"],
            "prereqs": [p for p in row["prereqs"] if p],
            "groups": [g for g in row["groups"] if g]
        }

    return course_data


# -----------------------------
# Requirement Targets
# -----------------------------
def get_requirement_targets(specialization):

    return {
        "UNIVERSITY_MANDATORY": math.inf,
        "FACULTY_CORE": math.inf,
        f"{specialization}_CORE": math.inf,
        "UNIVERSITY_CHOOSE_2": 2,
        "FACULTY_CHOOSE_3": 3,
        f"{specialization}_ELECTIVE": 7
    }


# -----------------------------
# Requirement Progress
# -----------------------------
def calculate_requirement_progress(completed, course_data, targets):

    progress = defaultdict(int)

    for course in completed:
        if course not in course_data:
            continue

        for group in course_data[course]["groups"]:
            if group in targets:
                progress[group] += 1

    return progress


# -----------------------------
# Compute Remaining Required
# -----------------------------
def compute_remaining_required(course_data, targets, progress, completed):

    remaining = set()

    for code, data in course_data.items():

        if code in completed:
            continue

        for group in data["groups"]:

            if group not in targets:
                continue

            if targets[group] == math.inf:
                remaining.add(code)

            elif progress[group] < targets[group]:
                remaining.add(code)

    return remaining


# -----------------------------
# Reverse Graph
# -----------------------------
def build_reverse_graph(course_data):

    reverse = defaultdict(list)

    for course, data in course_data.items():
        for prereq in data["prereqs"]:
            reverse[prereq].append(course)

    return reverse


# -----------------------------
# Unlock Power
# -----------------------------
def compute_unlock_power(course, reverse_graph, remaining):

    visited = set()
    stack = [course]
    count = 0

    while stack:
        current = stack.pop()
        for nxt in reverse_graph.get(current, []):
            if nxt not in visited and nxt in remaining:
                visited.add(nxt)
                stack.append(nxt)
                count += 1

    return count


# -----------------------------
# Eligibility
# -----------------------------
def is_eligible(course, completed, course_data, semester, year):

    data = course_data[course]

    if data["semester"] not in [str(semester), "x"]:
        return False

    if data["level"] == 4 and year < 4:
        return False

    if not set(data["prereqs"]).issubset(completed):
        return False

    return True


# -----------------------------
# Score
# -----------------------------
def score_course(course, course_data, reverse_graph,
                 remaining, progress, targets, semesters_left):

    score = 0
    groups = course_data[course]["groups"]

    if any(g.endswith("_CORE") for g in groups):
        score += 1000
    elif any("CHOOSE" in g for g in groups):
        score += 800
    elif any(g.endswith("_ELECTIVE") for g in groups):
        score += 600

    for g in groups:
        if g in targets and targets[g] != math.inf:
            remaining_needed = targets[g] - progress[g]
            if remaining_needed >= semesters_left:
                score += 500

    unlock = compute_unlock_power(course, reverse_graph, remaining)
    score += unlock * 50

    return score


# -----------------------------
# Graduation Check
# -----------------------------
def validate_graduation(progress, targets):

    for group, target in targets.items():
        if target == math.inf:
            continue
        if progress[group] < target:
            return False

    return True


# -----------------------------
# Advanced Planner
# -----------------------------
def generate_advanced_plan(student_name):

    spec, completed = load_student(student_name)
    course_data = load_course_metadata()
    targets = get_requirement_targets(spec)

    reverse_graph = build_reverse_graph(course_data)

    progress = calculate_requirement_progress(completed, course_data, targets)
    remaining = compute_remaining_required(course_data, targets, progress, completed)

    plan = {}
    current_year = 3
    semester_pattern = [1, 2, 1, 2]

    project_code = f"{spec}498"

    for i in range(4):

        semester = semester_pattern[i]
        semester_label = f"Year {current_year} - Semester {semester}"
        semesters_left = 4 - i

        max_courses = 7 if current_year == 4 else 6

        selected = []

        # Force-add project in Year 4 Semester 1
        if current_year == 4 and semester == 1:
            if project_code in course_data and project_code not in completed:
                if is_eligible(project_code, completed, course_data, semester, current_year):
                    selected.append(project_code)

        eligible = [
            c for c in remaining
            if is_eligible(c, completed, course_data, semester, current_year)
            and c not in selected
        ]

        scored = []
        for c in eligible:
            score = score_course(
                c, course_data, reverse_graph,
                remaining, progress, targets,
                semesters_left
            )
            scored.append((c, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        remaining_slots = max_courses - len(selected)
        selected += [c for c, s in scored[:remaining_slots]]

        plan[semester_label] = selected

        completed.update(selected)

        for c in selected:
            for g in course_data[c]["groups"]:
                if g in targets:
                    progress[g] += 1

        remaining = compute_remaining_required(course_data, targets, progress, completed)

        if semester == 2:
            current_year += 1

    graduation_ok = validate_graduation(progress, targets)

    return plan, graduation_ok


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":

    student_name = "Ali"

    plan, graduation_ok = generate_advanced_plan(student_name)

    for semester, courses in plan.items():
        print("\n", semester)
        print("Courses:", courses)
        print("Count:", len(courses))

    print("\nGraduation Status:", "VALID PLAN" if graduation_ok else "INCOMPLETE")
