import streamlit as st
import sqlite3
import hashlib
import hmac
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
import pandas as pd


# ============================================================
# ENGLISHHUB LMS
# Teacher / Student
# SQLite + Class Code + Video Upload
# ============================================================

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "englishhub.db"
VIDEO_DIR = BASE_DIR / "videos"

VIDEO_DIR.mkdir(exist_ok=True)

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
    background: #f7f8fc;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.hero {
    padding: 30px;
    border-radius: 20px;
    background: linear-gradient(
        135deg,
        #eef2ff,
        #f8f9ff
    );
    margin-bottom: 25px;
}

.hero h1 {
    margin-bottom: 8px;
}

.card {
    padding: 20px;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    background: white;
    margin-bottom: 15px;
}

.badge {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 20px;
    background: #eef2ff;
    color: #4338ca;
    font-size: 13px;
    margin-bottom: 8px;
}

.student-name {
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 5px;
}

.small {
    color: #6b7280;
    font-size: 14px;
}

.login-title {
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 8px;
}

.login-subtitle {
    color: #6b7280;
    font-size: 18px;
    margin-bottom: 25px;
}

.class-code {
    padding: 15px;
    border-radius: 12px;
    background: #f3f4f6;
    font-size: 24px;
    font-weight: 800;
    text-align: center;
    letter-spacing: 3px;
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


def column_exists(table, column):
    con = connect()

    rows = con.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    con.close()

    return any(row["name"] == column for row in rows)


def init_db():

    con = connect()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        class_name TEXT NOT NULL,
        class_code TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS class_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        joined_at TEXT NOT NULL,
        UNIQUE(class_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        level TEXT,
        category TEXT,
        content TEXT,
        resource_url TEXT,
        video_path TEXT,
        video_name TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        lesson_id INTEGER,
        instructions TEXT,
        questions TEXT,
        max_score INTEGER DEFAULT 100,
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
        class_id INTEGER,
        action TEXT NOT NULL,
        object_name TEXT,
        created_at TEXT NOT NULL
    );
    """)

    con.commit()

    # ========================================================
    # MIGRATION CHO DATABASE CŨ
    # ========================================================

    # lessons cũ chưa có class_id
    if not column_exists("lessons", "class_id"):
        con.execute(
            "ALTER TABLE lessons ADD COLUMN class_id INTEGER"
        )

    if not column_exists("lessons", "video_path"):
        con.execute(
            "ALTER TABLE lessons ADD COLUMN video_path TEXT"
        )

    if not column_exists("lessons", "video_name"):
        con.execute(
            "ALTER TABLE lessons ADD COLUMN video_name TEXT"
        )

    # exercises cũ chưa có class_id
    if not column_exists("exercises", "class_id"):
        con.execute(
            "ALTER TABLE exercises ADD COLUMN class_id INTEGER"
        )

    # activity cũ chưa có class_id
    if not column_exists("activity", "class_id"):
        con.execute(
            "ALTER TABLE activity ADD COLUMN class_id INTEGER"
        )

    con.commit()
    con.close()


init_db()


# ============================================================
# HELPER
# ============================================================

def now():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


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


def generate_class_code():
    while True:

        code = uuid.uuid4().hex[:8].upper()

        exists = fetch(
            "SELECT id FROM classes WHERE class_code=?",
            (code,)
        )

        if not exists:
            return code


def safe_filename(filename):

    filename = Path(filename).name

    filename = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        filename
    )

    return filename


# ============================================================
# ACTIVITY
# ============================================================

def log_activity(
    student_id,
    action,
    object_name="",
    class_id=None
):

    execute("""
        INSERT INTO activity
        (
            student_id,
            class_id,
            action,
            object_name,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        student_id,
        class_id,
        action,
        object_name,
        now()
    ))


# ============================================================
# REGISTER / LOGIN
# ============================================================

