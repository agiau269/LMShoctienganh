import streamlit as st
import sqlite3
import hashlib
import hmac
import os
import secrets
import string
from datetime import datetime
from pathlib import Path
import pandas as pd

# ============================================================
# ENGLISHHUB LMS
# BẢN TIẾNG VIỆT
# ============================================================

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "englishhub.db"

UPLOAD_DIR = BASE_DIR / "uploads"
VIDEO_DIR = UPLOAD_DIR / "videos"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="EnglishHub LMS",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# GIAO DIỆN
# ============================================================

st.markdown("""
<style>

.main {
    background-color: #f7f9fc;
}

.hero {
    padding: 30px;
    border-radius: 18px;
    background: linear-gradient(
        135deg,
        #eaf2ff,
        #f8fbff
    );
    margin-bottom: 25px;
}

.card {
    padding: 22px;
    border-radius: 16px;
    background: white;
    border: 1px solid #e5e7eb;
    margin-bottom: 15px;
}

.student-name {
    font-size: 21px;
    font-weight: 700;
    margin-top: 8px;
    margin-bottom: 8px;
}

.badge {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 20px;
    background: #eef4ff;
    color: #2563eb;
    font-size: 13px;
    font-weight: 600;
}

.small {
    color: #6b7280;
    font-size: 14px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE
# ============================================================

def connect():
    con = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )
    con.row_factory = sqlite3.Row
    return con


def init_db():

    con = connect()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        class_id INTEGER,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        class_name TEXT NOT NULL,
        access_code TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        level TEXT,
        category TEXT,
        content TEXT,
        resource_url TEXT,
        video_file TEXT,
        video_name TEXT,
        teacher_id INTEGER,
        class_id INTEGER,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        lesson_id INTEGER,
        instructions TEXT,
        questions TEXT,
        max_score INTEGER DEFAULT 100,
        teacher_id INTEGER,
        class_id INTEGER,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        answer TEXT,
        score REAL DEFAULT 0,
        feedback TEXT,
        submitted_at TEXT NOT NULL,
        UNIQUE(exercise_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS lesson_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        first_viewed TEXT NOT NULL,
        last_viewed TEXT NOT NULL,
        view_count INTEGER DEFAULT 1,
        UNIQUE(lesson_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        action TEXT NOT NULL,
        object_name TEXT,
        created_at TEXT NOT NULL
    );
    """)

    con.commit()
    con.close()


init_db()


# ============================================================
# DATABASE MIGRATION
# ============================================================

def migrate_database():

    con = connect()

    # USERS
    user_columns = [
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "class_id" not in user_columns:
        con.execute(
            "ALTER TABLE users ADD COLUMN class_id INTEGER"
        )

    # LESSONS
    lesson_columns = [
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(lessons)"
        ).fetchall()
    ]

    if "video_file" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN video_file TEXT"
        )

    if "video_name" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN video_name TEXT"
        )

    if "teacher_id" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN teacher_id INTEGER"
        )

    if "class_id" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN class_id INTEGER"
        )

    # EXERCISES
    exercise_columns = [
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(exercises)"
        ).fetchall()
    ]

    if "teacher_id" not in exercise_columns:
        con.execute(
            "ALTER TABLE exercises ADD COLUMN teacher_id INTEGER"
        )

    if "class_id" not in exercise_columns:
        con.execute(
            "ALTER TABLE exercises ADD COLUMN class_id INTEGER"
        )

    con.commit()
    con.close()


migrate_database()


# ============================================================
# SYSTEM
# ============================================================

def now():
    return datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )


def teacher_code():

    try:
        return st.secrets["LMS_TEACHER_CODE"]

    except Exception:

        return os.getenv(
            "LMS_TEACHER_CODE",
            "THAY-MA-GIAO-VIEN"
        )


def password_hash(password):

    salt = os.urandom(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        120000
    )

    return salt.hex() + ":" + key.hex()


def check_password(password, stored):

    try:

        salt, key = stored.split(":")

        new_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt),
            120000
        )

        return hmac.compare_digest(
            new_key.hex(),
            key
        )

    except Exception:

        return False


def execute(sql, params=()):

    con = connect()

    cur = con.execute(
        sql,
        params
    )

    con.commit()

    result = cur.lastrowid

    con.close()

    return result


def fetch(sql, params=()):

    con = connect()

    rows = con.execute(
        sql,
        params
    ).fetchall()

    con.close()

    return rows


def log_activity(
    student_id,
    action,
    object_name=""
):

    execute("""
        INSERT INTO activity
        (
            student_id,
            action,
            object_name,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        student_id,
        action,
        object_name,
        now()
    ))


# ============================================================
# TẠO MÃ LỚP
# ============================================================

def generate_class_code():

    chars = string.ascii_uppercase + string.digits

    while True:

        code = "-".join([
            "".join(
                secrets.choice(chars)
                for _ in range(4)
            ),
            "".join(
                secrets.choice(chars)
                for _ in range(4)
            )
        ])

        exists = fetch("""
            SELECT id
            FROM classes
            WHERE access_code=?
        """, (code,))

        if not exists:
            return code


# ============================================================
# CLASS
# ============================================================

def create_class(
    teacher_id,
    class_name
):

    class_name = class_name.strip()

    if not class_name:
        return False, "Vui lòng nhập tên lớp."

    code = generate_class_code()

    execute("""
        INSERT INTO classes
        (
            teacher_id,
            class_name,
            access_code,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        teacher_id,
        class_name,
        code,
        now()
    ))

    return True, code


