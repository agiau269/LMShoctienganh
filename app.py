import streamlit as st
import sqlite3
import hashlib
import hmac
import os
import secrets
from datetime import datetime
from pathlib import Path
import pandas as pd


# ============================================================
# ENGLISHHUB LMS
# FULL VERSION
# Teacher / Student
# SQLite
# Class codes
# Video upload
# Student progress
# ============================================================


# ============================================================
# 1. CẤU HÌNH
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
# 2. GIAO DIỆN
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        color: #666666;
        margin-bottom: 25px;
    }

    .card {
        padding: 20px;
        border: 1px solid #dddddd;
        border-radius: 12px;
        margin-bottom: 15px;
        background: white;
    }

    .class-code {
        font-size: 28px;
        font-weight: 700;
        letter-spacing: 3px;
    }

    .small-text {
        color: #777777;
        font-size: 14px;
    }

    .success-box {
        padding: 15px;
        border-radius: 10px;
        background: #eaf7ea;
        border: 1px solid #b7dfb7;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 3. DATABASE
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

    con.executescript(
        """
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
            teacher_id INTEGER NOT NULL,
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
            teacher_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            lesson_id INTEGER,
            title TEXT NOT NULL,
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
            action TEXT NOT NULL,
            object_name TEXT,
            created_at TEXT NOT NULL
        );
        """
    )

    con.commit()
    con.close()


init_db()


# ============================================================
# 4. HÀM CƠ BẢN
# ============================================================

def now():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


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
# 5. PASSWORD
# ============================================================

def password_hash(password):

    salt = os.urandom(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )

    return salt.hex() + ":" + key.hex()


def check_password(password, stored):

    try:

        salt, key = stored.split(":")

        new_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            120000
        )

        return hmac.compare_digest(
            new_key.hex(),
            key
        )

    except Exception:

        return False


# ============================================================
# 6. ACTIVITY
# ============================================================

