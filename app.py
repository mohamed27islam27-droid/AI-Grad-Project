from flask import Flask, render_template, request, jsonify
from flasgger import Swagger
from llm_wrapper import summarize_text
from planner_v2 import generate_advanced_plan
from neo4j import GraphDatabase
import pickle
import numpy as np
import requests
import os
from pymongo import MongoClient
import bcrypt
import jwt
import datetime

app = Flask(__name__)
# Initialize Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,  # all in
            "model_filter": lambda tag: True,  # all in
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}
swagger = Swagger(app, config=swagger_config, template={
    "info": {
        "title": "AI Grad Project API",
        "description": "API documentation for the AI Graduation Project",
        "version": "1.0.0"
    }
})

# ==========================================
# Neo4j Config
# ==========================================
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

# ==========================================
# MongoDB Config
# ==========================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27018/gp_backend")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key")
try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = mongo_client.get_database()
    users_collection = db.users
except Exception as e:
    print(f"MongoDB Connection Error: {e}")

# ==========================================
# Load ML Model
# ==========================================
with open("grade_predictor.pkl", "rb") as f:
    grade_model = pickle.load(f)


# ==========================================
# GPA Calculator (Egyptian 4.0 Weighted)
# ==========================================
def convert_percentage_to_gpa(grade):
    if grade >= 90: return 4.0
    if grade >= 85: return 3.7
    if grade >= 80: return 3.3
    if grade >= 75: return 3.0
    if grade >= 70: return 2.7
    if grade >= 65: return 2.3
    if grade >= 60: return 2.0
    if grade >= 50: return 1.0
    return 0.0


def calculate_weighted_gpa(course_grades):
    total_points = 0
    total_credits = 0

    with driver.session() as session:
        for course_code, grade in course_grades.items():

            result = session.run(
                "MATCH (c:Course {code:$code}) RETURN c.credits AS credits",
                {"code": course_code}
            ).single()

            if result:
                credits = result["credits"]
                gpa_value = convert_percentage_to_gpa(float(grade))

                total_points += gpa_value * credits
                total_credits += credits

    if total_credits == 0:
        return 0.0

    return round(total_points / total_credits, 2)


# ==========================================
# Authentication
# ==========================================
@app.route("/api/auth/register", methods=["POST"])
def register():
    """
    Register a new user
    ---
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            password:
              type: string
    responses:
      201:
        description: User registered successfully
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return jsonify({"msg": "Username and password required"}), 400
        
    if users_collection.find_one({"username": username}):
        return jsonify({"msg": "User already exists"}), 400
        
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    users_collection.insert_one({
        "username": username,
        "password": hashed_password.decode('utf-8'),
        "created_at": datetime.datetime.now(datetime.timezone.utc)
    })
    
    return jsonify({"msg": "User registered successfully"}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    """
    Login a user
    ---
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            password:
              type: string
    responses:
      200:
        description: Login successful
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    user = users_collection.find_one({"username": username})
    
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
        return jsonify({"msg": "Invalid credentials"}), 401
        
    token = jwt.encode({
        "username": username,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)
    }, JWT_SECRET, algorithm="HS256")
    
    return jsonify({
        "msg": "Login successful",
        "token": token,
        "user": {"username": username}
    }), 200

# ==========================================
# Home + Guest Pages
# ==========================================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/guest")
def guest_page():
    return render_template("guest.html")


# ==========================================
# Grade Predictor
# ==========================================
@app.route("/predict", methods=["POST"])
def predict():
    """
    Predict Final Exam Grade
    ---
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            coursework:
              type: number
              example: 20
            midterm:
              type: number
              example: 22
    responses:
      200:
        description: Prediction and AI advice
    """
    data = request.json
    coursework = float(data["coursework"])
    midterm = float(data["midterm"])

    performance_gap = midterm - coursework
    average_internal = (midterm + coursework) / 2

    features = np.array([[coursework, midterm, performance_gap, average_internal]])

    predicted_final_exam = grade_model.predict(features)[0]
    predicted_final_exam = max(0, min(50, predicted_final_exam))

    total_grade = coursework + midterm + predicted_final_exam

    advice_prompt = f"""
    A student has:
    Coursework: {coursework}/25
    Midterm: {midterm}/25
    Predicted Final Exam: {predicted_final_exam:.2f}/50
    Total Expected Grade: {total_grade:.2f}/100

    Provide short academic advice (3 sentences).
    """

    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "phi",
                "prompt": advice_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 120
                }
            }
        )

        advice = response.json()["response"].strip()

    except Exception:
        advice = "AI advice unavailable."

    result_text = f"""
    <b>Predicted Final Exam:</b> {predicted_final_exam:.2f} / 50<br>
    <b>Total Expected Grade:</b> {total_grade:.2f} / 100<br><br>
    <b>AI Advice:</b><br>{advice}
    """

    return jsonify({"result": result_text})


