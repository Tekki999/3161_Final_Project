from faker import Faker
import random

fake = Faker()

# Settings
NUM_STUDENTS = 100000      # Increased number of students
NUM_COURSES = 200          # Increased number of courses
NUM_LECTURERS = 40         # Increased number of lecturers to handle 200 courses
NUM_ADMINS = 1             # Keeping 1 admin

# Data Containers
users = []
student_profiles = []
courses = []
student_courses = []
lecturers = []
admin = []
course_assignments = {}

user_id_counter = 1

# --- Admin ---
admin.append((user_id_counter, fake.name(), fake.email(), 'adminpass', 'admin'))
user_id_counter += 1

# --- Lecturers ---
for _ in range(NUM_LECTURERS):
    lecturers.append((user_id_counter, fake.name(), fake.email(), 'lecturerpass', 'lecturer'))
    user_id_counter += 1

# --- Students ---
for _ in range(NUM_STUDENTS):
    users.append((user_id_counter, fake.name(), fake.email(), 'studentpass', 'student'))
    student_profiles.append((user_id_counter, round(random.uniform(2.0, 4.0), 2)))
    user_id_counter += 1

# --- Courses ---
for course_id in range(1, NUM_COURSES + 1):
    courses.append((course_id, fake.catch_phrase(), f"CSE{1000 + course_id}", fake.word()))

# --- Assign Lecturers to Courses ---
# Each lecturer teaches 1-5 courses
available_courses = list(range(1, NUM_COURSES + 1))
random.shuffle(available_courses)

lecturer_course_map = {lecturer[0]: [] for lecturer in lecturers}

for course_id in available_courses:
    eligible_lecturers = [lid for lid, c in lecturer_course_map.items() if len(c) < 5]
    selected_lecturer = random.choice(eligible_lecturers)
    lecturer_course_map[selected_lecturer].append(course_id)
    course_assignments[course_id] = selected_lecturer

# --- Enroll Students ---
# Each student must be enrolled in 3-6 courses
for student in student_profiles:
    enrolled_courses = random.sample(list(course_assignments.keys()), random.randint(3, 6))
    for course_id in enrolled_courses:
        student_courses.append((student[0], course_id))

# --- Ensure Each Course Has at Least 10 Students ---
course_membership = {cid: [] for cid in course_assignments.keys()}

for student_id, course_id in student_courses:
    course_membership[course_id].append(student_id)

for course_id, members in course_membership.items():
    if len(members) < 10:
        needed = 10 - len(members)
        available_students = [s[0] for s in student_profiles if s[0] not in members]
        selected_students = random.sample(available_students, needed)
        for student_id in selected_students:
            student_courses.append((student_id, course_id))

# --- Generate SQL ---

# Admin
print("-- Insert Admins")
for entry in admin:
    print(f"INSERT INTO user (user_id, name, email, password, role) VALUES ({entry[0]}, '{entry[1]}', '{entry[2]}', '{entry[3]}', '{entry[4]}');")

# Lecturers
print("\n-- Insert Lecturers")
for entry in lecturers:
    print(f"INSERT INTO user (user_id, name, email, password, role) VALUES ({entry[0]}, '{entry[1]}', '{entry[2]}', '{entry[3]}', '{entry[4]}');")

# Students
print("\n-- Insert Students")
for entry in users:
    print(f"INSERT INTO user (user_id, name, email, password, role) VALUES ({entry[0]}, '{entry[1]}', '{entry[2]}', '{entry[3]}', '{entry[4]}');")

# Student Profiles
print("\n-- Insert Student Profiles")
for entry in student_profiles:
    print(f"INSERT INTO student_profile (student_id, gpa) VALUES ({entry[0]}, {entry[1]});")

# Courses
print("\n-- Insert Courses")
for entry in courses:
    lecturer_id = course_assignments[entry[0]]
    print(f"INSERT INTO course (course_id, name, course_code, department_name, lecturer_id) VALUES ({entry[0]}, '{entry[1]}', '{entry[2]}', '{entry[3]}', {lecturer_id});")

# Student Course Enrollment
print("\n-- Insert Student Course Enrollments")
for entry in student_courses:
    print(f"INSERT INTO student_course (student_id, course_id) VALUES ({entry[0]}, {entry[1]});")
