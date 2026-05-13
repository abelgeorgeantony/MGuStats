-- ============================================================
-- MGU Student Results Analytics Database
-- Target: SQLite  |  Normal Form: 3NF
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;


-- ------------------------------------------------------------
-- 1. LOOKUP: Programmes
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS programmes (
    programme_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_name TEXT    NOT NULL UNIQUE
);


-- ------------------------------------------------------------
-- 2. LOOKUP: Exam Centres
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_centres (
    centre_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_name TEXT    NOT NULL UNIQUE
);


-- ------------------------------------------------------------
-- 3. CORE ENTITY: Students
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    student_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    start_year    INTEGER NOT NULL,          -- The year part of Permanent Register Number
    prn_counter   TEXT    NOT NULL,          -- The global counter part of Permanent Register Number
    student_name  TEXT    NOT NULL,
    programme_id  INTEGER NOT NULL,
    centre_id     INTEGER NOT NULL,
    FOREIGN KEY (programme_id) REFERENCES programmes (programme_id),
    FOREIGN KEY (centre_id)    REFERENCES exam_centres (centre_id)
);

CREATE INDEX IF NOT EXISTS idx_students_id          ON students (student_id);
CREATE INDEX IF NOT EXISTS idx_students_programme_id ON students (programme_id);
CREATE INDEX IF NOT EXISTS idx_students_centre_id    ON students (centre_id);


-- ------------------------------------------------------------
-- 4. CATALOGUE: Courses
--    Each unique course_code is stored once.
--    semester_number is inferred from the course code prefix
--    (e.g., EN1xxx → 1, EN5xxx → 5) and stored for fast filtering.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses (
    course_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code     TEXT    NOT NULL UNIQUE,        -- e.g. 'EN6CRT10'
    course_name     TEXT    NOT NULL,
    credit          INTEGER NOT NULL,               -- Credit weight of the course
    semester_number INTEGER,                        -- 1–6; NULL if undetermined
    course_type     TEXT                            -- e.g. 'Core', 'Common', 'Complementary', 'Open', 'Project'
                    CHECK (course_type IN (
                        'Core', 'Common', 'Complementary', 'Open', 'Project', 'Other'
                    ))
);

CREATE INDEX IF NOT EXISTS idx_courses_course_code     ON courses (course_code);
CREATE INDEX IF NOT EXISTS idx_courses_semester_number ON courses (semester_number);
CREATE INDEX IF NOT EXISTS idx_courses_course_type     ON courses (course_type);