# ==========================================
# Summarizer
# ==========================================
@app.route("/summarize", methods=["POST"])
def summarize():
    """
    Summarize Text
    ---
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            text:
              type: string
              example: "This is a long test text for summarization."
    responses:
      200:
        description: Text summary
    """
    data = request.json
    summary = summarize_text(data["text"], 3)
    return jsonify({"result": summary})


# ==========================================
# Existing Student Planner
# ==========================================
@app.route("/generate_plan", methods=["POST"])
def generate_plan():
    """
    Generate Advanced Academic Plan for Existing Student
    ---
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            student:
              type: string
              example: "Alice"
    responses:
      200:
        description: Generated academic plan
    """
    student_name = request.json["student"]
    plan, graduation_ok = generate_advanced_plan(student_name)

    return jsonify({
        "plan": format_plan(plan),
        "status": "VALID PLAN" if graduation_ok else "INCOMPLETE",
        "explanation": generate_plan_explanation(graduation_ok)
    })


# ==========================================
# Guest Mode Planner + GPA
# ==========================================
@app.route("/guest_plan", methods=["POST"])
def guest_plan():
    """
    Generate Plan for Guest Student
    ---
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            specialization:
              type: string
              example: "AI"
            courses:
              type: array
              items:
                type: string
              example: ["CS101", "CS102"]
            gpa_mode:
              type: boolean
              example: false
            grades:
              type: object
              example: {"CS101": 85, "CS102": 90}
    responses:
      200:
        description: Generated academic plan and optional GPA
    """
    data = request.json
    specialization = data["specialization"]
    selected_courses = data["courses"]
    gpa_mode = data["gpa_mode"]
    grades = data.get("grades", {})

    with driver.session() as session:

        # Delete old Guest
        session.run("MATCH (s:Student {name:'Guest'}) DETACH DELETE s")

        # Create new Guest
        session.run("CREATE (s:Student {name:'Guest'})")

        session.run("""
            MATCH (s:Student {name:'Guest'})
            MATCH (sp:Specialization {code:$spec})
            CREATE (s)-[:INTENDS]->(sp)
        """, {"spec": specialization})

        for course in selected_courses:
            session.run("""
                MATCH (s:Student {name:'Guest'})
                MATCH (c:Course {code:$code})
                CREATE (s)-[:TOOK]->(c)
            """, {"code": course})

    gpa_value = None
    if gpa_mode:
        gpa_value = calculate_weighted_gpa(grades)

    plan, graduation_ok = generate_advanced_plan("Guest")

    return jsonify({
        "plan": format_plan(plan),
        "status": "VALID PLAN" if graduation_ok else "INCOMPLETE",
        "gpa": gpa_value,
        "explanation": generate_plan_explanation(graduation_ok)
    })


# ==========================================
# API: Courses Grouped by Requirement
# ==========================================
@app.route("/api_courses")
def api_courses():
    """
    Get all courses grouped by requirements
    ---
    responses:
      200:
        description: List of courses grouped by requirement group
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Course)-[:PART_OF]->(rg:RequirementGroup)
            RETURN 
                c.code AS code,
                c.name AS name,
                c.credits AS credits,
                rg.name AS group
            ORDER BY rg.name, c.code
        """)

        courses = []

        for r in result:
            courses.append({
                "code": r["code"],
                "name": r["name"],
                "credits": r["credits"],
                "group": r["group"]
            })

    return jsonify({"courses": courses})


# ==========================================
# Helpers
# ==========================================
def format_plan(plan):
    html = ""
    for semester, courses in plan.items():
        html += f"<h4>{semester}</h4><ul>"
        for c in courses:
            html += f"<li>{c}</li>"
        html += "</ul>"
    return html


def generate_plan_explanation(graduation_ok):

    prompt = f"""
    Explain in 3 sentences why this academic plan is logically structured.
    Graduation valid: {graduation_ok}.
    """

    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "phi",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 100
                }
            }
        )

        return response.json()["response"].strip()

    except:
        return "AI explanation unavailable."


# ==========================================
# Run
# ==========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)