def register(
    full_name,
    username,
    password,
    role,
    code="",
    class_code=""
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
            code.strip(),
            teacher_code()
        ):
            return False, (
                "Mã truy cập giáo viên không chính xác."
            )

    # --------------------------------------------------------
    # STUDENT
    # --------------------------------------------------------

    class_row = None

    if role == "student":

        class_code = class_code.strip().upper()

        if not class_code:
            return False, (
                "Học sinh bắt buộc phải nhập mã lớp."
            )

        class_rows = fetch("""
            SELECT *
            FROM classes
            WHERE class_code=?
        """, (class_code,))

        if not class_rows:
            return False, (
                "Mã lớp không tồn tại. "
                "Hãy kiểm tra lại mã do giáo viên cung cấp."
            )

        class_row = class_rows[0]

    # --------------------------------------------------------
    # CREATE USER
    # --------------------------------------------------------

    try:

        user_id = execute("""
            INSERT INTO users
            (
                full_name,
                username,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            full_name,
            username,
            password_hash(password),
            role,
            now()
        ))

    except sqlite3.IntegrityError:

        return False, (
            "Tên đăng nhập này đã tồn tại."
        )

    # --------------------------------------------------------
    # ADD STUDENT TO CLASS
    # --------------------------------------------------------

    if role == "student":

        execute("""
            INSERT INTO class_members
            (
                class_id,
                student_id,
                joined_at
            )
            VALUES (?, ?, ?)
        """, (
            class_row["id"],
            user_id,
            now()
        ))

    return True, "Tạo tài khoản thành công."


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

    if rows and check_password(
        password,
        rows[0]["password_hash"]
    ):
        return dict(rows[0])

    return None


# ============================================================
# CLASS FUNCTIONS
# ============================================================

def teacher_classes(teacher_id):

    return fetch("""
        SELECT *
        FROM classes
        WHERE teacher_id=?
        ORDER BY created_at DESC
    """, (teacher_id,))


def student_classes(student_id):

    return fetch("""
        SELECT
            c.*,
            cm.joined_at
        FROM class_members cm
        JOIN classes c
            ON c.id=cm.class_id
        WHERE cm.student_id=?
        ORDER BY c.created_at DESC
    """, (student_id,))


def student_class_ids(student_id):

    rows = fetch("""
        SELECT class_id
        FROM class_members
        WHERE student_id=?
    """, (student_id,))

    return [row["class_id"] for row in rows]


def teacher_class_ids(teacher_id):

    rows = fetch("""
        SELECT id
        FROM classes
        WHERE teacher_id=?
    """, (teacher_id,))

    return [row["id"] for row in rows]


# ============================================================
# PROGRESS
# ============================================================

def student_progress(student_id):

    class_ids = student_class_ids(student_id)

    if not class_ids:
        return {
            "total_lessons": 0,
            "viewed_lessons": 0,
            "total_exercises": 0,
            "completed_exercises": 0,
            "average": 0,
            "participation": 0
        }

    placeholders = ",".join(
        ["?"] * len(class_ids)
    )

    total_lessons = fetch(
        f"""
        SELECT COUNT(*) n
        FROM lessons
        WHERE class_id IN ({placeholders})
        """,
        class_ids
    )[0]["n"]

    viewed_lessons = fetch(
        f"""
        SELECT COUNT(*) n
        FROM lesson_views v
        JOIN lessons l
            ON l.id=v.lesson_id
        WHERE v.student_id=?
        AND l.class_id IN ({placeholders})
        """,
        [student_id] + class_ids
    )[0]["n"]

    total_exercises = fetch(
        f"""
        SELECT COUNT(*) n
        FROM exercises
        WHERE class_id IN ({placeholders})
        """,
        class_ids
    )[0]["n"]

    completed_exercises = fetch(
        f"""
        SELECT COUNT(*) n
        FROM submissions s
        JOIN exercises e
            ON e.id=s.exercise_id
        WHERE s.student_id=?
        AND e.class_id IN ({placeholders})
        """,
        [student_id] + class_ids
    )[0]["n"]

    avg = fetch(
        f"""
        SELECT AVG(s.score * 100.0 / NULLIF(e.max_score, 0)) a
        FROM submissions s
        JOIN exercises e
            ON e.id=s.exercise_id
        WHERE s.student_id=?
        AND e.class_id IN ({placeholders})
        """,
        [student_id] + class_ids
    )[0]["a"]

    average = float(avg or 0)

    lesson_rate = (
        viewed_lessons / total_lessons * 100
        if total_lessons
        else 0
    )

    exercise_rate = (
        completed_exercises / total_exercises * 100
        if total_exercises
        else 0
    )

    participation = round(
        lesson_rate * 0.4
        +
        exercise_rate * 0.6 * (
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

    st.markdown(
        """
        <div class="hero">
            <div class="login-title">
                EnglishHub LMS
            </div>

            <div class="login-subtitle">
                Nền tảng học tiếng Anh dành cho lớp học
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    left, right = st.columns(2)

    # ========================================================
    # LOGIN
    # ========================================================

    with left:

        st.markdown("### Đăng nhập")

        role = st.radio(
            "Bạn là:",
            ["Học sinh", "Giáo viên"],
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

                if role_db == "student":
                    st.session_state.selected_class = None

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
            "Học sinh bắt buộc phải có mã lớp "
            "do giáo viên cung cấp."
        )

        with st.form("register_form"):

            full_name = st.text_input(
                "Họ và tên"
            )

            username = st.text_input(
                "Tên đăng nhập",
                key="register_username"
            )

            password = st.text_input(
                "Mật khẩu",
                type="password",
                key="register_password"
            )

            role = st.selectbox(
                "Loại tài khoản",
                ["Học sinh", "Giáo viên"]
            )

            role_db = (
                "student"
                if role == "Học sinh"
                else "teacher"
            )

            teacher_access_code = ""
            class_code = ""

            if role_db == "teacher":

                teacher_access_code = st.text_input(
                    "Mã truy cập giáo viên",
                    type="password"
                )

            else:

                class_code = st.text_input(
                    "Mã lớp",
                    placeholder="Ví dụ: A7F29C31"
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
                teacher_access_code,
                class_code
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
                "Lớp học",
                "Bài giảng",
                "Tạo bài giảng",
                "Bài tập & chấm điểm",
                "Tạo bài tập",
                "Học sinh",
                "Lượt xem bài giảng",
                "Hoạt động học tập"
            ]
        )

        st.divider()

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

    st.markdown(
        """
        <div class="hero">
            <h1>Tổng quan lớp học</h1>
            <p>
                Quản lý lớp học, bài giảng,
                video, bài tập và tiến độ học sinh.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    classes = teacher_classes(teacher_id)

    class_ids = [
        c["id"]
        for c in classes
    ]

    students = 0
    lessons = 0
    exercises = 0
    submissions = 0

    if class_ids:

        placeholders = ",".join(
            ["?"] * len(class_ids)
        )

        students = fetch(
            f"""
            SELECT COUNT(DISTINCT student_id) n
            FROM class_members
            WHERE class_id IN ({placeholders})
            """,
            class_ids
        )[0]["n"]

        lessons = fetch(
            f"""
            SELECT COUNT(*) n
            FROM lessons
            WHERE class_id IN ({placeholders})
            """,
            class_ids
        )[0]["n"]

        exercises = fetch(
            f"""
            SELECT COUNT(*) n
            FROM exercises
            WHERE class_id IN ({placeholders})
            """,
            class_ids
        )[0]["n"]

        submissions = fetch(
            f"""
            SELECT COUNT(*) n
            FROM submissions s
            JOIN exercises e
                ON e.id=s.exercise_id
            WHERE e.class_id IN ({placeholders})
            """,
            class_ids
        )[0]["n"]

    a, b, c, d = st.columns(4)

    a.metric(
        "Lớp học",
        len(classes)
    )

    b.metric(
        "Học sinh",
        students
    )

    c.metric(
        "Bài giảng",
        lessons
    )

    d.metric(
        "Bài đã nộp",
        submissions
    )

    st.markdown("### Các lớp của bạn")

    if not classes:

        st.info(
            "Bạn chưa tạo lớp nào."
        )

    else:

        for classroom in classes:

            member_count = fetch(
                """
                SELECT COUNT(*) n
                FROM class_members
                WHERE class_id=?
                """,
                (classroom["id"],)
            )[0]["n"]

            st.markdown(
                f"""
                <div class="card">

                    <div class="student-name">
                        {classroom["class_name"]}
                    </div>

                    <p>
                        {classroom["description"] or ""}
                    </p>

                    <div class="small">
                        Học sinh: {member_count}
                    </div>

                    <div class="class-code">
                        {classroom["class_code"]}
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


# ============================================================
# TEACHER CLASS MANAGEMENT
# ============================================================

def teacher_class_page():

    teacher_id = st.session_state.user["id"]

    st.markdown("## Quản lý lớp học")

    st.markdown(
        "Tạo nhiều lớp và gửi mã lớp cho học sinh."
    )

    with st.form("create_class"):

        class_name = st.text_input(
            "Tên lớp",
            placeholder="Ví dụ: English B1 - K26"
        )

        description = st.text_area(
            "Mô tả lớp",
            placeholder="Ví dụ: Lớp luyện thi B1"
        )

        submit = st.form_submit_button(
            "Tạo lớp",
            use_container_width=True
        )

    if submit:

        if not class_name.strip():

            st.error(
                "Tên lớp không được để trống."
            )

        else:

            code = generate_class_code()

            execute("""
                INSERT INTO classes
                (
                    teacher_id,
                    class_name,
                    class_code,
                    description,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                teacher_id,
                class_name.strip(),
                code,
                description,
                now()
            ))

            st.success(
                "Đã tạo lớp thành công."
            )

            st.rerun()

    st.divider()

    classes = teacher_classes(
        teacher_id
    )

    if not classes:

        st.info(
            "Bạn chưa có lớp học nào."
        )

        return

    for classroom in classes:

        st.markdown(
            f"""
            <div class="card">

                <div class="student-name">
                    {classroom["class_name"]}
                </div>

                <p>
                    {classroom["description"] or ""}
                </p>

                <div class="small">
                    Mã lớp:
                </div>

                <div class="class-code">
                    {classroom["class_code"]}
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        members = fetch("""
            SELECT
                u.full_name,
                u.username,
                cm.joined_at
            FROM class_members cm
            JOIN users u
                ON u.id=cm.student_id
            WHERE cm.class_id=?
            ORDER BY u.full_name
        """, (classroom["id"],))

        if members:

            st.dataframe(
                pd.DataFrame(
                    [dict(m) for m in members]
                ).rename(
                    columns={
                        "full_name": "Họ và tên",
                        "username": "Tên đăng nhập",
                        "joined_at": "Ngày tham gia"
                    }
                ),
                use_container_width=True,
                hide_index=True
            )

        else:

            st.caption(
                "Chưa có học sinh tham gia lớp này."
            )


# ============================================================
# CREATE LESSON
# ============================================================

def create_lesson():

    teacher_id = st.session_state.user["id"]

    st.markdown("## Tạo bài giảng mới")

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
        f"{c['class_name']} — {c['class_code']}":
        c["id"]
        for c in classes
    }

    with st.form("create_lesson"):

        selected_class = st.selectbox(
            "Đăng bài giảng cho lớp",
            list(class_options.keys())
        )

        title = st.text_input(
            "Tên bài giảng"
        )

        description = st.text_area(
            "Mô tả ngắn"
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
            height=350,
            placeholder=(
                "# Present Perfect\n\n"
                "## Công thức\n\n"
                "Subject + have/has + V3\n\n"
                "## Ví dụ\n\n"
                "I have studied English for three years."
            )
        )

        resource = st.text_input(
            "Đường dẫn tài liệu bên ngoài (nếu có)"
        )

        st.markdown("### Video bài giảng")

        video = st.file_uploader(
            "Upload video từ máy tính",
            type=[
                "mp4",
                "mov",
                "webm",
                "m4v"
            ],
            help=(
                "Chọn video để học sinh "
                "xem trực tiếp trên website."
            )
        )

        submit = st.form_submit_button(
            "Đăng bài giảng",
            use_container_width=True
        )

    if submit:

        if not title.strip():

            st.error(
                "Tên bài giảng không được để trống."
            )

            return

        if not content.strip() and video is None:

            st.error(
                "Bài giảng cần có nội dung "
                "hoặc video."
            )

            return

        video_path = None
        video_name = None

        if video is not None:

            original_name = safe_filename(
                video.name
            )

            unique_name = (
                f"{uuid.uuid4().hex[:12]}_"
                f"{original_name}"
            )

            path = VIDEO_DIR / unique_name

            with open(path, "wb") as file:

                file.write(
                    video.getbuffer()
                )

            video_path = str(path)
            video_name = original_name

        execute("""
            INSERT INTO lessons
            (
                class_id,
                title,
                description,
                level,
                category,
                content,
                resource_url,
                video_path,
                video_name,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            class_options[selected_class],
            title.strip(),
            description,
            level,
            category,
            content,
            resource,
            video_path,
            video_name,
            now()
        ))

        st.success(
            "Đã đăng bài giảng thành công."
        )

        st.rerun()


# ============================================================
# TEACHER LESSONS
# ============================================================

def teacher_lessons():

    teacher_id = st.session_state.user["id"]

    st.markdown("## Danh sách bài giảng")

    classes = teacher_classes(
        teacher_id
    )

    if not classes:

        st.info(
            "Bạn chưa tạo lớp nào."
        )

        return

    class_ids = [
        c["id"]
        for c in classes
    ]

    placeholders = ",".join(
        ["?"] * len(class_ids)
    )

    lessons = fetch(
        f"""
        SELECT
            l.*,
            c.class_name,
            c.class_code,
            COUNT(v.id) AS so_luot_xem
        FROM lessons l
        JOIN classes c
            ON c.id=l.class_id
        LEFT JOIN lesson_views v
            ON v.lesson_id=l.id
        WHERE l.class_id IN ({placeholders})
        GROUP BY l.id
        ORDER BY l.created_at DESC
        """,
        class_ids
    )

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
                    {lesson["class_name"]}
                    •
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
                    Lượt xem:
                    {lesson["so_luot_xem"]}
                </span>

            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander(
            "Xem bài giảng"
        ):

            if lesson["video_path"]:

                video_file = Path(
                    lesson["video_path"]
                )

                if video_file.exists():

                    st.video(
                        str(video_file)
                    )

                    st.caption(
                        f"Video: "
                        f"{lesson['video_name']}"
                    )

            if lesson["content"]:

                st.markdown(
                    lesson["content"]
                )

            if lesson["resource_url"]:

                st.link_button(
                    "Mở tài liệu bên ngoài",
                    lesson["resource_url"]
                )


# ============================================================
# CREATE EXERCISE
# ============================================================

def create_exercise():

    teacher_id = st.session_state.user["id"]

    st.markdown("## Tạo bài tập mới")

    classes = teacher_classes(
        teacher_id
    )

    if not classes:

        st.warning(
            "Bạn cần tạo lớp trước."
        )

        return

    class_options = {
        f"{c['class_name']} — {c['class_code']}":
        c["id"]
        for c in classes
    }

    selected_class = st.selectbox(
        "Lớp",
        list(class_options.keys())
    )

    class_id = class_options[
        selected_class
    ]

    lessons = fetch("""
        SELECT id, title
        FROM lessons
        WHERE class_id=?
        ORDER BY title
    """, (class_id,))

    lesson_dict = {
        "Không liên kết bài giảng": None
    }

    for lesson in lessons:

        lesson_dict[
            lesson["title"]
        ] = lesson["id"]

    with st.form("create_exercise"):

        title = st.text_input(
            "Tên bài tập"
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

        if not title.strip() or not questions.strip():

            st.error(
                "Tên bài tập và nội dung câu hỏi "
                "là bắt buộc."
            )

            return

        execute("""
            INSERT INTO exercises
            (
                class_id,
                title,
                lesson_id,
                instructions,
                questions,
                max_score,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            class_id,
            title.strip(),
            lesson_dict[linked],
            instructions,
            questions,
            max_score,
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

    class_ids = teacher_class_ids(
        teacher_id
    )

    if not class_ids:

        st.info(
            "Bạn chưa tạo lớp nào."
        )

        return

    placeholders = ",".join(
        ["?"] * len(class_ids)
    )

    submissions = fetch(
        f"""
        SELECT
            s.id,
            s.answer,
            s.score,
            s.feedback,
            s.submitted_at,
            u.full_name AS student_name,
            e.title AS exercise_title,
            e.max_score,
            c.class_name
        FROM submissions s
        JOIN users u
            ON u.id=s.student_id
        JOIN exercises e
            ON e.id=s.exercise_id
        JOIN classes c
            ON c.id=e.class_id
        WHERE e.class_id IN ({placeholders})
        ORDER BY s.submitted_at DESC
        """,
        class_ids
    )

    if not submissions:

        st.info(
            "Chưa có học sinh nộp bài."
        )

        return

    for submission in submissions:

        st.markdown(
            f"""
            ### {submission["student_name"]}
            — {submission["exercise_title"]}

            **Lớp:** {submission["class_name"]}
            """
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
                min_value=0.0,
                max_value=float(
                    submission["max_score"]
                ),
                value=float(
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

    classes = teacher_classes(
        teacher_id
    )

    if not classes:

        st.info(
            "Bạn chưa tạo lớp."
        )

        return

    selected = st.selectbox(
        "Chọn lớp",
        classes,
        format_func=lambda x:
            f"{x['class_name']} — {x['class_code']}"
    )

    students = fetch("""
        SELECT
            u.id,
            u.full_name,
            u.username,
            cm.joined_at
        FROM class_members cm
        JOIN users u
            ON u.id=cm.student_id
        WHERE cm.class_id=?
        ORDER BY u.full_name
    """, (selected["id"],))

    if not students:

        st.info(
            "Chưa có học sinh trong lớp."
        )

        return

    data = []

    for student in students:

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
                f"{p['participation']}%",

            "Ngày tham gia":
                student["joined_at"]
        })

    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# LESSON VIEWS
# ============================================================

def teacher_lesson_views():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Lượt xem bài giảng"
    )

    class_ids = teacher_class_ids(
        teacher_id
    )

    if not class_ids:

        st.info(
            "Bạn chưa tạo lớp."
        )

        return

    placeholders = ",".join(
        ["?"] * len(class_ids)
    )

    lessons = fetch(
        f"""
        SELECT
            l.id,
            l.title,
            c.class_name
        FROM lessons l
        JOIN classes c
            ON c.id=l.class_id
        WHERE l.class_id IN ({placeholders})
        ORDER BY l.created_at DESC
        """,
        class_ids
    )

    if not lessons:

        st.info(
            "Chưa có bài giảng."
        )

        return

    selected = st.selectbox(
        "Chọn bài giảng",
        lessons,
        format_func=lambda x:
            f"{x['class_name']} — {x['title']}"
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
        JOIN class_members cm
            ON cm.student_id=v.student_id
        WHERE v.lesson_id=?
        AND cm.class_id=(
            SELECT class_id
            FROM lessons
            WHERE id=?
        )
        ORDER BY v.last_viewed DESC
    """, (
        selected["id"],
        selected["id"]
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
            "Chưa có học sinh nào xem bài này."
        )


# ============================================================
# TEACHER ACTIVITY
# ============================================================

def teacher_activity():

    teacher_id = st.session_state.user["id"]

    st.markdown(
        "## Hoạt động học tập"
    )

    class_ids = teacher_class_ids(
        teacher_id
    )

    if not class_ids:

        st.info(
            "Bạn chưa tạo lớp."
        )

        return

    placeholders = ",".join(
        ["?"] * len(class_ids)
    )

    rows = fetch(
        f"""
        SELECT
            a.created_at AS "Thời gian",
            u.full_name AS "Học sinh",
            c.class_name AS "Lớp",
            a.action AS "Hoạt động",
            a.object_name AS "Nội dung"
        FROM activity a
        LEFT JOIN users u
            ON u.id=a.student_id
        LEFT JOIN classes c
            ON c.id=a.class_id
        WHERE a.class_id IN ({placeholders})
        ORDER BY a.created_at DESC
        LIMIT 300
        """,
        class_ids
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
            "Chưa có hoạt động học tập."
        )


# ============================================================
# STUDENT SIDEBAR
# ============================================================

def student_sidebar():

    with st.sidebar:

        st.markdown("## EnglishHub LMS")

        st.caption(
            f"Học sinh: "
            f"{st.session_state.user['full_name']}"
        )

        classes = student_classes(
            st.session_state.user["id"]
        )

        if classes:

            st.markdown("### Lớp của bạn")

            selected = st.selectbox(
                "Chọn lớp",
                classes,
                format_func=lambda x:
                    x["class_name"]
            )

            st.session_state.selected_class = (
                selected["id"]
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

        st.divider()

        if st.button(
            "Đăng xuất",
            use_container_width=True
        ):

            st.session_state.user = None
            st.rerun()

    return page


# ============================================================
# RECORD LESSON VIEW
# ============================================================

def record_lesson_view(
    lesson_id,
    student_id,
    lesson_title,
    class_id
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
        lesson_title,
        class_id
    )


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
                Xin chào, {user["full_name"]}!
            </h1>

            <p>
                Chào mừng bạn quay lại EnglishHub.
                Hãy tiếp tục hành trình học tiếng Anh.
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

    class_id = st.session_state.get(
        "selected_class"
    )

    if not class_id:

        st.info(
            "Bạn chưa chọn lớp."
        )

        return

    lessons = fetch("""
        SELECT
            l.*,
            CASE
                WHEN v.id IS NULL THEN 0
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
        class_id
    ))

    if not lessons:

        st.info(
            "Lớp này chưa có bài giảng."
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
            key=f"dashboard_{lesson['id']}"
        ):

            record_lesson_view(
                lesson["id"],
                user["id"],
                lesson["title"],
                lesson["class_id"]
            )

            st.session_state.open_lesson = (
                lesson["id"]
            )

            st.rerun()


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

    class_id = st.session_state.get(
        "selected_class"
    )

    if not class_id:

        st.info(
            "Bạn chưa chọn lớp."
        )

        return

    lessons = fetch("""
        SELECT
            l.*,
            CASE
                WHEN v.id IS NULL THEN 0
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
        class_id
    ))

    if not lessons:

        st.info(
            "Giáo viên chưa đăng bài giảng nào."
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
            key=f"student_lesson_{lesson['id']}"
        ):

            record_lesson_view(
                lesson["id"],
                user["id"],
                lesson["title"],
                lesson["class_id"]
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
        """,
        (lesson_id,)
    )

    if not rows:

        st.session_state.open_lesson = None

        return

    lesson = rows[0]

    # --------------------------------------------------------
    # CHECK STUDENT BELONGS TO CLASS
    # --------------------------------------------------------

    membership = fetch("""
        SELECT id
        FROM class_members
        WHERE class_id=?
        AND student_id=?
    """, (
        lesson["class_id"],
        user["id"]
    ))

    if not membership:

        st.error(
            "Bạn không có quyền xem bài giảng này."
        )

        st.session_state.open_lesson = None

        return

    record_lesson_view(
        lesson["id"],
        user["id"],
        lesson["title"],
        lesson["class_id"]
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

    # ========================================================
    # VIDEO
    # ========================================================

    if lesson["video_path"]:

        video_file = Path(
            lesson["video_path"]
        )

        if video_file.exists():

            st.markdown(
                "### Video bài giảng"
            )

            st.video(
                str(video_file)
            )

        else:

            st.warning(
                "Video không còn tồn tại trên máy chủ."
            )

    # ========================================================
    # CONTENT
    # ========================================================

    if lesson["content"]:

        st.markdown(
            "### Nội dung bài học"
        )

        st.markdown(
            lesson["content"]
        )

    # ========================================================
    # RESOURCE
    # ========================================================

    if lesson["resource_url"]:

        st.link_button(
            "Mở tài liệu học tập",
            lesson["resource_url"]
        )

    st.divider()

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

    class_id = st.session_state.get(
        "selected_class"
    )

    if not class_id:

        st.info(
            "Bạn chưa chọn lớp."
        )

        return

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
        class_id
    ))

    if not exercises:

        st.info(
            "Giáo viên chưa đăng bài tập nào."
        )

        return

    for exercise in exercises:

        if exercise["submitted_at"]:

            status = (
                f"Đã nộp • "
                f"{exercise['score']}/"
                f"{exercise['max_score']}"
            )

        else:

            status = "Chưa nộp"

        with st.expander(
            f"{exercise['title']} — {status}"
        ):

            if exercise["lesson_title"]:

                st.caption(
                    f"Bài giảng: "
                    f"{exercise['lesson_title']}"
                )

            if exercise["instructions"]:

                st.write(
                    exercise["instructions"]
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
                    exercise["title"],
                    class_id
                )

                st.success(
                    "Đã nộp bài thành công."
                )

                st.rerun()

            if exercise["feedback"]:

                st.success(
                    "Nhận xét của giáo viên: "
                    f"{exercise['feedback']}"
                )