def log_activity(
    student_id,
    action,
    object_name=""
):

    execute(
        """
        INSERT INTO activity
        (student_id, action, object_name, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            student_id,
            action,
            object_name,
            now()
        )
    )


# ============================================================
# 7. TẠO MÃ LỚP
# ============================================================

def generate_class_code():

    while True:

        code = secrets.token_hex(3).upper()

        exists = fetch(
            """
            SELECT id
            FROM classes
            WHERE class_code=?
            """,
            (code,)
        )

        if not exists:

            return code


# ============================================================
# 8. ĐĂNG KÝ
# ============================================================

def register_student(
    full_name,
    username,
    password,
    class_code
):

    full_name = full_name.strip()
    username = username.strip().lower()
    class_code = class_code.strip().upper()

    if not full_name:
        return False, "Vui lòng nhập họ và tên."

    if not username:
        return False, "Vui lòng nhập tên đăng nhập."

    if not password:
        return False, "Vui lòng nhập mật khẩu."

    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự."

    if not class_code:
        return False, "Học sinh bắt buộc phải nhập mã lớp."

    class_rows = fetch(
        """
        SELECT *
        FROM classes
        WHERE class_code=?
        """,
        (class_code,)
    )

    if not class_rows:
        return False, "Mã lớp không tồn tại."

    try:

        student_id = execute(
            """
            INSERT INTO users
            (full_name, username, password_hash, role, created_at)
            VALUES (?, ?, ?, 'student', ?)
            """,
            (
                full_name,
                username,
                password_hash(password),
                now()
            )
        )

    except sqlite3.IntegrityError:

        return False, "Tên đăng nhập này đã tồn tại."

    execute(
        """
        INSERT INTO class_members
        (class_id, student_id, joined_at)
        VALUES (?, ?, ?)
        """,
        (
            class_rows[0]["id"],
            student_id,
            now()
        )
    )

    return True, "Đăng ký thành công."


# ============================================================
# 9. ĐĂNG KÝ GIÁO VIÊN
# ============================================================

def register_teacher(
    full_name,
    username,
    password
):

    full_name = full_name.strip()
    username = username.strip().lower()

    if not full_name:
        return False, "Vui lòng nhập họ và tên."

    if not username:
        return False, "Vui lòng nhập tên đăng nhập."

    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự."

    try:

        execute(
            """
            INSERT INTO users
            (full_name, username, password_hash, role, created_at)
            VALUES (?, ?, ?, 'teacher', ?)
            """,
            (
                full_name,
                username,
                password_hash(password),
                now()
            )
        )

        return True, "Tạo tài khoản giáo viên thành công."

    except sqlite3.IntegrityError:

        return False, "Tên đăng nhập này đã tồn tại."


# ============================================================
# 10. LOGIN
# ============================================================

def login(
    username,
    password,
    role
):

    rows = fetch(
        """
        SELECT *
        FROM users
        WHERE username=?
        AND role=?
        """,
        (
            username.strip().lower(),
            role
        )
    )

    if rows:

        user = rows[0]

        if check_password(
            password,
            user["password_hash"]
        ):

            return dict(user)

    return None


# ============================================================
# 11. LẤY LỚP CỦA HỌC SINH
# ============================================================

def get_student_classes(student_id):

    return fetch(
        """
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
        """,
        (student_id,)
    )


# ============================================================
# 12. PROGRESS
# ============================================================

def student_progress(student_id):

    class_rows = get_student_classes(student_id)

    if not class_rows:

        return {
            "total_lessons": 0,
            "viewed_lessons": 0,
            "total_exercises": 0,
            "completed_exercises": 0,
            "average": 0,
            "participation": 0
        }

    class_ids = [
        row["id"]
        for row in class_rows
    ]

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
        SELECT COUNT(DISTINCT lv.lesson_id) n
        FROM lesson_views lv
        JOIN lessons l
            ON l.id=lv.lesson_id
        WHERE lv.student_id=?
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
        SELECT COUNT(DISTINCT s.exercise_id) n
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
        lesson_rate * 0.4 +
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
# 13. LOGIN PAGE
# ============================================================

def login_page():

    st.markdown(
        '<div class="main-title">EnglishHub LMS</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">Nền tảng học tiếng Anh dành cho lớp học của Tom và các bạn</div>',
        unsafe_allow_html=True
    )

    left, right = st.columns(2)

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    with left:

        st.subheader("Đăng nhập")

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

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    with right:

        st.subheader("Tạo tài khoản")

        account_type = st.selectbox(
            "Loại tài khoản",
            [
                "Học sinh",
                "Giáo viên"
            ]
        )

        if account_type == "Học sinh":

            st.info(
                "Học sinh bắt buộc phải có mã lớp do giáo viên cung cấp."
            )

            with st.form("student_register"):

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

                class_code = st.text_input(
                    "Mã lớp"
                )

                submit = st.form_submit_button(
                    "Đăng ký học sinh",
                    use_container_width=True
                )

            if submit:

                ok, message = register_student(
                    full_name,
                    username,
                    password,
                    class_code
                )

                if ok:
                    st.success(message)
                else:
                    st.error(message)

        else:

            st.info(
                "Giáo viên không cần mã lớp để đăng ký. "
                "Sau khi đăng nhập, giáo viên có thể tự tạo nhiều lớp."
            )

            with st.form("teacher_register"):

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

                submit = st.form_submit_button(
                    "Đăng ký giáo viên",
                    use_container_width=True
                )

            if submit:

                ok, message = register_teacher(
                    full_name,
                    username,
                    password
                )

                if ok:
                    st.success(message)
                else:
                    st.error(message)


# ============================================================
# 14. TEACHER SIDEBAR
# ============================================================

def teacher_sidebar():

    with st.sidebar:

        st.title("EnglishHub LMS")

        st.caption(
            f"Giáo viên: {st.session_state.user['full_name']}"
        )

        page = st.radio(
            "MENU GIÁO VIÊN",
            [
                "Tổng quan",
                "Lớp học",
                "Tạo lớp",
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
# 15. TEACHER DASHBOARD
# ============================================================

def teacher_dashboard():

    teacher_id = st.session_state.user["id"]

    st.title("Tổng quan lớp học")

    st.write(
        "Quản lý lớp học, bài giảng, bài tập và tiến độ học sinh."
    )

    students = fetch(
        """
        SELECT COUNT(DISTINCT cm.student_id) n
        FROM class_members cm
        JOIN classes c
            ON c.id=cm.class_id
        WHERE c.teacher_id=?
        """,
        (teacher_id,)
    )[0]["n"]

    classes = fetch(
        """
        SELECT COUNT(*) n
        FROM classes
        WHERE teacher_id=?
        """,
        (teacher_id,)
    )[0]["n"]

    lessons = fetch(
        """
        SELECT COUNT(*) n
        FROM lessons
        WHERE teacher_id=?
        """,
        (teacher_id,)
    )[0]["n"]

    exercises = fetch(
        """
        SELECT COUNT(*) n
        FROM exercises
        WHERE teacher_id=?
        """,
        (teacher_id,)
    )[0]["n"]

    a, b, c, d = st.columns(4)

    a.metric("Học sinh", students)
    b.metric("Lớp học", classes)
    c.metric("Bài giảng", lessons)
    d.metric("Bài tập", exercises)

    st.subheader("Danh sách học sinh")

    rows = fetch(
        """
        SELECT
            u.id,
            u.full_name,
            u.username,
            c.class_name,
            c.class_code
        FROM class_members cm
        JOIN users u
            ON u.id=cm.student_id
        JOIN classes c
            ON c.id=cm.class_id
        WHERE c.teacher_id=?
        ORDER BY u.full_name
        """,
        (teacher_id,)
    )

    if rows:

        st.dataframe(
            pd.DataFrame(
                [dict(row) for row in rows]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Chưa có học sinh tham gia lớp."
        )


# ============================================================
# 16. TẠO LỚP
# ============================================================

def create_class():

    teacher_id = st.session_state.user["id"]

    st.title("Tạo lớp học")

    st.write(
        "Tạo mã lớp và gửi mã này cho học sinh."
    )

    with st.form("create_class"):

        class_name = st.text_input(
            "Tên lớp",
            placeholder="Ví dụ: English B1 - Morning"
        )

        submit = st.form_submit_button(
            "Tạo lớp",
            use_container_width=True
        )

    if submit:

        if not class_name.strip():

            st.error(
                "Vui lòng nhập tên lớp."
            )

        else:

            code = generate_class_code()

            execute(
                """
                INSERT INTO classes
                (teacher_id, class_name, class_code, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    teacher_id,
                    class_name.strip(),
                    code,
                    now()
                )
            )

            st.success(
                "Tạo lớp thành công."
            )

            st.info(
                f"Mã lớp của bạn là: {code}"
            )

            st.rerun()