def teacher_classes(teacher_id):

    return fetch("""
        SELECT *
        FROM classes
        WHERE teacher_id=?
        ORDER BY created_at DESC
    """, (teacher_id,))


# ============================================================
# REGISTER
# ============================================================

def register(
    full_name,
    username,
    password,
    role,
    code=""
):

    full_name = full_name.strip()
    username = username.strip().lower()

    if not full_name or not username or not password:

        return False, "Vui lòng điền đầy đủ thông tin."

    if len(password) < 6:

        return False, "Mật khẩu phải có ít nhất 6 ký tự."

    # --------------------------------------------------------
    # TEACHER
    # --------------------------------------------------------

    if role == "teacher":

        if not hmac.compare_digest(
            code,
            teacher_code()
        ):

            return False, (
                "Mã truy cập giáo viên không chính xác."
            )

        class_id = None

    # --------------------------------------------------------
    # STUDENT
    # --------------------------------------------------------

    else:

        code = code.strip().upper()

        class_rows = fetch("""
            SELECT id
            FROM classes
            WHERE access_code=?
        """, (code,))

        if not class_rows:

            return False, (
                "Mã lớp không chính xác. "
                "Hãy nhập mã do giáo viên cung cấp."
            )

        class_id = class_rows[0]["id"]

    try:

        execute("""
            INSERT INTO users
            (
                full_name,
                username,
                password_hash,
                role,
                class_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            full_name,
            username,
            password_hash(password),
            role,
            class_id,
            now()
        ))

        return True, "Tạo tài khoản thành công."

    except sqlite3.IntegrityError:

        return False, (
            "Tên đăng nhập này đã tồn tại."
        )


# ============================================================
# LOGIN
# ============================================================

def login(
    username,
    password,
    role
):

    rows = fetch("""
        SELECT *
        FROM users
        WHERE username=?
        AND role=?
    """, (
        username.strip().lower(),
        role
    ))

    if rows:

        if check_password(
            password,
            rows[0]["password_hash"]
        ):

            return dict(rows[0])

    return None


# ============================================================
# PROGRESS
# ============================================================

def student_progress(student_id):

    total_lessons = fetch(
        "SELECT COUNT(*) n FROM lessons"
    )[0]["n"]

    viewed_lessons = fetch("""
        SELECT COUNT(*) n
        FROM lesson_views
        WHERE student_id=?
    """, (
        student_id,
    ))[0]["n"]

    total_exercises = fetch(
        "SELECT COUNT(*) n FROM exercises"
    )[0]["n"]

    completed_exercises = fetch("""
        SELECT COUNT(*) n
        FROM submissions
        WHERE student_id=?
    """, (
        student_id,
    ))[0]["n"]

    avg = fetch("""
        SELECT AVG(
            CASE
                WHEN e.max_score > 0
                THEN s.score * 100.0 / e.max_score
                ELSE 0
            END
        ) a
        FROM submissions s
        JOIN exercises e
        ON e.id=s.exercise_id
        WHERE s.student_id=?
    """, (
        student_id,
    ))[0]["a"]

    average = float(avg or 0)

    lesson_rate = (
        viewed_lessons /
        total_lessons *
        100
        if total_lessons
        else 0
    )

    exercise_rate = (
        completed_exercises /
        total_exercises *
        100
        if total_exercises
        else 0
    )

    participation = round(
        lesson_rate * 0.4 +
        exercise_rate * 0.6 *
        (
            average / 100
            if total_exercises
            else 0
        ),
        1
    )

    return {
        "total_lessons": total_lessons,
        "viewed_lessons": viewed_lessons,
        "total_exercises": total_exercises,
        "completed_exercises": completed_exercises,
        "average": round(average, 1),
        "participation": participation
    }


# ============================================================
# LOGIN PAGE
# ============================================================

def login_page():

    st.markdown("""
    <div class="hero">

        <h1>EnglishHub LMS</h1>

        <p>
        Nền tảng học tiếng Anh dành cho lớp học.
        </p>

    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns(2)

    # ========================================================
    # LOGIN
    # ========================================================

    with left:

        st.markdown("### Đăng nhập")

        role = st.radio(
            "Bạn là:",
            [
                "Học sinh",
                "Giáo viên"
            ],
            horizontal=True
        )

        role_db = (
            "student"
            if role == "Học sinh"
            else "teacher"
        )

        with st.form("login_form"):

            username = st.text_input(
                "Tên đăng nhập"
            )

            password = st.text_input(
                "Mật khẩu",
                type="password"
            )

            submit = st.form_submit_button(
                "Đăng nhập",
                use_container_width=True
            )

        if submit:

            user = login(
                username,
                password,
                role_db
            )

            if user:

                st.session_state.user = user

                st.rerun()

            else:

                st.error(
                    "Tên đăng nhập, mật khẩu "
                    "hoặc loại tài khoản không chính xác."
                )

    # ========================================================
    # REGISTER
    # ========================================================

    with right:

        st.markdown("### Tạo tài khoản")

        st.info(
            "Học sinh bắt buộc phải có "
            "Mã lớp do giáo viên cung cấp."
        )

        with st.form("register_form"):

            full_name = st.text_input(
                "Họ và tên"
            )

            username = st.text_input(
                "Tên đăng nhập"
            )

            password = st.text_input(
                "Mật khẩu",
                type="password"
            )

            role = st.selectbox(
                "Loại tài khoản",
                [
                    "Học sinh",
                    "Giáo viên"
                ]
            )

            role_db = (
                "student"
                if role == "Học sinh"
                else "teacher"
            )

            code = ""

            if role_db == "teacher":

                code = st.text_input(
                    "Mã truy cập giáo viên",
                    type="password"
                )

            else:

                code = st.text_input(
                    "Mã lớp học",
                    placeholder="Ví dụ: ABCD-1234"
                )

            submit = st.form_submit_button(
                "Tạo tài khoản",
                use_container_width=True
            )

        if submit:

            ok, message = register(
                full_name,
                username,
                password,
                role_db,
                code
            )

            if ok:

                st.success(message)

            else:

                st.error(message)


# ============================================================
# TEACHER SIDEBAR
# ============================================================

def teacher_sidebar():

    with st.sidebar:

        st.markdown("## EnglishHub LMS")

        st.caption(
            f"Giáo viên: "
            f"{st.session_state.user['full_name']}"
        )

        page = st.radio(
            "MENU GIÁO VIÊN",
            [
                "Tổng quan",
                "Lớp học & mã học sinh",
                "Bài giảng",
                "Tạo bài giảng",
                "Bài tập & chấm điểm",
                "Tạo bài tập",
                "Học sinh",
                "Lượt xem bài giảng",
                "Hoạt động học tập"
            ]
        )

        if st.button(
            "Đăng xuất",
            use_container_width=True
        ):

            st.session_state.user = None

            st.rerun()

    return page


# ============================================================
# TEACHER DASHBOARD
# ============================================================

def teacher_dashboard():

    teacher_id = st.session_state.user["id"]

    st.markdown("""
    <div class="hero">

        <h1>Tổng quan lớp học</h1>

        <p>
        Quản lý bài giảng, bài tập,
        mã lớp và tiến độ học sinh.
        </p>

    </div>
    """, unsafe_allow_html=True)

    students = fetch("""
        SELECT COUNT(*) n
        FROM users
        WHERE role='student'
        AND class_id IN (
            SELECT id
            FROM classes
            WHERE teacher_id=?
        )
    """, (
        teacher_id,
    ))[0]["n"]

    lessons = fetch("""
        SELECT COUNT(*) n
        FROM lessons
        WHERE teacher_id=?
    """, (
        teacher_id,
    ))[0]["n"]

    exercises = fetch("""
        SELECT COUNT(*) n
        FROM exercises
        WHERE teacher_id=?
    """, (
        teacher_id,
    ))[0]["n"]

    submissions = fetch("""
        SELECT COUNT(*) n
        FROM submissions s
        JOIN exercises e
        ON e.id=s.exercise_id
        WHERE e.teacher_id=?
    """, (
        teacher_id,
    ))[0]["n"]

    a, b, c, d = st.columns(4)

    a.metric(
        "Học sinh",
        students
    )

    b.metric(
        "Bài giảng",
        lessons
    )

    c.metric(
        "Bài tập",
        exercises
    )

    d.metric(
        "Bài đã nộp",
        submissions
    )

    st.markdown("### Tiến độ học sinh")

    students_data = fetch("""
        SELECT id, full_name, username, created_at
        FROM users
        WHERE role='student'
        AND class_id IN (
            SELECT id
            FROM classes
            WHERE teacher_id=?
        )
        ORDER BY full_name
    """, (
        teacher_id,
    ))

    data = []

    for student in students_data:

        p = student_progress(
            student["id"]
        )

        data.append({
            "Họ và tên":
                student["full_name"],

            "Tên đăng nhập":
                student["username"],

            "Bài giảng":
                f"{p['viewed_lessons']}/"
                f"{p['total_lessons']}",

            "Bài tập":
                f"{p['completed_exercises']}/"
                f"{p['total_exercises']}",

            "Điểm trung bình":
                f"{p['average']}%",

            "Mức độ tham gia":
                f"{p['participation']}%"
        })

    if data:

        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Chưa có học sinh đăng ký vào lớp."
        )


