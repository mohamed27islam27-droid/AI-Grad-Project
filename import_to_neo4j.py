from neo4j import GraphDatabase
import pandas as pd

import os

# -----------------------------
# CONFIG
# -----------------------------
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

CSV_FILE = "courses_data.csv"

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))


# -----------------------------
# UTILITY FUNCTION
# -----------------------------
def run_query(query, parameters=None):
    with driver.session() as session:
        session.run(query, parameters or {})


# -----------------------------
# CLEAR DATABASE
# -----------------------------
def clear_database():
    print("Clearing database...")
    run_query("MATCH (n) DETACH DELETE n")


# -----------------------------
# CREATE CONSTRAINTS
# -----------------------------
def create_constraints():
    print("Creating constraints...")
    run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Course) REQUIRE c.code IS UNIQUE")
    run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Student) REQUIRE s.id IS UNIQUE")
    run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (sp:Specialization) REQUIRE sp.code IS UNIQUE")
    run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (rg:RequirementGroup) REQUIRE rg.name IS UNIQUE")


# -----------------------------
# IMPORT COURSES
# -----------------------------
def import_courses():
    print("Importing courses...")
    df = pd.read_csv(CSV_FILE)

    for _, row in df.iterrows():
        run_query("""
        CREATE (c:Course {
            code: $code,
            name: $name,
            credits: $credits,
            semester: $semester,
            level_requirement: $level_requirement
        })
        """, {
            "code": row["code"],
            "name": row["name"],
            "credits": int(row["credits"]),
            "semester": str(row["semester"]),
            "level_requirement": int(row["level_requirement"])
        })


# -----------------------------
# IMPORT PREREQUISITES
# -----------------------------
def import_prerequisites():
    print("Creating prerequisite relationships...")
    df = pd.read_csv(CSV_FILE)

    for _, row in df.iterrows():
        prereqs = str(row["prerequisites"]).split(",")

        for prereq in prereqs:
            prereq = prereq.strip()
            if prereq != "NONE":
                run_query("""
                MATCH (c:Course {code: $course})
                MATCH (p:Course {code: $prereq})
                CREATE (c)-[:REQUIRES]->(p)
                """, {
                    "course": row["code"],
                    "prereq": prereq
                })


# -----------------------------
# IMPORT SPECIALIZATIONS
# -----------------------------
def import_specializations():
    print("Creating specializations...")
    df = pd.read_csv(CSV_FILE)

    specializations = set()

    for specs in df["specializations"]:
        for sp in str(specs).split(","):
            specializations.add(sp.strip())

    for sp in specializations:
        run_query("""
        CREATE (s:Specialization {code: $code})
        """, {"code": sp})


# -----------------------------
# LINK COURSES TO SPECIALIZATIONS
# -----------------------------
def link_courses_to_specializations():
    print("Linking courses to specializations...")
    df = pd.read_csv(CSV_FILE)

    for _, row in df.iterrows():
        for sp in str(row["specializations"]).split(","):
            run_query("""
            MATCH (c:Course {code: $code})
            MATCH (s:Specialization {code: $sp})
            CREATE (c)-[:BELONGS_TO]->(s)
            """, {
                "code": row["code"],
                "sp": sp.strip()
            })


# -----------------------------
# IMPORT REQUIREMENT GROUPS
# -----------------------------
def import_requirement_groups():
    print("Creating requirement groups...")
    df = pd.read_csv(CSV_FILE)

    groups = set()

    for group_field in df["requirement_group"]:
        for g in str(group_field).split(","):
            groups.add(g.strip())

    for g in groups:
        run_query("""
        CREATE (rg:RequirementGroup {name: $name})
        """, {"name": g})


# -----------------------------
# LINK COURSES TO REQUIREMENT GROUPS
# -----------------------------
def link_courses_to_groups():
    print("Linking courses to requirement groups...")
    df = pd.read_csv(CSV_FILE)

    for _, row in df.iterrows():
        for g in str(row["requirement_group"]).split(","):
            run_query("""
            MATCH (c:Course {code: $code})
            MATCH (rg:RequirementGroup {name: $group})
            CREATE (c)-[:PART_OF]->(rg)
            """, {
                "code": row["code"],
                "group": g.strip()
            })


# -----------------------------
# CREATE STUDENTS
# -----------------------------
def create_students():
    print("Creating students...")

    students = [
        {"id": "S1", "name": "Ali", "spec": "IS"},
        {"id": "S2", "name": "Ahmed", "spec": "IT"},
        {"id": "S3", "name": "Aser", "spec": "AI"},
        {"id": "S4", "name": "Amr", "spec": "CS"}
    ]

    for student in students:
        run_query("""
        CREATE (s:Student {
            id: $id,
            name: $name,
            current_year: 3
        })
        """, student)

        run_query("""
        MATCH (s:Student {id: $id})
        MATCH (sp:Specialization {code: $spec})
        CREATE (s)-[:INTENDS]->(sp)
        """, student)


# -----------------------------
# ADD COMPLETED COURSES
# -----------------------------
def add_completed_courses():
    print("Adding completed courses...")

    completed = [
        "HU111","IT111","CS111","MA111","PH111","IS231",
        "HU112","HU122","ST121","CS112","MA113","IT223",
        "IT221","HU313","IS351","CS213","CS214","CS221","IS211",
        "CS316","CS241","CS251","MA112","ST112","IT222"
    ]

    for course in completed:
        run_query("""
        MATCH (s:Student)
        MATCH (c:Course {code: $code})
        CREATE (s)-[:TOOK]->(c)
        """, {"code": course})


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    clear_database()
    create_constraints()
    import_courses()
    import_prerequisites()
    import_specializations()
    link_courses_to_specializations()
    import_requirement_groups()
    link_courses_to_groups()
    create_students()
    add_completed_courses()

    print("\nImport completed successfully!")