# ============================================================
# 17. QUẢN LÝ LỚP
# ============================================================

def teacher_classes():

    teacher_id = st.session_state.user["id"]

    st.title("Lớp học")

    classes = fetch(
        """
        SELECT
            c.*,
            COUNT(cm.student_id) AS student_count
        FROM classes c
        LEFT JOIN class_members cm
            ON cm.class_id=c.id
        WHERE c.teacher_id=?
        GROUP BY c.id
        ORDER BY c.created_at DESC
        """,
        (teacher_id,)
    )

    if not classes:

        st.info(
            "Bạn chưa tạo lớp nào."
        )

        return

    for cls in classes:

        st.markdown(
            f"### {cls['class_name']}"
        )

        st.markdown(
            f"Mã lớp: **{cls['class_code']}**"
        )

        st.write(
            f"Số học sinh: {cls['student_count']}"
        )

        with st.expander(
            "Xem học sinh"
        ):

            students = fetch(
                """
                SELECT
                    u.full_name,
                    u.username,
                    cm.joined_at
                FROM class_members cm
                JOIN users u
                    ON u.id=cm.student_id
                WHERE cm.class_id=?
                ORDER BY u.full_name
                """,
                (cls["id"],)
            )

            if students:

                st.dataframe(
                    pd.DataFrame(
                        [dict(s) for s in students]
                    ),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "Chưa có học sinh."
                )

        st.divider()


# ============================================================
# 18. TẠO BÀI GIẢNG
# ============================================================

