from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import mysql.connector
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change in production!
app.config['UPLOAD_FOLDER'] = 'uploads'
jwt = JWTManager(app)

# ==============================================
# MySQL Database Configuration
# ==============================================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",          # Default MySQL username
        password="",          # Default MySQL password (empty for local dev)
        database="course_management"
    )

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==============================================
# 1. AUTHENTICATION ENDPOINTS
# ==============================================
@app.route('/auth/register', methods=['POST'])
def register():
    """Register a user (student, lecturer, or admin)"""
    data = request.get_json()
    required = ['user_id', 'name', 'email', 'password', 'role']
    if not all(field in data for field in required):
        return jsonify({"error": "Missing fields"}), 400
    
    if data['role'] not in ['admin', 'lecturer', 'student']:
        return jsonify({"error": "Invalid role"}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO user (user_id, name, email, password, role) VALUES (%s, %s, %s, %s, %s)",
            (data['user_id'], data['name'], data['email'], data['password'], data['role'])
        )
        db.commit()
        return jsonify({"message": "User registered"}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"error": "User ID or email exists"}), 400

@app.route('/auth/login', methods=['POST'])
def login():
    """Login with credentials, returns JWT token"""
    data = request.get_json()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT user_id, role FROM user WHERE email = %s AND password = %s",
        (data['email'], data['password'])
    )
    user = cursor.fetchone()
    if user:
        token = create_access_token(identity={'user_id': user['user_id'], 'role': user['role']})
        return jsonify({"token": token}), 200
    return jsonify({"error": "Invalid credentials"}), 401

# ==============================================
# 2. COURSE MANAGEMENT ENDPOINTS
# ==============================================
@app.route('/courses', methods=['POST'])
@jwt_required()
def create_course():
    """Create a course (admin only)"""
    if get_jwt_identity()['role'] != 'admin':
        return jsonify({"error": "Admins only"}), 403
    
    data = request.get_json()
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO course (course_id, name, lecturer_id) VALUES (%s, %s, %s)",
        (data['course_id'], data['name'], data['lecturer_id'])
    )
    db.commit()
    return jsonify({"message": "Course created"}), 201

@app.route('/courses', methods=['GET'])
def get_courses():
    """Get all courses, or filter by student/lecturer"""
    lecturer_id = request.args.get('lecturer_id')
    student_id = request.args.get('student_id')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    offset = (page - 1) * limit

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if lecturer_id:
        cursor.execute(
            "SELECT * FROM course WHERE lecturer_id = %s LIMIT %s OFFSET %s",
            (lecturer_id, limit, offset)
        )
    elif student_id:
        cursor.execute(
            """SELECT c.* FROM course c 
            JOIN student_course sc ON c.course_id = sc.course_id 
            WHERE sc.student_id = %s LIMIT %s OFFSET %s""",
            (student_id, limit, offset)
        )
    else:
        cursor.execute("SELECT * FROM course LIMIT %s OFFSET %s", (limit, offset))

    courses = cursor.fetchall()
    return jsonify({"courses": courses, "page": page, "limit": limit}), 200

# ==============================================
# 3. ENROLLMENT ENDPOINTS
# ==============================================
@app.route('/courses/<int:course_id>/enroll', methods=['POST'])
@jwt_required()
def enroll(course_id):
    """Enroll a student in a course"""
    student_id = get_jwt_identity()['user_id']
    db = get_db()
    cursor = db.cursor()

    # Check if already enrolled
    cursor.execute(
        "SELECT 1 FROM student_course WHERE student_id = %s AND course_id = %s",
        (student_id, course_id)
    )
    if cursor.fetchone():
        return jsonify({"error": "Already enrolled"}), 400

    cursor.execute(
        "INSERT INTO student_course (student_id, course_id) VALUES (%s, %s)",
        (student_id, course_id)
    )
    db.commit()
    return jsonify({"message": "Enrolled"}), 201

# ==============================================
# 4. ASSIGNMENT ENDPOINTS
# ==============================================
@app.route('/assignments/<int:assignment_id>/submit', methods=['POST'])
@jwt_required()
def submit_assignment(assignment_id):
    """Submit an assignment (PDF upload)"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    student_id = get_jwt_identity()['user_id']
    filename = f"assignment_{assignment_id}_student_{student_id}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    file.save(filepath)

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO assignment_submission (assignment_id, student_id, file_path) VALUES (%s, %s, %s)",
        (assignment_id, student_id, filepath)
    )
    db.commit()
    return jsonify({"file_path": filepath}), 201

# ==============================================
# 5. FORUM & DISCUSSION ENDPOINTS
# ==============================================
@app.route('/forums/<int:forum_id>/threads', methods=['POST'])
@jwt_required()
def create_thread(forum_id):
    """Create a discussion thread in a forum"""
    data = request.get_json()
    user_id = get_jwt_identity()['user_id']
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO forum_post (forum_id, user_id, title, post) VALUES (%s, %s, %s, %s)",
        (forum_id, user_id, data['title'], data['post'])
    )
    db.commit()
    return jsonify({"message": "Thread created"}), 201

# ==============================================
# 6. REPORT ENDPOINTS (SQL VIEWS)
# ==============================================
@app.route('/reports/top-students', methods=['GET'])
def top_students():
    """Get top 10 students by average grade"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.user_id, s.name, AVG(a.grade) as average
        FROM student_profile s
        JOIN assignment_submission a ON s.user_id = a.student_id
        GROUP BY s.user_id, s.name
        ORDER BY average DESC
        LIMIT 10
    """)
    return jsonify({"students": cursor.fetchall()}), 200

if __name__ == '__main__':
    app.run(debug=True)