# ============================================================
# TEACHER CLASS MANAGEMENT
# ============================================================

def teacher_class_management():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Lớp học & mã học sinh"
    )

    st.write(
        "Tại đây giáo viên có thể tạo mã lớp. "
        "Học sinh phải nhập đúng mã này "
        "khi đăng ký tài khoản."
    )

    # --------------------------------------------------------
    # CREATE CLASS
    # --------------------------------------------------------

    with st.form("create_class_form"):

        class_name = st.text_input(
            "Tên lớp",
            placeholder="Ví dụ: English C1 - Class 01"
        )

        submit = st.form_submit_button(
            "Tạo mã lớp",
            use_container_width=True
        )

    if submit:

        ok, result = create_class(
            teacher_id,
            class_name
        )

        if ok:

            st.success(
                "Đã tạo lớp thành công."
            )

            st.code(
                result,
                language=None
            )

            st.info(
                "Gửi mã này cho học sinh "
                "để các bạn đăng ký tài khoản."
            )

        else:

            st.error(result)

    # --------------------------------------------------------
    # EXISTING CLASSES
    # --------------------------------------------------------

    st.markdown("### Các lớp của bạn")

    classes = teacher_classes(
        teacher_id
    )

    if not classes:

        st.info(
            "Bạn chưa tạo lớp nào."
        )

        return

    for class_item in classes:

        students = fetch("""
            SELECT COUNT(*) n
            FROM users
            WHERE class_id=?
            AND role='student'
        """, (
            class_item["id"],
        ))[0]["n"]

        st.markdown(
            f"""
            <div class="card">

                <div class="student-name">
                    {class_item["class_name"]}
                </div>

                <p>
                    Mã lớp:
                    <strong>
                        {class_item["access_code"]}
                    </strong>
                </p>

                <span class="small">
                    Số học sinh: {students}
                </span>

            </div>
            """,
            unsafe_allow_html=True
        )

        st.code(
            class_item["access_code"],
            language=None
        )