def create_lesson():

    teacher_id = st.session_state.user["id"]

    st.title("Tạo bài giảng")

    classes = fetch(
        """
        SELECT *
        FROM classes
        WHERE teacher_id=?
        ORDER BY class_name
        """,
        (teacher_id,)
    )

    if not classes:

        st.warning(
            "Bạn cần tạo lớp trước khi đăng bài giảng."
        )

        return

    class_dict = {
        f"{c['class_name']} — {c['class_code']}": c["id"]
        for c in classes
    }

    with st.form(
        "create_lesson_form"
    ):

        title = st.text_input(
            "Tên bài giảng"
        )

        description = st.text_area(
            "Mô tả ngắn"
        )

        class_name = st.selectbox(
            "Lớp học",
            list(class_dict.keys())
        )

        col1, col2 = st.columns(2)

        with col1:

            level = st.selectbox(
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

        with col2:

            category = st.selectbox(
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
            height=300,
            placeholder=(
                "Ví dụ:\n\n"
                "# Present Perfect\n\n"
                "Công thức...\n\n"
                "Ví dụ..."
            )
        )

        resource_url = st.text_input(
            "Link tài liệu bên ngoài (không bắt buộc)"
        )

        video = st.file_uploader(
            "Upload video bài giảng",
            type=[
                "mp4",
                "mov",
                "webm",
                "m4v"
            ],
            help="Chọn video từ máy tính của bạn."
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
                "Bạn cần nhập nội dung hoặc upload video."
            )

            return

        video_path = ""
        video_name = ""

        if video is not None:

            safe_name = (
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}_"
                f"{video.name}"
            )

            file_path = VIDEO_DIR / safe_name

            with open(
                file_path,
                "wb"
            ) as f:

                f.write(
                    video.getbuffer()
                )

            video_path = str(file_path)
            video_name = video.name

        execute(
            """
            INSERT INTO lessons
            (
                teacher_id,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                teacher_id,
                class_dict[class_name],
                title.strip(),
                description.strip(),
                level,
                category,
                content,
                resource_url,
                video_path,
                video_name,
                now()
            )
        )

        st.success(
            "Đã đăng bài giảng thành công."
        )

        st.rerun()


# ============================================================
# 19. DANH SÁCH BÀI GIẢNG GIÁO VIÊN
# ============================================================

def teacher_lessons():

    teacher_id = st.session_state.user["id"]

    st.title("Danh sách bài giảng")

    lessons = fetch(
        """
        SELECT
            l.*,
            c.class_name,
            c.class_code,
            COUNT(DISTINCT v.student_id) AS viewed_students
        FROM lessons l
        JOIN classes c
            ON c.id=l.class_id
        LEFT JOIN lesson_views v
            ON v.lesson_id=l.id
        WHERE l.teacher_id=?
        GROUP BY l.id
        ORDER BY l.created_at DESC
        """,
        (teacher_id,)
    )

    if not lessons:

        st.info(
            "Bạn chưa tạo bài giảng nào."
        )

        return

    for lesson in lessons:

        st.subheader(
            lesson["title"]
        )

        st.caption(
            f"{lesson['class_name']} | "
            f"Mã lớp: {lesson['class_code']} | "
            f"{lesson['level']} | "
            f"{lesson['category']}"
        )

        st.write(
            lesson["description"] or ""
        )

        if lesson["video_path"]:

            st.video(
                lesson["video_path"]
            )

        if lesson["content"]:

            with st.expander(
                "Xem nội dung bài giảng"
            ):

                st.markdown(
                    lesson["content"]
                )

        st.write(
            f"Học sinh đã xem: "
            f"**{lesson['viewed_students']}**"
        )

        if lesson["resource_url"]:

            st.link_button(
                "Mở tài liệu",
                lesson["resource_url"]
            )

        st.divider()


# ============================================================
# 20. TẠO BÀI TẬP
# ============================================================

def create_exercise():

    teacher_id = st.session_state.user["id"]

    st.title("Tạo bài tập")

    classes = fetch(
        """
        SELECT *
        FROM classes
        WHERE teacher_id=?
        ORDER BY class_name
        """,
        (teacher_id,)
    )

    if not classes:

        st.warning(
            "Bạn cần tạo lớp trước."
        )

        return

    class_dict = {
        f"{c['class_name']} — {c['class_code']}": c["id"]
        for c in classes
    }

    selected_class = st.selectbox(
        "Lớp học",
        list(class_dict.keys())
    )

    lessons = fetch(
        """
        SELECT *
        FROM lessons
        WHERE teacher_id=?
        AND class_id=?
        ORDER BY title
        """,
        (
            teacher_id,
            class_dict[selected_class]
        )
    )

    lesson_dict = {
        "Không liên kết bài giảng": None
    }

    for lesson in lessons:

        lesson_dict[
            lesson["title"]
        ] = lesson["id"]

    with st.form(
        "create_exercise"
    ):

        title = st.text_input(
            "Tên bài tập"
        )

        linked_lesson = st.selectbox(
            "Bài giảng liên quan",
            list(lesson_dict.keys())
        )

        instructions = st.text_area(
            "Hướng dẫn"
        )

        questions = st.text_area(
            "Nội dung câu hỏi / yêu cầu",
            height=300
        )

        max_score = st.number_input(
            "Thang điểm",
            min_value=1,
            max_value=100,
            value=100
        )

        submit = st.form_submit_button(
            "Đăng bài tập",
            use_container_width=True
        )

    if submit:

        if not title.strip():

            st.error(
                "Tên bài tập không được để trống."
            )

            return

        if not questions.strip():

            st.error(
                "Nội dung câu hỏi không được để trống."
            )

            return

        execute(
            """
            INSERT INTO exercises
            (
                teacher_id,
                class_id,
                lesson_id,
                title,
                instructions,
                questions,
                max_score,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                teacher_id,
                class_dict[selected_class],
                lesson_dict[linked_lesson],
                title.strip(),
                instructions,
                questions,
                max_score,
                now()
            )
        )

        st.success(
            "Đã đăng bài tập."
        )

        st.rerun()


