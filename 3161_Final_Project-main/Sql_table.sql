CREATE DATABASE IF NOT EXISTS course_management;

-- Single User Table
CREATE TABLE user
(
    user_id  INT PRIMARY KEY,
    name     VARCHAR(100) NOT NULL,
    email    VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    role     ENUM('admin', 'lecturer', 'student') NOT NULL
);

-- Student Profile Table (only for students)
CREATE TABLE student_profile
(
    student_id INT PRIMARY KEY,
    gpa        DECIMAL(3,2),
    FOREIGN KEY (student_id) REFERENCES user(user_id)
);

-- Courses
CREATE TABLE course
(
    course_id       INT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    course_code     VARCHAR(10),
    department_name VARCHAR(100),
    lecturer_id     INT, -- Lecturer assigned to course
    FOREIGN KEY (lecturer_id) REFERENCES user(user_id)
);

-- Student - Course Many-to-Many
CREATE TABLE student_course
(
    student_id INT,
    course_id  INT,
    PRIMARY KEY (student_id, course_id),
    FOREIGN KEY (student_id) REFERENCES user(user_id),
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

-- Calendar Events
CREATE TABLE calendar_event
(
    event_id    INT PRIMARY KEY,
    course_id   INT,
    title       VARCHAR(100),
    event_date  DATE,
    description TEXT,
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

-- Forums (Per Course)
CREATE TABLE forum
(
    forum_id  INT PRIMARY KEY,
    name      VARCHAR(100),
    course_id INT,
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

-- Forum Posts (Discussion Threads)
CREATE TABLE forum_post
(
    post_id     INT PRIMARY KEY,
    title       VARCHAR(100),
    post        TEXT,
    user_id     INT,
    forum_id    INT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (forum_id) REFERENCES forum(forum_id)
);

-- Replies (Nested Replies Support)
CREATE TABLE reply
(
    reply_id        INT PRIMARY KEY,
    reply_content   TEXT NOT NULL,
    user_id         INT,
    post_id         INT,
    parent_reply_id INT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (post_id) REFERENCES forum_post(post_id),
    FOREIGN KEY (parent_reply_id) REFERENCES reply(reply_id)
);

-- Course Content (Organized by Sections)
CREATE TABLE course_content
(
    content_id  INT PRIMARY KEY,
    course_id   INT,
    section     VARCHAR(100),
    title       VARCHAR(100),
    link        VARCHAR(255),
    file        BLOB,
    description TEXT,
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

-- Assignments
CREATE TABLE assignment
(
    assignment_id INT PRIMARY KEY,
    name          VARCHAR(100),
    course_id     INT,
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

-- Student Submissions for Assignments
CREATE TABLE assignment_submission
(
    submission_id   INT PRIMARY KEY,
    assignment_id   INT,
    student_id      INT,
    submitted_file  BLOB,
    submission_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    grade           DECIMAL(5,2),
    FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id),
    FOREIGN KEY (student_id) REFERENCES user(user_id)
);

-- Optional: Store Lecturer-Uploaded Resources (PDFs, Videos)
CREATE TABLE course_resource
(
    resource_id INT PRIMARY KEY,
    course_id   INT,
    name        VARCHAR(100),
    content     BLOB,
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