# ============================================================
# TEACHER LESSONS
# ============================================================

def teacher_lessons():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Danh sách bài giảng"
    )

    lessons = fetch("""
        SELECT
            l.*,
            c.class_name,
            COUNT(v.id)
                AS so_hoc_sinh_da_xem
        FROM lessons l

        LEFT JOIN classes c
        ON c.id=l.class_id

        LEFT JOIN lesson_views v
        ON v.lesson_id=l.id

        WHERE l.teacher_id=?

        GROUP BY l.id

        ORDER BY l.created_at DESC
    """, (
        teacher_id,
    ))

    if not lessons:

        st.info(
            "Chưa có bài giảng."
        )

        return

    for lesson in lessons:

        st.markdown(
            f"""
            <div class="card">

                <span class="badge">
                    {lesson["level"]}
                    •
                    {lesson["category"]}
                </span>

                <div class="student-name">
                    {lesson["title"]}
                </div>

                <p>
                    {lesson["description"] or ""}
                </p>

                <span class="small">
                    Lớp:
                    {lesson["class_name"] or "Không xác định"}
                    <br>
                    Số học sinh đã xem:
                    {lesson["so_hoc_sinh_da_xem"]}
                </span>

            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander(
            "Xem nội dung bài giảng"
        ):

            if lesson["video_file"]:

                video_path = Path(
                    lesson["video_file"]
                )

                if video_path.exists():

                    st.video(
                        str(video_path)
                    )

                    st.caption(
                        "Video: "
                        +
                        (
                            lesson["video_name"]
                            or video_path.name
                        )
                    )

                else:

                    st.warning(
                        "Không tìm thấy file video."
                    )

            st.markdown(
                lesson["content"] or ""
            )

            if lesson["resource_url"]:

                st.link_button(
                    "Mở tài liệu bên ngoài",
                    lesson["resource_url"]
                )


# ============================================================
# CREATE LESSON
# ============================================================

def create_lesson():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Tạo bài giảng mới"
    )

    classes = teacher_classes(
        teacher_id
    )

    if not classes:

        st.warning(
            "Bạn cần tạo ít nhất một lớp "
            "trước khi đăng bài giảng."
        )

        return

    class_options = {
        c["class_name"]: c["id"]
        for c in classes
    }

    with st.form("create_lesson"):

        title = st.text_input(
            "Tên bài giảng"
        )

        description = st.text_area(
            "Mô tả ngắn"
        )

        selected_class = st.selectbox(
            "Lớp học",
            list(class_options.keys())
        )

        a, b = st.columns(2)

        level = a.selectbox(
            "Trình độ CEFR",
            [
                "A1",
                "A2",
                "B1",
                "B2",
                "C1",
                "C2"
            ]
        )

        category = b.selectbox(
            "Chủ đề",
            [
                "Ngữ pháp",
                "Từ vựng",
                "Đọc",
                "Nghe",
                "Nói",
                "Viết",
                "Luyện thi",
                "Tiếng Anh tổng quát"
            ]
        )

        content = st.text_area(
            "Nội dung bài giảng",
            height=400,
            placeholder="""
# Present Perfect

## Công thức

Subject + have/has + V3

## Ví dụ

I have studied English for three years.

## Bài tập

Complete the sentences...
"""
        )

        st.markdown(
            "### Video bài giảng"
        )

        st.caption(
            "Bạn có thể tải video trực tiếp "
            "từ máy tính lên website."
        )

        video = st.file_uploader(
            "Chọn video",
            type=[
                "mp4",
                "mov",
                "webm",
                "m4v"
            ]
        )

        if video is not None:

            st.video(video)

            st.caption(
                f"Video đã chọn: {video.name}"
            )

        resource = st.text_input(
            "Đường dẫn tài liệu bên ngoài "
            "(nếu có)"
        )

        submit = st.form_submit_button(
            "Đăng bài giảng",
            use_container_width=True
        )

    if submit:

        if not title or not content:

            st.error(
                "Tên bài giảng và nội dung "
                "không được để trống."
            )

            return

        video_file = None
        video_name = None

        if video is not None:

            safe_name = (
                Path(video.name)
                .name
                .replace(" ", "_")
            )

            unique_name = (
                datetime.now().strftime(
                    "%Y%m%d_%H%M%S_%f"
                )
                +
                "_"
                +
                safe_name
            )

            video_path = (
                VIDEO_DIR /
                unique_name
            )

            with open(
                video_path,
                "wb"
            ) as f:

                f.write(
                    video.getbuffer()
                )

            video_file = str(
                video_path
            )

            video_name = video.name

        execute("""
            INSERT INTO lessons
            (
                title,
                description,
                level,
                category,
                content,
                resource_url,
                video_file,
                video_name,
                teacher_id,
                class_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            description,
            level,
            category,
            content,
            resource,
            video_file,
            video_name,
            teacher_id,
            class_options[selected_class],
            now()
        ))

        st.success(
            "Đã đăng bài giảng thành công."
        )

        st.rerun()


# ============================================================
# CREATE EXERCISE
# ============================================================