# ============================================================
# 21. CHẤM ĐIỂM
# ============================================================

def teacher_exercises():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Bài tập và chấm điểm"
    )

    submissions = fetch(
        """
        SELECT
            s.*,
            u.full_name AS student_name,
            u.username,
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
        WHERE e.teacher_id=?
        ORDER BY s.submitted_at DESC
        """,
        (teacher_id,)
    )

    if not submissions:

        st.info(
            "Chưa có học sinh nộp bài."
        )

        return

    for submission in submissions:

        st.subheader(
            f"{submission['student_name']} — "
            f"{submission['exercise_title']}"
        )

        st.caption(
            f"Lớp: {submission['class_name']}"
        )

        st.write(
            "**Bài làm:**"
        )

        st.write(
            submission["answer"] or "(Không có nội dung)"
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
                "Nhận xét",
                value=(
                    submission["feedback"]
                    or ""
                )
            )

            save = st.form_submit_button(
                "Lưu điểm",
                use_container_width=True
            )

        if save:

            execute(
                """
                UPDATE submissions
                SET score=?,
                    feedback=?
                WHERE id=?
                """,
                (
                    score,
                    feedback,
                    submission["id"]
                )
            )

            st.success(
                "Đã lưu điểm."
            )

            st.rerun()

        st.divider()


# ============================================================
# 22. HỌC SINH CỦA GIÁO VIÊN
# ============================================================

def teacher_students():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Học sinh"
    )

    students = fetch(
        """
        SELECT DISTINCT
            u.id,
            u.full_name,
            u.username,
            u.created_at,
            c.class_name,
            c.class_code
        FROM class_members cm
        JOIN users u
            ON u.id=cm.student_id
        JOIN classes c
            ON c.id=cm.class_id
        WHERE c.teacher_id=?
        ORDER BY u.full_name
        """,
        (teacher_id,)
    )

    if not students:

        st.info(
            "Chưa có học sinh."
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
        s
        for s in students
        if s["full_name"] == selected_name
    )

    p = student_progress(
        student["id"]
    )

    st.subheader(
        student["full_name"]
    )

    st.write(
        f"Tên đăng nhập: {student['username']}"
    )

    st.write(
        f"Lớp: {student['class_name']} "
        f"({student['class_code']})"
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Tham gia",
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
        "Điểm TB",
        f"{p['average']}%"
    )

    st.progress(
        p["participation"] / 100
    )

    st.subheader(
        "Lịch sử xem bài"
    )

    views = fetch(
        """
        SELECT
            l.title AS "Bài giảng",
            l.level AS "Trình độ",
            l.category AS "Chủ đề",
            v.first_viewed AS "Xem lần đầu",
            v.last_viewed AS "Xem gần nhất",
            v.view_count AS "Số lần xem"
        FROM lesson_views v
        JOIN lessons l
            ON l.id=v.lesson_id
        WHERE v.student_id=?
        AND l.teacher_id=?
        ORDER BY v.last_viewed DESC
        """,
        (
            student["id"],
            teacher_id
        )
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
            "Học sinh chưa xem bài nào."
        )


# ============================================================
# 23. LƯỢT XEM
# ============================================================

