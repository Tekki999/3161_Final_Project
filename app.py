from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import mysql.connector
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from mysql.connector import Error

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  
app.config['UPLOAD_FOLDER'] = 'uploads'
jwt = JWTManager(app)

# ==============================================
# Database Connection Manager
# ==============================================
def get_db():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="course_management",
            autocommit=False  # We'll manage commits manually
        )
    except Error as e:
        app.logger.error(f"Database connection failed: {str(e)}")
        raise

# ==============================================
# Helper Functions
# ==============================================
def validate_role(required_roles):
    """Check if user has required role"""
    current_role = get_jwt_identity()['role']
    if current_role not in required_roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None

def handle_db_operation(callback, success_message, status_code=200):
    """Handle database operations with proper error handling"""
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        result = callback(db, cursor)
        db.commit()
        return jsonify({"message": success_message, "data": result}), status_code
    except Error as e:
        if db: db.rollback()
        app.logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database operation failed"}), 500
    except Exception as e:
        if db: db.rollback()
        app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Operation failed"}), 500
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

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

    def db_op(db, cursor):
        cursor.execute(
            "INSERT INTO user (user_id, name, email, password, role) VALUES (%s, %s, %s, %s, %s)",
            (data['user_id'], data['name'], data['email'], data['password'], data['role'])
        )
        return {"user_id": data['user_id']}

    return handle_db_operation(db_op, "User registered", 201)

@app.route('/auth/login', methods=['POST'])
def login():
    """Login with credentials, returns JWT token"""
    data = request.get_json()
    
    def db_op(db, cursor):
        cursor.execute(
            "SELECT user_id, role FROM user WHERE email = %s AND password = %s",
            (data['email'], data['password'])
        )
        user = cursor.fetchone()
        if not user:
            raise ValueError("Invalid credentials")
        return create_access_token(identity={'user_id': user['user_id'], 'role': user['role']})

    try:
        token = handle_db_operation(db_op, "Login successful")[0].get_json()['data']
        return jsonify({"token": token}), 200
    except:
        return jsonify({"error": "Invalid credentials"}), 401

# ==============================================
# 2. COURSE MANAGEMENT ENDPOINTS
# ==============================================
@app.route('/courses', methods=['POST'])
@jwt_required()
def create_course():
    """Create a course (admin only)"""
    if validate_role(['admin']):
        return validate_role(['admin'])
    
    data = request.get_json()

    def db_op(db, cursor):
        cursor.execute(
            "INSERT INTO course (course_id, name, lecturer_id) VALUES (%s, %s, %s)",
            (data['course_id'], data['name'], data['lecturer_id'])
        )
        return {"course_id": data['course_id']}

    return handle_db_operation(db_op, "Course created", 201)

@app.route('/courses/<int:course_id>/members', methods=['GET'])
@jwt_required()
def get_course_members(course_id):
    """Get all students enrolled in a course"""
    def db_op(db, cursor):
        cursor.execute("""
            SELECT u.user_id, u.name, u.email 
            FROM user u
            JOIN student_course sc ON u.user_id = sc.student_id
            WHERE sc.course_id = %s
        """, (course_id,))
        return cursor.fetchall()

    return handle_db_operation(db_op, "Course members retrieved")

@app.route('/courses', methods=['GET'])
def get_courses():
    """Get all courses, or filter by student/lecturer"""
    lecturer_id = request.args.get('lecturer_id')
    student_id = request.args.get('student_id')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    offset = (page - 1) * limit

    def db_op(db, cursor):
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
        return cursor.fetchall()

    return handle_db_operation(db_op, "Courses retrieved")

# ==============================================
# 3. ENROLLMENT ENDPOINTS
# ==============================================
@app.route('/courses/<int:course_id>/enroll', methods=['POST'])
@jwt_required()
def enroll(course_id):
    """Enroll a student in a course"""
    student_id = get_jwt_identity()['user_id']

    def db_op(db, cursor):
        # Check if already enrolled
        cursor.execute(
            "SELECT 1 FROM student_course WHERE student_id = %s AND course_id = %s",
            (student_id, course_id)
        )
        if cursor.fetchone():
            raise ValueError("Already enrolled")

        cursor.execute(
            "INSERT INTO student_course (student_id, course_id) VALUES (%s, %s)",
            (student_id, course_id)
        )
        return {"student_id": student_id, "course_id": course_id}

    return handle_db_operation(db_op, "Enrollment successful", 201)