def create_exercise():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Tạo bài tập mới"
    )

    classes = teacher_classes(
        teacher_id
    )

    if not classes:

        st.warning(
            "Bạn cần tạo lớp trước."
        )

        return

    lessons = fetch("""
        SELECT id, title
        FROM lessons
        WHERE teacher_id=?
        ORDER BY title
    """, (
        teacher_id,
    ))

    lesson_dict = {
        "Không liên kết bài giảng":
            None
    }

    for lesson in lessons:

        lesson_dict[
            lesson["title"]
        ] = lesson["id"]

    class_dict = {
        c["class_name"]: c["id"]
        for c in classes
    }

    with st.form("create_exercise"):

        title = st.text_input(
            "Tên bài tập"
        )

        selected_class = st.selectbox(
            "Lớp học",
            list(class_dict.keys())
        )

        linked = st.selectbox(
            "Bài giảng liên quan",
            list(lesson_dict.keys())
        )

        instructions = st.text_area(
            "Hướng dẫn làm bài"
        )

        questions = st.text_area(
            "Nội dung câu hỏi / yêu cầu",
            height=300
        )

        max_score = st.number_input(
            "Thang điểm tối đa",
            min_value=1,
            max_value=100,
            value=100
        )

        submit = st.form_submit_button(
            "Đăng bài tập",
            use_container_width=True
        )

    if submit:

        if not title or not questions:

            st.error(
                "Tên bài tập và nội dung "
                "câu hỏi là bắt buộc."
            )

            return

        execute("""
            INSERT INTO exercises
            (
                title,
                lesson_id,
                instructions,
                questions,
                max_score,
                teacher_id,
                class_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            lesson_dict[linked],
            instructions,
            questions,
            max_score,
            teacher_id,
            class_dict[selected_class],
            now()
        ))

        st.success(
            "Đã đăng bài tập thành công."
        )

        st.rerun()


# ============================================================
# TEACHER EXERCISES
# ============================================================

def teacher_exercises():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Bài tập và chấm điểm"
    )

    submissions = fetch("""
        SELECT
            s.id,
            s.answer,
            s.score,
            s.feedback,
            s.submitted_at,

            u.full_name
                AS student_name,

            e.title
                AS exercise_title,

            e.max_score

        FROM submissions s

        JOIN users u
        ON u.id=s.student_id

        JOIN exercises e
        ON e.id=s.exercise_id

        WHERE e.teacher_id=?

        ORDER BY s.submitted_at DESC
    """, (
        teacher_id,
    ))

    if not submissions:

        st.info(
            "Chưa có học sinh nộp bài."
        )

        return

    for submission in submissions:

        st.markdown(
            f"### "
            f"{submission['student_name']} "
            f"— "
            f"{submission['exercise_title']}"
        )

        st.write(
            "**Bài làm của học sinh:**"
        )

        st.write(
            submission["answer"]
            or "(Không có nội dung)"
        )

        with st.form(
            f"grade_{submission['id']}"
        ):

            score = st.number_input(
                "Điểm",
                0.0,
                float(
                    submission["max_score"]
                ),
                float(
                    submission["score"] or 0
                ),
                step=1.0
            )

            feedback = st.text_area(
                "Nhận xét cho học sinh",
                value=(
                    submission["feedback"]
                    or ""
                )
            )

            save = st.form_submit_button(
                "Lưu điểm và nhận xét",
                use_container_width=True
            )

        if save:

            execute("""
                UPDATE submissions
                SET score=?,
                    feedback=?
                WHERE id=?
            """, (
                score,
                feedback,
                submission["id"]
            ))

            st.success(
                "Đã lưu điểm và nhận xét."
            )

            st.rerun()


# ============================================================
# TEACHER STUDENTS
# ============================================================

def teacher_students():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Quản lý học sinh"
    )

    students = fetch("""
        SELECT
            u.*,
            c.class_name
        FROM users u

        LEFT JOIN classes c
        ON c.id=u.class_id

        WHERE u.role='student'

        AND c.teacher_id=?

        ORDER BY u.full_name
    """, (
        teacher_id,
    ))

    if not students:

        st.info(
            "Chưa có học sinh."
        )

        return

    student_names = [
        student["full_name"]
        for student in students
    ]

    selected_name = st.selectbox(
        "Chọn học sinh",
        student_names
    )

    student = next(
        s
        for s in students
        if s["full_name"] == selected_name
    )

    p = student_progress(
        student["id"]
    )

    st.markdown(
        f"""
        <div class="card">

            <div class="student-name">
                {student["full_name"]}
            </div>

            <div class="small">
                Tên đăng nhập:
                {student["username"]}
            </div>

            <div class="small">
                Lớp:
                {student["class_name"] or "—"}
            </div>

            <div class="small">
                Ngày tham gia:
                {student["created_at"]}
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Mức độ tham gia",
        f"{p['participation']}%"
    )

    b.metric(
        "Bài giảng",
        f"{p['viewed_lessons']}/"
        f"{p['total_lessons']}"
    )

    c.metric(
        "Bài tập",
        f"{p['completed_exercises']}/"
        f"{p['total_exercises']}"
    )

    d.metric(
        "Điểm trung bình",
        f"{p['average']}%"
    )

    st.progress(
        p["participation"] / 100,
        text=(
            f"Mức độ tham gia: "
            f"{p['participation']}%"
        )
    )

    # --------------------------------------------------------
    # LESSON HISTORY
    # --------------------------------------------------------

    st.markdown(
        "### Lịch sử học bài"
    )

    views = fetch("""
        SELECT
            l.title AS "Bài giảng",
            l.level AS "Trình độ",
            l.category AS "Chủ đề",
            v.first_viewed AS "Lần xem đầu",
            v.last_viewed AS "Lần xem gần nhất",
            v.view_count AS "Số lần xem"

        FROM lesson_views v

        JOIN lessons l
        ON l.id=v.lesson_id

        WHERE v.student_id=?

        ORDER BY v.last_viewed DESC
    """, (
        student["id"],
    ))

    if views:

        st.dataframe(
            pd.DataFrame(
                [dict(v) for v in views]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Học sinh này chưa xem bài giảng."
        )

    # --------------------------------------------------------
    # EXERCISE RESULTS
    # --------------------------------------------------------

    st.markdown(
        "### Kết quả bài tập"
    )

    results = fetch("""
        SELECT
            e.title AS "Bài tập",
            s.score AS "Điểm",
            e.max_score AS "Điểm tối đa",
            s.feedback AS "Nhận xét",
            s.submitted_at AS "Thời gian nộp"

        FROM submissions s

        JOIN exercises e
        ON e.id=s.exercise_id

        WHERE s.student_id=?

        ORDER BY s.submitted_at DESC
    """, (
        student["id"],
    ))

    if results:

        st.dataframe(
            pd.DataFrame(
                [dict(r) for r in results]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Học sinh này chưa nộp bài."
        )


# ============================================================
# LESSON VIEWS
# ============================================================

def teacher_lesson_views():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Lượt xem bài giảng"
    )

    lessons = fetch("""
        SELECT id, title
        FROM lessons
        WHERE teacher_id=?
        ORDER BY title
    """, (
        teacher_id,
    ))

    if not lessons:

        st.info(
            "Chưa có bài giảng."
        )

        return

    selected = st.selectbox(
        "Chọn bài giảng",
        lessons,
        format_func=lambda x: x["title"]
    )

    rows = fetch("""
        SELECT
            u.full_name AS "Họ và tên",
            u.username AS "Tên đăng nhập",
            v.first_viewed AS "Lần xem đầu",
            v.last_viewed AS "Lần xem gần nhất",
            v.view_count AS "Số lần xem"

        FROM lesson_views v

        JOIN users u
        ON u.id=v.student_id

        WHERE v.lesson_id=?

        ORDER BY v.last_viewed DESC
    """, (
        selected["id"],
    ))

    st.markdown(
        f"### Học sinh đã xem: "
        f"{selected['title']}"
    )

    if rows:

        st.dataframe(
            pd.DataFrame(
                [dict(r) for r in rows]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Chưa có học sinh nào xem bài."
        )


# ============================================================
# ACTIVITY
# ============================================================

def teacher_activity():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Hoạt động học tập"
    )

    rows = fetch("""
        SELECT
            a.created_at AS "Thời gian",
            u.full_name AS "Học sinh",
            a.action AS "Hoạt động",
            a.object_name AS "Nội dung"

        FROM activity a

        LEFT JOIN users u
        ON u.id=a.student_id

        LEFT JOIN classes c
        ON c.id=u.class_id

        WHERE c.teacher_id=?

        ORDER BY a.created_at DESC

        LIMIT 300
    """, (
        teacher_id,
    ))

    if rows:

        st.dataframe(
            pd.DataFrame(
                [dict(r) for r in rows]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Chưa có hoạt động học tập."
        )


# ============================================================
# STUDENT SIDEBAR
# ============================================================

def student_sidebar():

    with st.sidebar:

        st.markdown(
            "## EnglishHub LMS"
        )

        st.caption(
            f"Học sinh: "
            f"{st.session_state.user['full_name']}"
        )

        page = st.radio(
            "MENU HỌC SINH",
            [
                "Trang chủ",
                "Bài giảng",
                "Bài tập",
                "Tiến độ học tập"
            ]
        )

        if st.button(
            "Đăng xuất",
            use_container_width=True
        ):

            st.session_state.user = None

            st.rerun()

    return page


# ============================================================
# STUDENT DASHBOARD
# ============================================================

def student_dashboard():

    user = st.session_state.user

    p = student_progress(
        user["id"]
    )

    st.markdown(
        f"""
        <div class="hero">

            <h1>
                Xin chào,
                {user["full_name"]}!
            </h1>

            <p>
                Chào mừng bạn quay lại
                EnglishHub.
                Hãy tiếp tục hành trình
                học tiếng Anh của mình.
            </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Mức độ tham gia",
        f"{p['participation']}%"
    )

    b.metric(
        "Bài giảng đã học",
        f"{p['viewed_lessons']}/"
        f"{p['total_lessons']}"
    )

    c.metric(
        "Bài tập đã làm",
        f"{p['completed_exercises']}/"
        f"{p['total_exercises']}"
    )

    d.metric(
        "Điểm trung bình",
        f"{p['average']}%"
    )

    st.markdown(
        "### Tiếp tục học"
    )

    lessons = fetch("""
        SELECT
            l.*,

            CASE
                WHEN v.id IS NULL
                THEN 0
                ELSE 1
            END AS viewed

        FROM lessons l

        LEFT JOIN lesson_views v

        ON v.lesson_id=l.id

        AND v.student_id=?

        WHERE l.class_id=?

        ORDER BY viewed ASC,
        l.created_at DESC
    """, (
        user["id"],
        user["class_id"]
    ))

    if not lessons:

        st.info(
            "Giáo viên chưa đăng bài giảng."
        )

        return

    for lesson in lessons[:8]:

        st.markdown(
            f"""
            <div class="card">

                <span class="badge">
                    {lesson["level"]}
                    •
                    {lesson["category"]}
                </span>

                <div class="student-name">
                    {lesson["title"]}
                </div>

                <p>
                    {lesson["description"] or ""}
                </p>

            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Mở bài giảng",
            key=f"dashboard_lesson_{lesson['id']}"
        ):

            st.session_state.open_lesson = (
                lesson["id"]
            )

            st.rerun()


# ============================================================
# RECORD LESSON VIEW
# ============================================================

def record_lesson_view(
    lesson_id,
    student_id,
    lesson_title
):

    existing = fetch("""
        SELECT *
        FROM lesson_views
        WHERE lesson_id=?
        AND student_id=?
    """, (
        lesson_id,
        student_id
    ))

    if existing:

        execute("""
            UPDATE lesson_views

            SET last_viewed=?,
                view_count=view_count+1

            WHERE lesson_id=?
            AND student_id=?
        """, (
            now(),
            lesson_id,
            student_id
        ))

    else:

        execute("""
            INSERT INTO lesson_views
            (
                lesson_id,
                student_id,
                first_viewed,
                last_viewed,
                view_count
            )
            VALUES (?, ?, ?, ?, 1)
        """, (
            lesson_id,
            student_id,
            now(),
            now()
        ))

    log_activity(
        student_id,
        "Đã xem bài giảng",
        lesson_title
    )


# ============================================================
# STUDENT LESSONS
# ============================================================

def student_lessons():

    user = st.session_state.user

    if st.session_state.get(
        "open_lesson"
    ):

        open_student_lesson(
            st.session_state.open_lesson
        )

        return

    st.markdown(
        "## Bài giảng"
    )

    lessons = fetch("""
        SELECT
            l.*,

            CASE
                WHEN v.id IS NULL
                THEN 0
                ELSE 1
            END AS viewed

        FROM lessons l

        LEFT JOIN lesson_views v

        ON v.lesson_id=l.id

        AND v.student_id=?

        WHERE l.class_id=?

        ORDER BY l.created_at DESC
    """, (
        user["id"],
        user["class_id"]
    ))

    if not lessons:

        st.info(
            "Giáo viên chưa đăng bài giảng."
        )

        return

    for lesson in lessons:

        status = (
            "Đã xem"
            if lesson["viewed"]
            else "Chưa xem"
        )

        st.markdown(
            f"""
            <div class="card">

                <span class="badge">
                    {lesson["level"]}
                    •
                    {lesson["category"]}
                    •
                    {status}
                </span>

                <div class="student-name">
                    {lesson["title"]}
                </div>

                <p>
                    {lesson["description"] or ""}
                </p>

            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Mở bài giảng",
            key=f"lesson_{lesson['id']}"
        ):

            record_lesson_view(
                lesson["id"],
                user["id"],
                lesson["title"]
            )

            st.session_state.open_lesson = (
                lesson["id"]
            )

            st.rerun()


# ============================================================
# OPEN STUDENT LESSON
# ============================================================

def open_student_lesson(
    lesson_id
):

    user = st.session_state.user

    rows = fetch(
        """
        SELECT *
        FROM lessons
        WHERE id=?
        AND class_id=?
        """,
        (
            lesson_id,
            user["class_id"]
        )
    )

    if not rows:

        st.session_state.open_lesson = None

        st.error(
            "Không tìm thấy bài giảng."
        )

        return

    lesson = rows[0]

    record_lesson_view(
        lesson["id"],
        user["id"],
        lesson["title"]
    )

    st.markdown(
        f"""
        <div class="hero">

            <span class="badge">
                {lesson["level"]}
                •
                {lesson["category"]}
            </span>

            <h1>
                {lesson["title"]}
            </h1>

            <p>
                {lesson["description"] or ""}
            </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    if lesson["video_file"]:

        video_path = Path(
            lesson["video_file"]
        )

        if video_path.exists():

            st.markdown(
                "### Video bài giảng"
            )

            st.video(
                str(video_path)
            )

            st.caption(
                "Video: "
                +
                (
                    lesson["video_name"]
                    or video_path.name
                )
            )

        else:

            st.warning(
                "Video của bài giảng "
                "hiện không khả dụng."
            )

    st.markdown(
        lesson["content"] or ""
    )

    if lesson["resource_url"]:

        st.link_button(
            "Mở tài liệu học tập",
            lesson["resource_url"]
        )

    if st.button(
        "← Quay lại danh sách bài giảng"
    ):

        st.session_state.open_lesson = None

        st.rerun()


# ============================================================
# STUDENT EXERCISES
# ============================================================

def student_exercises():

    user = st.session_state.user

    st.markdown(
        "## Bài tập"
    )

    exercises = fetch("""
        SELECT
            e.*,

            l.title AS lesson_title,

            s.answer,
            s.score,
            s.feedback,
            s.submitted_at

        FROM exercises e

        LEFT JOIN lessons l
        ON l.id=e.lesson_id

        LEFT JOIN submissions s

        ON s.exercise_id=e.id

        AND s.student_id=?

        WHERE e.class_id=?

        ORDER BY e.created_at DESC
    """, (
        user["id"],
        user["class_id"]
    ))

    if not exercises:

        st.info(
            "Giáo viên chưa đăng bài tập."
        )

        return

    for exercise in exercises:

        status = (
            f"Đã nộp • "
            f"{exercise['score']}/"
            f"{exercise['max_score']}"
            if exercise["submitted_at"]
            else
            "Chưa nộp"
        )

        with st.expander(
            f"{exercise['title']} — {status}"
        ):

            if exercise["lesson_title"]:

                st.caption(
                    "Bài giảng: "
                    +
                    exercise["lesson_title"]
                )

            st.write(
                exercise["instructions"]
                or ""
            )

            st.markdown(
                "### Yêu cầu bài tập"
            )

            st.markdown(
                exercise["questions"]
            )

            with st.form(
                f"submit_{exercise['id']}"
            ):

                answer = st.text_area(
                    "Bài làm của bạn",
                    value=(
                        exercise["answer"]
                        or ""
                    ),
                    height=300
                )

                submit = st.form_submit_button(
                    "Nộp bài",
                    use_container_width=True
                )

            if submit:

                existing = fetch("""
                    SELECT id
                    FROM submissions

                    WHERE exercise_id=?
                    AND student_id=?
                """, (
                    exercise["id"],
                    user["id"]
                ))

                if existing:

                    execute("""
                        UPDATE submissions

                        SET answer=?,
                            submitted_at=?

                        WHERE id=?
                    """, (
                        answer,
                        now(),
                        existing[0]["id"]
                    ))

                else:

                    execute("""
                        INSERT INTO submissions
                        (
                            exercise_id,
                            student_id,
                            answer,
                            score,
                            submitted_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        exercise["id"],
                        user["id"],
                        answer,
                        0,
                        now()
                    ))

                log_activity(
                    user["id"],
                    "Đã nộp bài tập",
                    exercise["title"]
                )

                st.success(
                    "Đã nộp bài thành công."
                )

                st.rerun()

            if exercise["feedback"]:

                st.success(
                    "Nhận xét của giáo viên: "
                    +
                    exercise["feedback"]
                )


# ============================================================
# STUDENT PROGRESS PAGE
# ============================================================

def student_progress_page():

    user = st.session_state.user

    p = student_progress(
        user["id"]
    )

    st.markdown(
        f"""
        <div class="hero">

            <h1>
                Tiến độ học tập
            </h1>

            <p>
                {user["full_name"]}
            </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.progress(
        p["participation"] / 100,
        text=(
            f"Mức độ tham gia: "
            f"{p['participation']}%"
        )
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Mức độ tham gia",
        f"{p['participation']}%"
    )

    b.metric(
        "Bài giảng",
        f"{p['viewed_lessons']}/"
        f"{p['total_lessons']}"
    )

    c.metric(
        "Bài tập",
        f"{p['completed_exercises']}/"
        f"{p['total_exercises']}"
    )

    d.metric(
        "Điểm trung bình",
        f"{p['average']}%"
    )

    st.markdown(
        "### Lịch sử học bài"
    )

    views = fetch("""
        SELECT
            l.title AS "Bài giảng",
            l.level AS "Trình độ",
            l.category AS "Chủ đề",
            v.first_viewed AS "Lần xem đầu tiên",
            v.last_viewed AS "Lần xem gần nhất",
            v.view_count AS "Số lần xem"

        FROM lesson_views v

        JOIN lessons l
        ON l.id=v.lesson_id

        WHERE v.student_id=?

        ORDER BY v.last_viewed DESC
    """, (
        user["id"],
    ))

    if views:

        st.dataframe(
            pd.DataFrame(
                [dict(v) for v in views]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Bạn chưa xem bài giảng nào."
        )

    st.markdown(
        "### Kết quả bài tập"
    )

    results = fetch("""
        SELECT
            e.title AS "Bài tập",
            s.score AS "Điểm",
            e.max_score AS "Điểm tối đa",
            s.feedback AS "Nhận xét giáo viên",
            s.submitted_at AS "Thời gian nộp"

        FROM submissions s

        JOIN exercises e
        ON e.id=s.exercise_id

        WHERE s.student_id=?

        ORDER BY s.submitted_at DESC
    """, (
        user["id"],
    ))

    if results:

        st.dataframe(
            pd.DataFrame(
                [dict(r) for r in results]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Bạn chưa nộp bài tập nào."
        )


# ============================================================
# APP
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


if "open_lesson" not in st.session_state:

    st.session_state.open_lesson = None


# ============================================================
# NOT LOGGED IN
# ============================================================

if not st.session_state.user:

    login_page()


# ============================================================
# LOGGED IN
# ============================================================

else:

    user = st.session_state.user

    # ========================================================
    # TEACHER
    # ========================================================

    if user["role"] == "teacher":

        page = teacher_sidebar()

        if page == "Tổng quan":

            teacher_dashboard()

        elif page == "Lớp học & mã học sinh":

            teacher_class_management()

        elif page == "Bài giảng":

            teacher_lessons()

        elif page == "Tạo bài giảng":

            create_lesson()

        elif page == "Bài tập & chấm điểm":

            teacher_exercises()

        elif page == "Tạo bài tập":

            create_exercise()

        elif page == "Học sinh":

            teacher_students()

        elif page == "Lượt xem bài giảng":

            teacher_lesson_views()

        elif page == "Hoạt động học tập":

            teacher_activity()

    # ========================================================
    # STUDENT
    # ========================================================

    else:

        page = student_sidebar()

        if page == "Trang chủ":

            student_dashboard()

        elif page == "Bài giảng":

            student_lessons()

        elif page == "Bài tập":

            student_exercises()

        elif page == "Tiến độ học tập":

            student_progress_page()