def teacher_lesson_views():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Lượt xem bài giảng"
    )

    lessons = fetch(
        """
        SELECT *
        FROM lessons
        WHERE teacher_id=?
        ORDER BY title
        """,
        (teacher_id,)
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
        f"{x['title']} — {x['class_id']}"
    )

    rows = fetch(
        """
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
        """,
        (selected["id"],)
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
# 24. ACTIVITY
# ============================================================

def teacher_activity():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Hoạt động học tập"
    )

    rows = fetch(
        """
        SELECT
            a.created_at AS "Thời gian",
            u.full_name AS "Học sinh",
            a.action AS "Hoạt động",
            a.object_name AS "Nội dung"
        FROM activity a
        JOIN users u
            ON u.id=a.student_id
        JOIN class_members cm
            ON cm.student_id=u.id
        JOIN classes c
            ON c.id=cm.class_id
        WHERE c.teacher_id=?
        ORDER BY a.created_at DESC
        LIMIT 300
        """,
        (teacher_id,)
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
            "Chưa có hoạt động."
        )


# ============================================================
# 25. STUDENT SIDEBAR
# ============================================================

def student_sidebar():

    with st.sidebar:

        st.title(
            "EnglishHub LMS"
        )

        st.caption(
            f"Học sinh: "
            f"{st.session_state.user['full_name']}"
        )

        page = st.radio(
            "MENU HỌC SINH",
            [
                "Trang chủ",
                "Lớp học",
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
# 26. STUDENT DASHBOARD
# ============================================================

def student_dashboard():

    user = st.session_state.user

    p = student_progress(
        user["id"]
    )

    st.title(
        f"Xin chào, {user['full_name']}!"
    )

    st.write(
        "Chào mừng bạn quay lại EnglishHub LMS."
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

    st.subheader(
        "Lớp của bạn"
    )

    classes = get_student_classes(
        user["id"]
    )

    if classes:

        for cls in classes:

            st.info(
                f"{cls['class_name']} — "
                f"Mã lớp: {cls['class_code']} — "
                f"Giáo viên: {cls['teacher_name']}"
            )

    else:

        st.warning(
            "Bạn chưa tham gia lớp nào."
        )


# ============================================================
# 27. STUDENT CLASSES
# ============================================================

def student_classes():

    user = st.session_state.user

    st.title(
        "Lớp học của tôi"
    )

    classes = get_student_classes(
        user["id"]
    )

    if not classes:

        st.info(
            "Bạn chưa tham gia lớp nào."
        )

        return

    for cls in classes:

        st.subheader(
            cls["class_name"]
        )

        st.write(
            f"Giáo viên: {cls['teacher_name']}"
        )

        st.write(
            f"Mã lớp: {cls['class_code']}"
        )

        st.divider()


# ============================================================
# 28. RECORD VIEW
# ============================================================

def record_lesson_view(
    lesson_id,
    student_id,
    lesson_title
):

    existing = fetch(
        """
        SELECT *
        FROM lesson_views
        WHERE lesson_id=?
        AND student_id=?
        """,
        (
            lesson_id,
            student_id
        )
    )

    if existing:

        execute(
            """
            UPDATE lesson_views
            SET last_viewed=?,
                view_count=view_count+1
            WHERE lesson_id=?
            AND student_id=?
            """,
            (
                now(),
                lesson_id,
                student_id
            )
        )

    else:

        execute(
            """
            INSERT INTO lesson_views
            (
                lesson_id,
                student_id,
                first_viewed,
                last_viewed,
                view_count
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                lesson_id,
                student_id,
                now(),
                now()
            )
        )

        log_activity(
            student_id,
            "Đã xem bài giảng",
            lesson_title
        )


# ============================================================
# 29. STUDENT LESSONS
# ============================================================

def student_lessons():

    user = st.session_state.user

    st.title(
        "Bài giảng"
    )

    classes = get_student_classes(
        user["id"]
    )

    if not classes:

        st.warning(
            "Bạn chưa tham gia lớp nào."
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
            CASE
                WHEN v.id IS NULL
                THEN 0
                ELSE 1
            END AS viewed
        FROM lessons l
        JOIN classes c
            ON c.id=l.class_id
        LEFT JOIN lesson_views v
            ON v.lesson_id=l.id
            AND v.student_id=?
        WHERE l.class_id IN ({placeholders})
        ORDER BY l.created_at DESC
        """,
        [user["id"]] + class_ids
    )

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

        with st.expander(
            f"{lesson['title']} — {status}"
        ):

            st.caption(
                f"{lesson['class_name']} | "
                f"{lesson['level']} | "
                f"{lesson['category']}"
            )

            st.write(
                lesson["description"] or ""
            )

            record_lesson_view(
                lesson["id"],
                user["id"],
                lesson["title"]
            )

            if lesson["video_path"]:

                st.subheader(
                    "Video bài giảng"
                )

                st.video(
                    lesson["video_path"]
                )

            if lesson["content"]:

                st.subheader(
                    "Nội dung bài giảng"
                )

                st.markdown(
                    lesson["content"]
                )

            if lesson["resource_url"]:

                st.link_button(
                    "Mở tài liệu học tập",
                    lesson["resource_url"]
                )


# ============================================================
# 30. STUDENT EXERCISES
# ============================================================

def student_exercises():

    user = st.session_state.user

    st.title(
        "Bài tập"
    )

    classes = get_student_classes(
        user["id"]
    )

    if not classes:

        st.warning(
            "Bạn chưa tham gia lớp nào."
        )

        return

    class_ids = [
        c["id"]
        for c in classes
    ]

    placeholders = ",".join(
        ["?"] * len(class_ids)
    )

    exercises = fetch(
        f"""
        SELECT
            e.*,
            l.title AS lesson_title,
            c.class_name,
            s.answer,
            s.score,
            s.feedback,
            s.submitted_at
        FROM exercises e
        JOIN classes c
            ON c.id=e.class_id
        LEFT JOIN lessons l
            ON l.id=e.lesson_id
        LEFT JOIN submissions s
            ON s.exercise_id=e.id
            AND s.student_id=?
        WHERE e.class_id IN ({placeholders})
        ORDER BY e.created_at DESC
        """,
        [user["id"]] + class_ids
    )

    if not exercises:

        st.info(
            "Giáo viên chưa đăng bài tập."
        )

        return

    for exercise in exercises:

        if exercise["submitted_at"]:

            status = (
                f"Đã nộp — "
                f"{exercise['score']}/"
                f"{exercise['max_score']}"
            )

        else:

            status = "Chưa nộp"

        with st.expander(
            f"{exercise['title']} — {status}"
        ):

            st.caption(
                f"Lớp: {exercise['class_name']}"
            )

            if exercise["lesson_title"]:

                st.write(
                    f"Bài giảng: "
                    f"{exercise['lesson_title']}"
                )

            st.write(
                exercise["instructions"] or ""
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

                existing = fetch(
                    """
                    SELECT id
                    FROM submissions
                    WHERE exercise_id=?
                    AND student_id=?
                    """,
                    (
                        exercise["id"],
                        user["id"]
                    )
                )

                if existing:

                    execute(
                        """
                        UPDATE submissions
                        SET answer=?,
                            submitted_at=?
                        WHERE id=?
                        """,
                        (
                            answer,
                            now(),
                            existing[0]["id"]
                        )
                    )

                else:

                    execute(
                        """
                        INSERT INTO submissions
                        (
                            exercise_id,
                            student_id,
                            answer,
                            score,
                            submitted_at
                        )
                        VALUES (?, ?, ?, 0, ?)
                        """,
                        (
                            exercise["id"],
                            user["id"],
                            answer,
                            now()
                        )
                    )

                log_activity(
                    user["id"],
                    "Đã nộp bài tập",
                    exercise["title"]
                )

                st.success(
                    "Đã nộp bài."
                )

                st.rerun()

            if exercise["feedback"]:

                st.success(
                    "Nhận xét của giáo viên: "
                    + exercise["feedback"]
                )


# ============================================================
# 31. STUDENT PROGRESS PAGE
# ============================================================

def student_progress_page():

    user = st.session_state.user

    p = student_progress(
        user["id"]
    )

    st.title(
        "Tiến độ học tập"
    )

    st.progress(
        p["participation"] / 100
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

    st.subheader(
        "Lịch sử học bài"
    )

    views = fetch(
        """
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
        """,
        (user["id"],)
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

    st.subheader(
        "Kết quả bài tập"
    )

    results = fetch(
        """
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
        """,
        (user["id"],)
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
# 32. MAIN
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


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

        elif page == "Lớp học":

            teacher_classes()

        elif page == "Tạo lớp":

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

        elif page == "Lớp học":

            student_classes()

        elif page == "Bài giảng":

            student_lessons()

        elif page == "Bài tập":

            student_exercises()

        elif page == "Tiến độ học tập":

            student_progress_page()