# ==============================================
# 4. CALENDAR EVENT ENDPOINTS
# ==============================================
@app.route('/courses/<int:course_id>/events', methods=['POST'])
@jwt_required()
def create_calendar_event(course_id):
    """Create a calendar event for a course (lecturer/admin only)"""
    if validate_role(['admin', 'lecturer']):
        return validate_role(['admin', 'lecturer'])
    
    data = request.get_json()

    def db_op(db, cursor):
        cursor.execute(
            """INSERT INTO calendar_event 
               (course_id, title, description, event_date, created_by) 
               VALUES (%s, %s, %s, %s, %s)""",
            (course_id, data['title'], data['description'], 
             data['event_date'], get_jwt_identity()['user_id'])
        )
        return {"event_id": cursor.lastrowid}

    return handle_db_operation(db_op, "Event created", 201)

@app.route('/courses/<int:course_id>/events', methods=['GET'])
def get_course_events(course_id):
    """Get all events for a course"""
    def db_op(db, cursor):
        cursor.execute(
            "SELECT * FROM calendar_event WHERE course_id = %s",
            (course_id,)
        )
        return cursor.fetchall()

    return handle_db_operation(db_op, "Events retrieved")

@app.route('/students/<int:student_id>/events', methods=['GET'])
@jwt_required()
def get_student_events(student_id):
    """Get events for a student on a specific date"""
    date = request.args.get('date')  # Expected format: YYYY-MM-DD

    def db_op(db, cursor):
        query = """
            SELECT ce.* FROM calendar_event ce
            JOIN student_course sc ON ce.course_id = sc.course_id
            WHERE sc.student_id = %s
        """
        params = [student_id]
        
        if date:
            query += " AND DATE(ce.event_date) = %s"
            params.append(date)
            
        cursor.execute(query, tuple(params))
        return cursor.fetchall()

    return handle_db_operation(db_op, "Student events retrieved")

# ==============================================
# 5. FORUM ENDPOINTS
# ==============================================
@app.route('/courses/<int:course_id>/forums', methods=['POST'])
@jwt_required()
def create_forum(course_id):
    """Create a forum for a course (lecturer/admin only)"""
    if validate_role(['admin', 'lecturer']):
        return validate_role(['admin', 'lecturer'])
    
    data = request.get_json()

    def db_op(db, cursor):
        cursor.execute(
            "INSERT INTO forum (course_id, name) VALUES (%s, %s)",
            (course_id, data['name'])
        )
        return {"forum_id": cursor.lastrowid}

    return handle_db_operation(db_op, "Forum created", 201)

@app.route('/courses/<int:course_id>/forums', methods=['GET'])
def get_course_forums(course_id):
    """Get all forums for a course"""
    def db_op(db, cursor):
        cursor.execute(
            "SELECT * FROM forum WHERE course_id = %s",
            (course_id,)
        )
        return cursor.fetchall()

    return handle_db_operation(db_op, "Forums retrieved")

@app.route('/forums/<int:forum_id>/threads', methods=['GET'])
def get_forum_threads(forum_id):
    """Get all threads in a forum"""
    def db_op(db, cursor):
        cursor.execute("""
            SELECT fp.*, u.name as author_name 
            FROM forum_post fp
            JOIN user u ON fp.user_id = u.user_id
            WHERE fp.forum_id = %s
        """, (forum_id,))
        return cursor.fetchall()

    return handle_db_operation(db_op, "Threads retrieved")

@app.route('/forums/<int:forum_id>/threads', methods=['POST'])
@jwt_required()
def create_thread(forum_id):
    """Create a discussion thread in a forum"""
    data = request.get_json()
    user_id = get_jwt_identity()['user_id']

    def db_op(db, cursor):
        cursor.execute(
            "INSERT INTO forum_post (forum_id, user_id, title, post) VALUES (%s, %s, %s, %s)",
            (forum_id, user_id, data['title'], data['post'])
        )
        return {"thread_id": cursor.lastrowid}

    return handle_db_operation(db_op, "Thread created", 201)

