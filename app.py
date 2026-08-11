import streamlit as st
import sqlite3
import hashlib
import hmac
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

# ============================================================
# ENGLISHHUB LMS
# Phiên bản có:
# - Giáo viên tạo lớp
# - Giáo viên tự tạo mã lớp
# - Học sinh bắt buộc nhập mã lớp khi đăng ký
# - Bài giảng theo từng lớp
# - Bài tập theo từng lớp
# - Upload video trực tiếp
# - Theo dõi tiến độ học sinh
# ============================================================


# ============================================================
# CẤU HÌNH
# ============================================================

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "englishhub.db"

UPLOAD_DIR = BASE_DIR / "uploads"
VIDEO_DIR = UPLOAD_DIR / "videos"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)


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
    background: #f7f9fc;
}

.hero {
    padding: 30px;
    border-radius: 18px;
    background: linear-gradient(
        135deg,
        #eef4ff,
        #f8fbff
    );
    margin-bottom: 25px;
}

.card {
    padding: 20px;
    border-radius: 15px;
    background: white;
    border: 1px solid #e8edf5;
    margin-bottom: 15px;
}

.student-name {
    font-size: 20px;
    font-weight: 700;
    margin-top: 8px;
}

.small {
    color: #6b7280;
    font-size: 14px;
}

.badge {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 20px;
    background: #eef4ff;
    font-size: 13px;
    font-weight: 600;
}

.class-code {
    font-size: 26px;
    font-weight: 800;
    letter-spacing: 2px;
    padding: 15px;
    background: #f3f6fa;
    border-radius: 12px;
    text-align: center;
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
        created_at TEXT NOT NULL
    );


    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        class_name TEXT NOT NULL,
        class_code TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (teacher_id)
            REFERENCES users(id)
    );


    CREATE TABLE IF NOT EXISTS class_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        joined_at TEXT NOT NULL,

        UNIQUE(class_id, student_id),

        FOREIGN KEY (class_id)
            REFERENCES classes(id),

        FOREIGN KEY (student_id)
            REFERENCES users(id)
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

        video_file TEXT,
        video_name TEXT,

        created_at TEXT NOT NULL,

        FOREIGN KEY (class_id)
            REFERENCES classes(id)
    );


    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        class_id INTEGER NOT NULL,
        lesson_id INTEGER,

        title TEXT NOT NULL,
        instructions TEXT,
        questions TEXT,

        max_score INTEGER DEFAULT 100,

        created_at TEXT NOT NULL,

        FOREIGN KEY (class_id)
            REFERENCES classes(id),

        FOREIGN KEY (lesson_id)
            REFERENCES lessons(id)
    );


    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        exercise_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,

        answer TEXT,

        score REAL DEFAULT 0,

        feedback TEXT,

        submitted_at TEXT NOT NULL,

        UNIQUE(exercise_id, student_id),

        FOREIGN KEY (exercise_id)
            REFERENCES exercises(id),

        FOREIGN KEY (student_id)
            REFERENCES users(id)
    );


    CREATE TABLE IF NOT EXISTS lesson_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        lesson_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,

        first_viewed TEXT NOT NULL,
        last_viewed TEXT NOT NULL,

        view_count INTEGER DEFAULT 1,

        UNIQUE(lesson_id, student_id),

        FOREIGN KEY (lesson_id)
            REFERENCES lessons(id),

        FOREIGN KEY (student_id)
            REFERENCES users(id)
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
# MIGRATION DATABASE CŨ
# ============================================================

def migrate_database():

    con = connect()

    # --------------------------------------------------------
    # lessons cũ có thể chưa có class_id
    # --------------------------------------------------------

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

    if "class_id" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN class_id INTEGER"
        )

    # --------------------------------------------------------
    # exercises cũ
    # --------------------------------------------------------

    exercise_columns = [
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(exercises)"
        ).fetchall()
    ]

    if "class_id" not in exercise_columns:
        con.execute(
            "ALTER TABLE exercises ADD COLUMN class_id INTEGER"
        )

    con.commit()
    con.close()