-- ------------------------------------------------------------
-- 5. FACT TABLE: Student-level Semester Aggregates
--    One row per student per semester.
--    Tracks the pass month/year to capture supplementary attempts.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_semester_results (
    sem_result_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        INTEGER NOT NULL,
    semester_number   INTEGER NOT NULL CHECK (semester_number BETWEEN 1 AND 12),
    total_credits     INTEGER NOT NULL,             -- Sum of credits for the semester
    scpa              REAL    NOT NULL,             -- Semester Credit Point Average
    total_marks       INTEGER NOT NULL,             -- Aggregate marks obtained
    max_marks         INTEGER NOT NULL,             -- Aggregate maximum marks
    grade             TEXT    NOT NULL,             -- Semester grade (e.g., 'A', 'B+')
    total_credit_pts  INTEGER NOT NULL,             -- CP = Credit × Grade Point (sum)
    result            TEXT    NOT NULL              -- 'P' (Passed) or 'F' (Failed)
                      CHECK (result IN ('P', 'F')),
    month_year_of_pass TEXT,                        -- e.g., 'September 2021'; NULL if failed
    UNIQUE (student_id, semester_number),
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

CREATE INDEX IF NOT EXISTS idx_ssr_student_id      ON student_semester_results (student_id);
CREATE INDEX IF NOT EXISTS idx_ssr_semester_number ON student_semester_results (semester_number);
CREATE INDEX IF NOT EXISTS idx_ssr_scpa            ON student_semester_results (scpa);
CREATE INDEX IF NOT EXISTS idx_ssr_grade           ON student_semester_results (grade);
CREATE INDEX IF NOT EXISTS idx_ssr_result          ON student_semester_results (result);


-- ------------------------------------------------------------
-- 6. FACT TABLE: Student Subject-level Marks
--    Granular marks per student per course per exam session.
--    exam_session handles supplementary / repeat attempts
--    (e.g., 'November 2022', 'March 2023').
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_subject_marks (
    mark_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL,
    course_id     INTEGER NOT NULL,
    exam_session  TEXT    NOT NULL,                 -- Month + Year of exam, e.g. 'March 2023'
    esa_marks     INTEGER,                          -- External (ESA) marks obtained
    esa_max       INTEGER NOT NULL DEFAULT 80,      -- External maximum (typically 80)
    isa_marks     INTEGER,                          -- Internal (ISA) marks obtained
    isa_max       INTEGER NOT NULL DEFAULT 20,      -- Internal maximum (typically 20)
    total_marks   INTEGER,                          -- ESA + ISA
    total_max     INTEGER NOT NULL DEFAULT 100,     -- Total maximum
    grade         TEXT,                             -- e.g. 'A+', 'A', 'B+', 'B', 'C'
    grade_point   INTEGER,                          -- GP: numeric grade point (5–10)
    credit_point  INTEGER,                          -- CP = Credit × GP
    result        TEXT    NOT NULL                  -- 'Passed' or 'Failed'
                  CHECK (result IN ('Passed', 'Failed')),
    UNIQUE (student_id, course_id, exam_session),
    FOREIGN KEY (student_id) REFERENCES students (student_id),
    FOREIGN KEY (course_id)  REFERENCES courses   (course_id)
);

CREATE INDEX IF NOT EXISTS idx_ssm_student_id   ON student_subject_marks (student_id);
CREATE INDEX IF NOT EXISTS idx_ssm_course_id    ON student_subject_marks (course_id);
CREATE INDEX IF NOT EXISTS idx_ssm_exam_session ON student_subject_marks (exam_session);
CREATE INDEX IF NOT EXISTS idx_ssm_grade        ON student_subject_marks (grade);
CREATE INDEX IF NOT EXISTS idx_ssm_result       ON student_subject_marks (result);
CREATE INDEX IF NOT EXISTS idx_ssm_student_course ON student_subject_marks (student_id, course_id);


-- ------------------------------------------------------------
-- 7. FACT TABLE: Student Final Programme Result (CCPA)
--    One row per student. Terminal aggregate for the full programme.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_final_results (
    final_result_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         INTEGER NOT NULL UNIQUE,     -- One final result per student
    marks_awarded      INTEGER NOT NULL,            -- Total marks across all semesters
    max_marks          INTEGER NOT NULL,            -- Total maximum marks
    ccpa               REAL    NOT NULL,            -- Cumulative Credit Point Average
    total_credit_pts   INTEGER NOT NULL,            -- Sum of all CP across programme
    programme_credit   INTEGER NOT NULL,            -- Total programme credits
    grade              TEXT    NOT NULL,            -- Final programme grade
    result             TEXT    NOT NULL             -- 'P' or 'F'
                       CHECK (result IN ('P', 'F')),
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

CREATE INDEX IF NOT EXISTS idx_sfr_student_id ON student_final_results (student_id);
CREATE INDEX IF NOT EXISTS idx_sfr_ccpa       ON student_final_results (ccpa);
CREATE INDEX IF NOT EXISTS idx_sfr_grade      ON student_final_results (grade);
CREATE INDEX IF NOT EXISTS idx_sfr_result     ON student_final_results (result);


-- ------------------------------------------------------------
-- 8. FACT TABLE: Student Programme Part Results
--    One row per student per programme part
--    (e.g., Common Course I, Core Course, Open Course).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_programme_part_results (
    part_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL,
    part_name      TEXT    NOT NULL,                -- e.g. 'Common Course I : English'
    marks_awarded  INTEGER NOT NULL,
    max_marks      INTEGER NOT NULL,
    ccpa           REAL    NOT NULL,
    credits        INTEGER NOT NULL,
    grade          TEXT    NOT NULL,
    UNIQUE (student_id, part_name),
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

CREATE INDEX IF NOT EXISTS idx_sppr_student_id ON student_programme_part_results (student_id);
CREATE INDEX IF NOT EXISTS idx_sppr_part_name  ON student_programme_part_results (part_name);
CREATE INDEX IF NOT EXISTS idx_sppr_grade      ON student_programme_part_results (grade);