# ==============================================
# 6. COURSE CONTENT ENDPOINTS
# ==============================================
@app.route('/courses/<int:course_id>/content', methods=['POST'])
@jwt_required()
def add_course_content(course_id):
    """Add course content (lecturer/admin only)"""
    if validate_role(['admin', 'lecturer']):
        return validate_role(['admin', 'lecturer'])
    
    data = request.get_json()

    def db_op(db, cursor):
        cursor.execute(
            """INSERT INTO course_content 
               (course_id, section, title, content_type, content_url, description) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (course_id, data['section'], data['title'], 
             data['content_type'], data.get('content_url'), data.get('description'))
        )
        return {"content_id": cursor.lastrowid}

    return handle_db_operation(db_op, "Content added", 201)

@app.route('/courses/<int:course_id>/content', methods=['GET'])
def get_course_content(course_id):
    """Get all content for a course"""
    def db_op(db, cursor):
        cursor.execute(
            "SELECT * FROM course_content WHERE course_id = %s ORDER BY section",
            (course_id,)
        )
        return cursor.fetchall()

    return handle_db_operation(db_op, "Course content retrieved")

# ==============================================
# 7. ASSIGNMENT ENDPOINTS
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

    def db_op(db, cursor):
        cursor.execute(
            "INSERT INTO assignment_submission (assignment_id, student_id, file_path) VALUES (%s, %s, %s)",
            (assignment_id, student_id, filepath)
        )
        return {"file_path": filepath}

    return handle_db_operation(db_op, "Assignment submitted", 201)

@app.route('/assignments/<int:assignment_id>/grade', methods=['POST'])
@jwt_required()
def grade_assignment(assignment_id):
    """Grade an assignment (lecturer only)"""
    if validate_role(['admin', 'lecturer']):
        return validate_role(['admin', 'lecturer'])
    
    data = request.get_json()

    def db_op(db, cursor):
        # Update grade
        cursor.execute(
            """UPDATE assignment_submission 
               SET grade = %s 
               WHERE assignment_id = %s AND student_id = %s""",
            (data['grade'], assignment_id, data['student_id'])
        )
        
        # Update student's GPA
        cursor.execute("""
            UPDATE student_profile sp
            SET gpa = (
                SELECT AVG(grade) 
                FROM assignment_submission 
                WHERE student_id = %s
            )
            WHERE sp.student_id = %s
        """, (data['student_id'], data['student_id']))
        
        return {"student_id": data['student_id'], "grade": data['grade']}

    return handle_db_operation(db_op, "Grade submitted")

# ==============================================
# 8. REPORT ENDPOINTS
# ==============================================
@app.route('/reports/top-students', methods=['GET'])
def top_students():
    """Get top 10 students by average grade"""
    def db_op(db, cursor):
        cursor.execute("""
            SELECT s.user_id, s.name, AVG(a.grade) as average
            FROM student_profile s
            JOIN assignment_submission a ON s.user_id = a.student_id
            GROUP BY s.user_id, s.name
            ORDER BY average DESC
            LIMIT 10
        """)
        return cursor.fetchall()

    return handle_db_operation(db_op, "Top students retrieved")

@app.route('/reports/popular-courses', methods=['GET'])
def popular_courses():
    """Get courses with ≥50 students"""
    def db_op(db, cursor):
        cursor.execute("""
            SELECT c.course_id, c.name, COUNT(sc.student_id) as enrollment
            FROM course c
            JOIN student_course sc ON c.course_id = sc.course_id
            GROUP BY c.course_id
            HAVING enrollment >= 50
            ORDER BY enrollment DESC
        """)
        return cursor.fetchall()

    return handle_db_operation(db_op, "Popular courses retrieved")

@app.route('/reports/busy-students', methods=['GET'])
def busy_students():
    """Get students taking ≥5 courses"""
    def db_op(db, cursor):
        cursor.execute("""
            SELECT u.user_id, u.name, COUNT(sc.course_id) as course_count
            FROM user u
            JOIN student_course sc ON u.user_id = sc.student_id
            WHERE u.role = 'student'
            GROUP BY u.user_id
            HAVING course_count >= 5
            ORDER BY course_count DESC
        """)
        return cursor.fetchall()

    return handle_db_operation(db_op, "Busy students retrieved")

# ==============================================
# ERROR HANDLERS
# ==============================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
