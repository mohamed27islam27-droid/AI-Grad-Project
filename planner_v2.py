from neo4j import GraphDatabase
from collections import defaultdict
import pandas as pd
import math

# -----------------------------
# CONFIG
# -----------------------------
URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "12345678"

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)


def run_query(query, params=None):
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


# -----------------------------
# Load Student
# -----------------------------
def load_student(student_name):

    spec_query = """
    MATCH (s:Student {firstName:$name})
    RETURN s.department AS specialization
    """

    result = run_query(
        spec_query,
        {"name": student_name}
    )

    if not result:
        raise Exception(
            f"Student '{student_name}' not found"
        )

    spec = str(
        result[0]["specialization"]
    ).upper()

    completed_query = """
    MATCH (s:Student {firstName:$name})-[:TOOK]->(c:Course)
    RETURN c.Code AS code
    """

    completed = {
        r["code"]
        for r in run_query(
            completed_query,
            {"name": student_name}
        )
    }

    return spec, completed

# -----------------------------
# Load Course Metadata
# -----------------------------
def load_course_metadata():

    df = pd.read_csv("courses_data.csv")

    course_data = {}

    for _, row in df.iterrows():

        prereqs = []

        if str(row["prerequisites"]) != "NONE":

            prereqs = [
                p.strip()
                for p in str(
                    row["prerequisites"]
                ).split(",")
            ]

        groups = [
            g.strip()
            for g in str(
                row["requirement_group"]
            ).split(",")
        ]

        course_data[row["code"]] = {

            "semester":
                str(row["semester"]),

            "level":
                int(
                    row["level_requirement"]
                ),

            "prereqs":
                prereqs,

            "groups":
                groups
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
def calculate_requirement_progress(
    completed,
    course_data,
    targets
):

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
def compute_remaining_required(
    course_data,
    targets,
    progress,
    completed
):

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
def compute_unlock_power(
    course,
    reverse_graph,
    remaining
):

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
def is_eligible(
    course,
    completed,
    course_data,
    semester,
    year
):

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
def score_course(
    course,
    course_data,
    reverse_graph,
    remaining,
    progress,
    targets,
    semesters_left,
    spec
):

    score = 0

    groups = course_data[course]["groups"]

    spec_core = f"{spec}_CORE"
    spec_elective = f"{spec}_ELECTIVE"

    # ---------------------------------
    # Strong specialization preference
    # ---------------------------------

    if spec_core in groups:
        score += 6000

    elif spec_elective in groups:
        score += 2500

    elif any(g.endswith("_CORE") for g in groups):
        score += 2000

    elif any("CHOOSE" in g for g in groups):
        score += 3000

    elif any(g.endswith("_ELECTIVE") for g in groups):
        score += 1000

    # ---------------------------------
    # Requirement urgency
    # ---------------------------------

    for g in groups:

        if g in targets and targets[g] != math.inf:

            remaining_needed = (
                targets[g]
                - progress[g]
            )

            if remaining_needed >= semesters_left:
                score += 3000

    # ---------------------------------
    # Project boost
    # ---------------------------------

    if course.endswith("497"):
        score += 1500

    if course.endswith("498"):
        score += 2500

    # ---------------------------------
    # Unlock power
    # ---------------------------------

    unlock = compute_unlock_power(
        course,
        reverse_graph,
        remaining
    )

    score += unlock * 50

    return score

# -----------------------------
# Graduation Check
# -----------------------------
def validate_graduation(progress, targets):

    valid = True

    print()
    print("Graduation Check")
    print("----------------")

    for group, target in targets.items():

        if target == math.inf:
            continue

        current = progress[group]

        print(
            group,
            "->",
            current,
            "/",
            target
        )

        if current < target:
            valid = False

    return valid

# -----------------------------
# Advanced Planner
# -----------------------------
def generate_advanced_plan(student_name):

    spec, completed = load_student(student_name)


    print("\n================================")
    print("Student:", student_name)
    print("Specialization:", spec)
    print("Completed Courses:", len(completed))
    print("================================")

    course_data = load_course_metadata()

    targets = get_requirement_targets(spec)

    print("\nTargets:")
    for k, v in targets.items():
        print(k, "=", v)

    reverse_graph = build_reverse_graph(
        course_data
    )

    progress = calculate_requirement_progress(
        completed,
        course_data,
        targets
    )

    remaining = compute_remaining_required(
        course_data,
        targets,
        progress,
        completed
    )

    print("\nCourses matching specialization targets:")

    spec_courses = []

    for code, data in course_data.items():

        if (
            f"{spec}_CORE" in data["groups"]
             or
            f"{spec}_ELECTIVE" in data["groups"]
        ):
         spec_courses.append(code)

    print(sorted(spec_courses))
    print("Total:", len(spec_courses))

    plan = {}

    current_year = 3

    semester_pattern = [1, 2, 1, 2]

    project_code = f"{spec}498"

    if project_code not in course_data:
        project_code = None

    for i in range(4):

        semester = semester_pattern[i]

        semester_label = (
            f"Year {current_year} - Semester {semester}"
        )

        semesters_left = 4 - i

        max_courses = (
            7
            if current_year == 4
            else 6
        )

        selected = []

        # -----------------------------
        # Force Project in Year 4 S1
        # -----------------------------
        if current_year == 4 and semester == 1:

            if project_code and project_code not in completed:

                if is_eligible(
                    project_code,
                    completed,
                    course_data,
                    semester,
                    current_year
                ):

                    selected.append(
                        project_code
                    )

        # -----------------------------
        # Eligible Courses
        # -----------------------------
        eligible = [

            c

            for c in remaining

            if is_eligible(
                c,
                completed,
                course_data,
                semester,
                current_year
            )

            and c not in selected
        ]

        scored = []

        for c in eligible:

            score = score_course(
                c,
                course_data,
                reverse_graph,
                remaining,
                progress,
                targets,
                semesters_left,
                spec
            )

            scored.append(
                (c, score)
            )

        scored.sort(
            key=lambda x: x[1],
            reverse=True
        )
        
        print("\nTop candidates for", semester_label)

        for course, score in scored[:15]:

            print(
                course,
                "Score:",
                score,
                "Groups:",
                course_data[course]["groups"]
            )

        remaining_slots = (
            max_courses - len(selected)
        )

        selected += [

            c

            for c, s

            in scored[:remaining_slots]
        ]

        plan[semester_label] = selected

        completed.update(selected)

        for c in selected:

            for g in course_data[c]["groups"]:

                if g in targets:
                    progress[g] += 1

        remaining = compute_remaining_required(
            course_data,
            targets,
            progress,
            completed
        )

        if semester == 2:
            current_year += 1

    graduation_ok = validate_graduation(
        progress,
        targets
    )

    return plan, graduation_ok


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":

    for student_name in [
        "Ali",
        "Ahmed",
        "Aser",
        "Amr"
    ]:

        plan, graduation_ok = generate_advanced_plan(
            student_name
        )

        print("\n")
        print("=" * 60)
        print("PLAN FOR:", student_name)
        print("=" * 60)

        for semester, courses in plan.items():

            print()
            print(semester)
            print(courses)

        print()

        print(
            "Graduation Status:",
            "VALID PLAN"
            if graduation_ok
            else "INCOMPLETE"
        )