# ============================================================
# STUDENT PROGRESS
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

    class_ids = student_class_ids(
        user["id"]
    )

    if class_ids:

        placeholders = ",".join(
            ["?"] * len(class_ids)
        )

        views = fetch(
            f"""
            SELECT
                c.class_name AS "Lớp",
                l.title AS "Bài giảng",
                l.level AS "Trình độ",
                l.category AS "Chủ đề",
                v.first_viewed AS "Lần xem đầu tiên",
                v.last_viewed AS "Lần xem gần nhất",
                v.view_count AS "Số lần xem"
            FROM lesson_views v
            JOIN lessons l
                ON l.id=v.lesson_id
            JOIN classes c
                ON c.id=l.class_id
            WHERE v.student_id=?
            AND l.class_id IN ({placeholders})
            ORDER BY v.last_viewed DESC
            """,
            [user["id"]] + class_ids
        )

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

    if class_ids:

        placeholders = ",".join(
            ["?"] * len(class_ids)
        )

        results = fetch(
            f"""
            SELECT
                c.class_name AS "Lớp",
                e.title AS "Bài tập",
                s.score AS "Điểm",
                e.max_score AS "Điểm tối đa",
                s.feedback AS "Nhận xét giáo viên",
                s.submitted_at AS "Thời gian nộp"
            FROM submissions s
            JOIN exercises e
                ON e.id=s.exercise_id
            JOIN classes c
                ON c.id=e.class_id
            WHERE s.student_id=?
            AND e.class_id IN ({placeholders})
            ORDER BY s.submitted_at DESC
            """,
            [user["id"]] + class_ids
        )

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
# MAIN
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


if "open_lesson" not in st.session_state:

    st.session_state.open_lesson = None


if "selected_class" not in st.session_state:

    st.session_state.selected_class = None


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

        elif page == "Lớp học":

            teacher_class_page()

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