migrate_database()


# ============================================================
# HỆ THỐNG
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


# ============================================================
# ACTIVITY
# ============================================================

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
# KIỂM TRA MÃ LỚP
# ============================================================

def find_class_by_code(class_code):

    class_code = class_code.strip().upper()

    rows = fetch("""
        SELECT *
        FROM classes
        WHERE UPPER(class_code)=?
    """, (
        class_code,
    ))

    if rows:
        return rows[0]

    return None


# ============================================================
# ĐĂNG KÝ
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
    # GIÁO VIÊN
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
    # HỌC SINH
    # --------------------------------------------------------

    class_info = None

    if role == "student":

        if not code.strip():
            return False, (
                "Học sinh bắt buộc phải nhập Mã lớp."
            )

        class_info = find_class_by_code(code)

        if not class_info:
            return False, (
                "Mã lớp không chính xác hoặc lớp không tồn tại."
            )

    # --------------------------------------------------------
    # TẠO USER
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
    # THÊM HỌC SINH VÀO LỚP
    # --------------------------------------------------------

    if role == "student":

        try:

            execute("""
                INSERT INTO class_members
                (
                    class_id,
                    student_id,
                    joined_at
                )
                VALUES (?, ?, ?)
            """, (
                class_info["id"],
                user_id,
                now()
            ))

        except sqlite3.IntegrityError:

            return False, (
                "Không thể thêm học sinh vào lớp."
            )

    return True, (
        "Tạo tài khoản thành công."
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
# LẤY LỚP CỦA GIÁO VIÊN
# ============================================================

def teacher_classes(teacher_id):

    return fetch("""
        SELECT *
        FROM classes
        WHERE teacher_id=?
        ORDER BY created_at DESC
    """, (
        teacher_id,
    ))


# ============================================================
# LỚP CỦA HỌC SINH
# ============================================================

def student_classes(student_id):

    return fetch("""
        SELECT
            c.*,
            u.full_name AS teacher_name
        FROM class_members cm

        JOIN classes c
            ON c.id=cm.class_id

        JOIN users u
            ON u.id=c.teacher_id

        WHERE cm.student_id=?

        ORDER BY c.created_at DESC
    """, (
        student_id,
    ))


# ============================================================
# PROGRESS
# ============================================================

def student_progress(
    student_id,
    class_id=None
):

    if class_id:

        total_lessons = fetch("""
            SELECT COUNT(*) n
            FROM lessons
            WHERE class_id=?
        """, (
            class_id,
        ))[0]["n"]

        viewed_lessons = fetch("""
            SELECT COUNT(*) n
            FROM lesson_views v
            JOIN lessons l
                ON l.id=v.lesson_id
            WHERE v.student_id=?
            AND l.class_id=?
        """, (
            student_id,
            class_id
        ))[0]["n"]

        total_exercises = fetch("""
            SELECT COUNT(*) n
            FROM exercises
            WHERE class_id=?
        """, (
            class_id,
        ))[0]["n"]

        completed_exercises = fetch("""
            SELECT COUNT(*) n
            FROM submissions s
            JOIN exercises e
                ON e.id=s.exercise_id
            WHERE s.student_id=?
            AND e.class_id=?
        """, (
            student_id,
            class_id
        ))[0]["n"]

        avg = fetch("""
            SELECT AVG(s.score) a
            FROM submissions s
            JOIN exercises e
                ON e.id=s.exercise_id
            WHERE s.student_id=?
            AND e.class_id=?
        """, (
            student_id,
            class_id
        ))[0]["a"]

    else:

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
            SELECT AVG(score) a
            FROM submissions
            WHERE student_id=?
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
        exercise_rate *
        0.6 *
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
            Nền tảng học tiếng Anh dành cho lớp học của bạn.
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
                    "Tên đăng nhập, mật khẩu hoặc loại tài khoản không chính xác."
                )


    # ========================================================
    # REGISTER
    # ========================================================

    with right:

        st.markdown("### Tạo tài khoản")

        st.info(
            "Học sinh cần Mã lớp do giáo viên cung cấp. "
            "Giáo viên cần Mã truy cập giáo viên."
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


            if role_db == "student":

                code = st.text_input(
                    "Mã lớp",
                    placeholder="Ví dụ: B1-2026"
                )

                st.caption(
                    "Nhập mã lớp do giáo viên cung cấp."
                )


            else:

                code = st.text_input(
                    "Mã truy cập giáo viên",
                    type="password"
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

                if role_db == "student":

                    st.info(
                        "Tài khoản đã được thêm vào lớp. "
                        "Bạn có thể đăng nhập ngay."
                    )

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
                "Quản lý lớp học",
                "Tạo lớp học",
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

    user = st.session_state.user

    st.markdown("""
    <div class="hero">

        <h1>Tổng quan lớp học</h1>

        <p>
            Quản lý lớp học, bài giảng,
            bài tập và tiến độ học sinh.
        </p>

    </div>
    """, unsafe_allow_html=True)


    classes = teacher_classes(
        user["id"]
    )

    students = fetch("""
        SELECT COUNT(DISTINCT cm.student_id) n

        FROM class_members cm

        JOIN classes c
            ON c.id=cm.class_id

        WHERE c.teacher_id=?
    """, (
        user["id"],
    ))[0]["n"]


    lessons = fetch("""
        SELECT COUNT(*) n
        FROM lessons l

        JOIN classes c
            ON c.id=l.class_id

        WHERE c.teacher_id=?
    """, (
        user["id"],
    ))[0]["n"]


    exercises = fetch("""
        SELECT COUNT(*) n
        FROM exercises e

        JOIN classes c
            ON c.id=e.class_id

        WHERE c.teacher_id=?
    """, (
        user["id"],
    ))[0]["n"]


    submissions = fetch("""
        SELECT COUNT(*) n

        FROM submissions s

        JOIN exercises e
            ON e.id=s.exercise_id

        JOIN classes c
            ON c.id=e.class_id

        WHERE c.teacher_id=?
    """, (
        user["id"],
    ))[0]["n"]


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
            "Bạn chưa tạo lớp học nào."
        )

        return


    for cls in classes:

        member_count = fetch("""
            SELECT COUNT(*) n
            FROM class_members
            WHERE class_id=?
        """, (
            cls["id"],
        ))[0]["n"]


        lesson_count = fetch("""
            SELECT COUNT(*) n
            FROM lessons
            WHERE class_id=?
        """, (
            cls["id"],
        ))[0]["n"]


        st.markdown(f"""
        <div class="card">

            <span class="badge">
                Lớp học
            </span>

            <div class="student-name">
                {cls["class_name"]}
            </div>

            <p>
                {cls["description"] or ""}
            </p>

            <div class="class-code">
                {cls["class_code"]}
            </div>

            <br>

            <span class="small">
                {member_count} học sinh •
                {lesson_count} bài giảng
            </span>

        </div>
        """, unsafe_allow_html=True)


# ============================================================
# CREATE CLASS
# ============================================================

def create_class():

    user = st.session_state.user

    st.markdown("## Tạo lớp học mới")

    st.info(
        "Bạn tự đặt Mã lớp. "
        "Học sinh sẽ dùng mã này để đăng ký và tham gia lớp."
    )


    with st.form("create_class_form"):

        class_name = st.text_input(
            "Tên lớp",
            placeholder="Ví dụ: English B1"
        )

        class_code = st.text_input(
            "Mã lớp",
            placeholder="Ví dụ: B1-2026"
        )

        description = st.text_area(
            "Mô tả lớp",
            placeholder="Ví dụ: Lớp tiếng Anh trình độ B1"
        )


        submit = st.form_submit_button(
            "Tạo lớp học",
            use_container_width=True
        )


    if submit:

        class_name = class_name.strip()
        class_code = class_code.strip().upper()


        if not class_name:

            st.error(
                "Tên lớp không được để trống."
            )

            return


        if not class_code:

            st.error(
                "Mã lớp không được để trống."
            )

            return


        if len(class_code) < 4:

            st.error(
                "Mã lớp nên có ít nhất 4 ký tự."
            )

            return


        existing = fetch("""
            SELECT id
            FROM classes
            WHERE UPPER(class_code)=?
        """, (
            class_code,
        ))


        if existing:

            st.error(
                "Mã lớp này đã tồn tại. "
                "Hãy chọn mã khác."
            )

            return


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
            user["id"],
            class_name,
            class_code,
            description,
            now()
        ))


        st.success(
            "Đã tạo lớp học thành công!"
        )

        st.markdown(
            f"""
            <div class="class-code">
                {class_code}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.info(
            "Hãy gửi mã này cho học sinh "
            "để các bạn đăng ký vào lớp."
        )


# ============================================================
# MANAGE CLASSES
# ============================================================

def manage_classes():

    user = st.session_state.user

    st.markdown("## Quản lý lớp học")

    classes = teacher_classes(
        user["id"]
    )


    if not classes:

        st.info(
            "Bạn chưa có lớp học nào."
        )

        return


    for cls in classes:

        members = fetch("""
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
        """, (
            cls["id"],
        ))


        with st.expander(
            f"{cls['class_name']} — Mã: {cls['class_code']}"
        ):

            st.markdown(
                f"""
                <div class="class-code">
                    {cls["class_code"]}
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write(
                cls["description"] or ""
            )


            st.markdown(
                f"### Học sinh ({len(members)})"
            )


            if members:

                data = []

                for member in members:

                    data.append({
                        "Họ và tên":
                            member["full_name"],

                        "Tên đăng nhập":
                            member["username"],

                        "Ngày tham gia":
                            member["joined_at"]
                    })


                st.dataframe(
                    pd.DataFrame(data),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "Chưa có học sinh nào tham gia lớp."
                )


# ============================================================
# TEACHER LESSONS
# ============================================================

def teacher_lessons():

    user = st.session_state.user

    st.markdown("## Danh sách bài giảng")


    lessons = fetch("""
        SELECT
            l.*,
            c.class_name,
            c.class_code,

            COUNT(v.id)
                AS so_luot_xem

        FROM lessons l

        JOIN classes c
            ON c.id=l.class_id

        LEFT JOIN lesson_views v
            ON v.lesson_id=l.id

        WHERE c.teacher_id=?

        GROUP BY l.id

        ORDER BY l.created_at DESC
    """, (
        user["id"],
    ))


    if not lessons:

        st.info(
            "Chưa có bài giảng."
        )

        return


    for lesson in lessons:

        st.markdown(f"""
        <div class="card">

            <span class="badge">
                {lesson["class_name"]}
                •
                {lesson["class_code"]}
            </span>

            <br><br>

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
                Lượt xem:
                {lesson["so_luot_xem"]}
            </span>

        </div>
        """, unsafe_allow_html=True)


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

    user = st.session_state.user

    st.markdown(
        "## Tạo bài giảng mới"
    )


    classes = teacher_classes(
        user["id"]
    )


    if not classes:

        st.warning(
            "Bạn cần tạo lớp học trước "
            "khi đăng bài giảng."
        )

        return


    class_dict = {
        f"{c['class_name']} — {c['class_code']}":
            c["id"]
        for c in classes
    }


    with st.form("create_lesson"):

        selected_class = st.selectbox(
            "Đăng bài giảng cho lớp",
            list(class_dict.keys())
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
            "Bạn có thể tải video trực tiếp từ máy tính."
        )


        video = st.file_uploader(
            "Chọn video",
            type=[
                "mp4",
                "mov",
                "webm",
                "m4v"
            ],
            help="Khuyến nghị MP4."
        )


        if video is not None:

            st.video(video)

            st.caption(
                f"Video đã chọn: {video.name}"
            )


        resource = st.text_input(
            "Đường dẫn tài liệu bên ngoài (nếu có)"
        )


        submit = st.form_submit_button(
            "Đăng bài giảng",
            use_container_width=True
        )


    if submit:

        if not title or not content:

            st.error(
                "Tên bài giảng và nội dung không được để trống."
            )

            return


        video_file = None
        video_name = None


        if video is not None:

            safe_name = Path(
                video.name
            ).name.replace(
                " ",
                "_"
            )


            unique_name = (
                datetime.now().strftime(
                    "%Y%m%d_%H%M%S_%f"
                )
                + "_"
                + safe_name
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
                class_id,
                title,
                description,
                level,
                category,
                content,
                resource_url,
                video_file,
                video_name,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            class_dict[selected_class],
            title,
            description,
            level,
            category,
            content,
            resource,
            video_file,
            video_name,
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

    user = st.session_state.user

    st.markdown(
        "## Tạo bài tập mới"
    )


    classes = teacher_classes(
        user["id"]
    )


    if not classes:

        st.warning(
            "Bạn cần tạo lớp trước."
        )

        return


    class_dict = {
        f"{c['class_name']} — {c['class_code']}":
            c["id"]
        for c in classes
    }


    selected_class = st.selectbox(
        "Lớp học",
        list(class_dict.keys())
    )


    class_id = class_dict[
        selected_class
    ]


    lessons = fetch("""
        SELECT id, title
        FROM lessons
        WHERE class_id=?
        ORDER BY title
    """, (
        class_id,
    ))


    lesson_dict = {
        "Không liên kết bài giảng":
            None
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

        if not title or not questions:

            st.error(
                "Tên bài tập và nội dung câu hỏi là bắt buộc."
            )

            return


        execute("""
            INSERT INTO exercises
            (
                class_id,
                lesson_id,
                title,
                instructions,
                questions,
                max_score,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            class_id,
            lesson_dict[linked],
            title,
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

    user = st.session_state.user

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

            e.max_score,

            c.class_name

        FROM submissions s

        JOIN users u
            ON u.id=s.student_id

        JOIN exercises e
            ON e.id=s.exercise_id

        JOIN classes c
            ON c.id=e.class_id

        WHERE c.teacher_id=?

        ORDER BY s.submitted_at DESC
    """, (
        user["id"],
    ))


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

            <span class="badge">
            {submission["class_name"]}
            </span>
            """,
            unsafe_allow_html=True
        )


        st.write(
            "**Bài làm của học sinh:**"
        )

        st.write(
            submission["answer"]
            or
            "(Không có nội dung)"
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
                    submission["score"]
                    or 0
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

                SET
                    score=?,
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

    user = st.session_state.user

    st.markdown(
        "## Quản lý học sinh"
    )


    classes = teacher_classes(
        user["id"]
    )


    if not classes:

        st.info(
            "Bạn chưa tạo lớp nào."
        )

        return


    class_dict = {
        f"{c['class_name']} — {c['class_code']}":
            c["id"]
        for c in classes
    }


    selected = st.selectbox(
        "Chọn lớp",
        list(class_dict.keys())
    )


    class_id = class_dict[
        selected
    ]


    students = fetch("""
        SELECT
            u.*,
            cm.joined_at

        FROM class_members cm

        JOIN users u
            ON u.id=cm.student_id

        WHERE cm.class_id=?

        ORDER BY u.full_name
    """, (
        class_id,
    ))


    if not students:

        st.info(
            "Lớp này chưa có học sinh."
        )

        return


    student_names = [
        s["full_name"]
        for s in students
    ]


    selected_name = st.selectbox(
        "Chọn học sinh",
        student_names
    )


    student = next(
        s for s in students
        if s["full_name"] == selected_name
    )


    p = student_progress(
        student["id"],
        class_id
    )


    st.markdown(f"""
    <div class="card">

        <div class="student-name">
            {student["full_name"]}
        </div>

        <div class="small">
            Tên đăng nhập:
            {student["username"]}
        </div>

        <div class="small">
            Ngày tham gia:
            {student["joined_at"]}
        </div>

    </div>
    """, unsafe_allow_html=True)


    a, b, c, d = st.columns(4)


    a.metric(
        "Mức độ tham gia",
        f"{p['participation']}%"
    )


    b.metric(
        "Bài giảng",
        f"{p['viewed_lessons']}/{p['total_lessons']}"
    )


    c.metric(
        "Bài tập",
        f"{p['completed_exercises']}/{p['total_exercises']}"
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


# ============================================================
# LESSON VIEWS
# ============================================================

def teacher_lesson_views():

    user = st.session_state.user

    st.markdown(
        "## Lượt xem bài giảng"
    )


    lessons = fetch("""
        SELECT
            l.id,
            l.title,
            c.class_name

        FROM lessons l

        JOIN classes c
            ON c.id=l.class_id

        WHERE c.teacher_id=?

        ORDER BY l.title
    """, (
        user["id"],
    ))


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

            u.full_name
                AS "Họ và tên",

            u.username
                AS "Tên đăng nhập",

            v.first_viewed
                AS "Lần xem đầu",

            v.last_viewed
                AS "Lần xem gần nhất",

            v.view_count
                AS "Số lần xem"

        FROM lesson_views v

        JOIN users u
            ON u.id=v.student_id

        JOIN class_members cm
            ON cm.student_id=u.id

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


    st.markdown(
        f"### Học sinh đã xem: {selected['title']}"
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
            "Chưa có học sinh nào xem bài giảng này."
        )


# ============================================================
# TEACHER ACTIVITY
# ============================================================

def teacher_activity():

    user = st.session_state.user

    st.markdown(
        "## Hoạt động học tập"
    )


    rows = fetch("""
        SELECT

            a.created_at
                AS "Thời gian",

            u.full_name
                AS "Học sinh",

            a.action
                AS "Hoạt động",

            a.object_name
                AS "Nội dung"

        FROM activity a

        LEFT JOIN users u
            ON u.id=a.student_id

        JOIN class_members cm
            ON cm.student_id=u.id

        JOIN classes c
            ON c.id=cm.class_id

        WHERE c.teacher_id=?

        ORDER BY a.created_at DESC

        LIMIT 300
    """, (
        user["id"],
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


        classes = student_classes(
            st.session_state.user["id"]
        )


        if classes:

            class_options = [
                f"{c['class_name']} — {c['class_code']}"
                for c in classes
            ]


            selected_class_name = st.selectbox(
                "Lớp học",
                class_options
            )


            selected_index = (
                class_options.index(
                    selected_class_name
                )
            )


            st.session_state.current_class_id = (
                classes[selected_index]["id"]
            )

        else:

            st.warning(
                "Bạn chưa tham gia lớp nào."
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

    class_id = st.session_state.get(
        "current_class_id"
    )


    if not class_id:

        st.warning(
            "Bạn chưa tham gia lớp học nào."
        )

        return


    classes = student_classes(
        user["id"]
    )


    current_class = next(
        (
            c for c in classes
            if c["id"] == class_id
        ),
        None
    )


    if not current_class:

        st.error(
            "Không tìm thấy lớp học."
        )

        return


    p = student_progress(
        user["id"],
        class_id
    )


    st.markdown(f"""
    <div class="hero">

        <h1>
            Xin chào, {user["full_name"]}!
        </h1>

        <p>
            Lớp:
            <strong>
                {current_class["class_name"]}
            </strong>
        </p>

        <p>
            Chào mừng bạn quay lại EnglishHub.
        </p>

    </div>
    """, unsafe_allow_html=True)


    a, b, c, d = st.columns(4)


    a.metric(
        "Mức độ tham gia",
        f"{p['participation']}%"
    )


    b.metric(
        "Bài giảng đã học",
        f"{p['viewed_lessons']}/{p['total_lessons']}"
    )


    c.metric(
        "Bài tập đã làm",
        f"{p['completed_exercises']}/{p['total_exercises']}"
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
        class_id
    ))


    if not lessons:

        st.info(
            "Giáo viên chưa đăng bài giảng nào."
        )

        return


    for lesson in lessons[:8]:

        st.markdown(f"""
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
        """, unsafe_allow_html=True)


        if st.button(
            "Mở bài giảng",
            key=f"dashboard_lesson_{lesson['id']}"
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

            SET
                last_viewed=?,
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

    class_id = st.session_state.get(
        "current_class_id"
    )


    if not class_id:

        st.warning(
            "Bạn chưa tham gia lớp."
        )

        return


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


        st.markdown(f"""
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
        """, unsafe_allow_html=True)


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
        """,
        (
            lesson_id,
        )
    )


    if not rows:

        st.session_state.open_lesson = None

        return


    lesson = rows[0]


    # --------------------------------------------------------
    # BẢO MẬT:
    # KIỂM TRA HỌC SINH CÓ THUỘC LỚP KHÔNG
    # --------------------------------------------------------

    member = fetch("""
        SELECT id
        FROM class_members

        WHERE class_id=?
        AND student_id=?
    """, (
        lesson["class_id"],
        user["id"]
    ))


    if not member:

        st.error(
            "Bạn không có quyền xem bài giảng này."
        )

        st.session_state.open_lesson = None

        return


    record_lesson_view(
        lesson["id"],
        user["id"],
        lesson["title"]
    )


    st.markdown(f"""
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
    """, unsafe_allow_html=True)


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
                "Video của bài giảng hiện không khả dụng."
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

    class_id = st.session_state.get(
        "current_class_id"
    )


    if not class_id:

        st.warning(
            "Bạn chưa tham gia lớp."
        )

        return


    st.markdown(
        "## Bài tập"
    )


    exercises = fetch("""
        SELECT

            e.*,

            l.title
                AS lesson_title,

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

                        SET
                            answer=?,
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
# STUDENT PROGRESS
# ============================================================

def student_progress_page():

    user = st.session_state.user

    class_id = st.session_state.get(
        "current_class_id"
    )


    if not class_id:

        st.warning(
            "Bạn chưa tham gia lớp."
        )

        return


    p = student_progress(
        user["id"],
        class_id
    )


    st.markdown("""
    <div class="hero">

        <h1>
            Tiến độ học tập
        </h1>

    </div>
    """, unsafe_allow_html=True)


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
        f"{p['viewed_lessons']}/{p['total_lessons']}"
    )


    c.metric(
        "Bài tập",
        f"{p['completed_exercises']}/{p['total_exercises']}"
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

            l.title
                AS "Bài giảng",

            l.level
                AS "Trình độ",

            l.category
                AS "Chủ đề",

            v.first_viewed
                AS "Lần xem đầu tiên",

            v.last_viewed
                AS "Lần xem gần nhất",

            v.view_count
                AS "Số lần xem"

        FROM lesson_views v

        JOIN lessons l
            ON l.id=v.lesson_id

        WHERE v.student_id=?
        AND l.class_id=?

        ORDER BY v.last_viewed DESC

    """, (
        user["id"],
        class_id
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

            e.title
                AS "Bài tập",

            s.score
                AS "Điểm",

            e.max_score
                AS "Điểm tối đa",

            s.feedback
                AS "Nhận xét giáo viên",

            s.submitted_at
                AS "Thời gian nộp"

        FROM submissions s

        JOIN exercises e
            ON e.id=s.exercise_id

        WHERE s.student_id=?
        AND e.class_id=?

        ORDER BY s.submitted_at DESC

    """, (
        user["id"],
        class_id
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
# KHỞI TẠO SESSION
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


if "current_class_id" not in st.session_state:

    st.session_state.current_class_id = None


if "open_lesson" not in st.session_state:

    st.session_state.open_lesson = None


# ============================================================
# CHẠY WEBSITE
# ============================================================

if not st.session_state.user:

    login_page()


else:

    user = st.session_state.user


    # ========================================================
    # TEACHER
    # ========================================================

    if user["role"] == "teacher":

        page = teacher_sidebar()


        if page == "Tổng quan":

            teacher_dashboard()


        elif page == "Quản lý lớp học":

            manage_classes()


        elif page == "Tạo lớp học":

            create_class()


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
