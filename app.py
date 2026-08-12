import streamlit as st
import sqlite3
import hashlib
import hmac
import os
import uuid
from datetime import datetime
from pathlib import Path
import pandas as pd


# ============================================================
# ENGLISHHUB LMS
# FULL VERSION
# ============================================================

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "englishhub.db"

VIDEO_DIR = BASE_DIR / "uploaded_videos"
VIDEO_DIR.mkdir(exist_ok=True)

DEFAULT_TEACHER_CODE = "ENGLISHHUB-TEACHER"


# ============================================================
# STREAMLIT CONFIG
# ============================================================

st.set_page_config(
    page_title="EnglishHub LMS",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


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
        class_code TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        class_name TEXT NOT NULL,
        class_code TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
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
        action TEXT NOT NULL,
        object_name TEXT,
        created_at TEXT NOT NULL
    );
    """)

    con.commit()

    # Migration cho database cũ nếu thiếu cột
    columns = [
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "class_code" not in columns:
        con.execute(
            "ALTER TABLE users ADD COLUMN class_code TEXT"
        )

    lesson_columns = [
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(lessons)"
        ).fetchall()
    ]

    if "teacher_id" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN teacher_id INTEGER"
        )

    if "video_path" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN video_path TEXT"
        )

    if "video_name" not in lesson_columns:
        con.execute(
            "ALTER TABLE lessons ADD COLUMN video_name TEXT"
        )

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

    con.commit()
    con.close()


init_db()


# ============================================================
# HELPER
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
            DEFAULT_TEACHER_CODE
        )


def password_hash(password):

    salt = os.urandom(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        120000
    )

    return (
        salt.hex()
        + ":"
        + key.hex()
    )


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
# AUTHENTICATION
# ============================================================

def register_teacher(
    full_name,
    username,
    password,
    code
):

    full_name = full_name.strip()
    username = username.strip().lower()
    code = code.strip()

    if not full_name:
        return False, "Vui lòng nhập họ và tên."

    if not username:
        return False, "Vui lòng nhập tên đăng nhập."

    if not password:
        return False, "Vui lòng nhập mật khẩu."

    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự."

    if not hmac.compare_digest(
        code,
        teacher_code()
    ):
        return False, "Mã giáo viên không chính xác."

    try:

        execute(
            """
            INSERT INTO users
            (
                full_name,
                username,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                full_name,
                username,
                password_hash(password),
                "teacher",
                now()
            )
        )

        return True, "Tạo tài khoản giáo viên thành công."

    except sqlite3.IntegrityError:

        return False, "Tên đăng nhập đã tồn tại."


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

        execute(
            """
            INSERT INTO users
            (
                full_name,
                username,
                password_hash,
                role,
                class_code,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                username,
                password_hash(password),
                "student",
                class_code,
                now()
            )
        )

        return True, "Tạo tài khoản học sinh thành công."

    except sqlite3.IntegrityError:

        return False, "Tên đăng nhập đã tồn tại."


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
# PROGRESS
# ============================================================

def student_progress(student_id):

    total_lessons = fetch(
        "SELECT COUNT(*) AS n FROM lessons"
    )[0]["n"]

    viewed_lessons = fetch(
        """
        SELECT COUNT(*) AS n
        FROM lesson_views
        WHERE student_id=?
        """,
        (student_id,)
    )[0]["n"]

    total_exercises = fetch(
        "SELECT COUNT(*) AS n FROM exercises"
    )[0]["n"]

    completed_exercises = fetch(
        """
        SELECT COUNT(*) AS n
        FROM submissions
        WHERE student_id=?
        """,
        (student_id,)
    )[0]["n"]

    avg = fetch(
        """
        SELECT AVG(
            CASE
                WHEN e.max_score > 0
                THEN s.score * 100.0 / e.max_score
                ELSE 0
            END
        ) AS a
        FROM submissions s
        JOIN exercises e
        ON e.id=s.exercise_id
        WHERE s.student_id=?
        """,
        (student_id,)
    )[0]["a"]

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

    if total_exercises:
        participation = (
            lesson_rate * 0.4
            +
            exercise_rate * 0.6
            *
            (average / 100)
        )
    else:
        participation = lesson_rate * 0.4

    return {
        "total_lessons": total_lessons,
        "viewed_lessons": viewed_lessons,
        "total_exercises": total_exercises,
        "completed_exercises": completed_exercises,
        "average": round(average, 1),
        "participation": round(
            participation,
            1
        )
    }


# ============================================================
# LOGIN PAGE
# ============================================================

def login_page():

    st.title("EnglishHub LMS")

    st.write(
        "Nền tảng học tiếng Anh dành cho lớp học của Tom và các bạn."
    )

    st.divider()

    left, right = st.columns(2)

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    with left:

        st.subheader("Đăng nhập")

        login_role = st.radio(
            "Bạn là:",
            [
                "Học sinh",
                "Giáo viên"
            ],
            horizontal=True
        )

        login_role_db = (
            "student"
            if login_role == "Học sinh"
            else "teacher"
        )

        with st.form("login_form"):

            username = st.text_input(
                "Tên đăng nhập",
                key="login_username"
            )

            password = st.text_input(
                "Mật khẩu",
                type="password",
                key="login_password"
            )

            submit = st.form_submit_button(
                "Đăng nhập",
                use_container_width=True
            )

        if submit:

            user = login(
                username,
                password,
                login_role_db
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

        register_role = st.selectbox(
            "Loại tài khoản",
            [
                "Học sinh",
                "Giáo viên"
            ]
        )

        with st.form(
            "register_form"
        ):

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

            if register_role == "Giáo viên":

                st.info(
                    "Giáo viên phải nhập Mã giáo viên để tạo tài khoản."
                )

                teacher_access_code = st.text_input(
                    "Mã giáo viên",
                    type="password"
                )

                class_code = ""

            else:

                st.info(
                    "Học sinh phải có Mã lớp do giáo viên cung cấp."
                )

                class_code = st.text_input(
                    "Mã lớp",
                    placeholder="Ví dụ: ENGLISH-A1-01"
                )

                teacher_access_code = ""

            submit_register = st.form_submit_button(
                "Tạo tài khoản",
                use_container_width=True
            )

        if submit_register:

            if register_role == "Giáo viên":

                ok, message = register_teacher(
                    full_name,
                    username,
                    password,
                    teacher_access_code
                )

            else:

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


# ============================================================
# TEACHER SIDEBAR
# ============================================================

def teacher_sidebar():

    with st.sidebar:

        st.title("EnglishHub LMS")

        st.caption(
            "Giáo viên: "
            +
            st.session_state.user[
                "full_name"
            ]
        )

        page = st.radio(
            "MENU GIÁO VIÊN",
            [
                "Tổng quan",
                "Quản lý lớp",
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

    st.title("Tổng quan lớp học")

    st.write(
        "Quản lý lớp, bài giảng, bài tập và tiến độ học sinh."
    )

    students = fetch(
        """
        SELECT COUNT(*) AS n
        FROM users
        WHERE role='student'
        AND class_code IN (
            SELECT class_code
            FROM classes
            WHERE teacher_id=?
        )
        """,
        (teacher_id,)
    )[0]["n"]

    lessons = fetch(
        """
        SELECT COUNT(*) AS n
        FROM lessons
        WHERE teacher_id=?
        """,
        (teacher_id,)
    )[0]["n"]

    exercises = fetch(
        """
        SELECT COUNT(*) AS n
        FROM exercises
        WHERE teacher_id=?
        """,
        (teacher_id,)
    )[0]["n"]

    submissions = fetch(
        """
        SELECT COUNT(*) AS n
        FROM submissions s
        JOIN exercises e
        ON e.id=s.exercise_id
        WHERE e.teacher_id=?
        """,
        (teacher_id,)
    )[0]["n"]

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

    st.divider()

    st.subheader(
        "Tiến độ học sinh"
    )

    students_data = fetch(
        """
        SELECT *
        FROM users
        WHERE role='student'
        AND class_code IN (
            SELECT class_code
            FROM classes
            WHERE teacher_id=?
        )
        ORDER BY full_name
        """,
        (teacher_id,)
    )

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

            "Mã lớp":
                student["class_code"],

            "Bài giảng":
                f"{p['viewed_lessons']}/{p['total_lessons']}",

            "Bài tập":
                f"{p['completed_exercises']}/{p['total_exercises']}",

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
            "Chưa có học sinh tham gia lớp."
        )


# ============================================================
# CLASS MANAGEMENT
# ============================================================

def teacher_classes():

    teacher_id = st.session_state.user["id"]

    st.title("Quản lý lớp")

    st.write(
        "Tạo mã lớp để học sinh dùng khi đăng ký tài khoản."
    )

    st.subheader(
        "Tạo mã lớp mới"
    )

    with st.form(
        "create_class_form"
    ):

        class_name = st.text_input(
            "Tên lớp",
            placeholder="Ví dụ: English A1 - Kỳ 1"
        )

        class_code = st.text_input(
            "Mã lớp",
            placeholder="Ví dụ: ENGLISH-A1-01"
        )

        create = st.form_submit_button(
            "Tạo lớp",
            use_container_width=True
        )

    if create:

        class_name = class_name.strip()
        class_code = class_code.strip().upper()

        if not class_name:

            st.error(
                "Vui lòng nhập tên lớp."
            )

        elif not class_code:

            st.error(
                "Vui lòng nhập mã lớp."
            )

        else:

            try:

                execute(
                    """
                    INSERT INTO classes
                    (
                        teacher_id,
                        class_name,
                        class_code,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        teacher_id,
                        class_name,
                        class_code,
                        now()
                    )
                )

                st.success(
                    f"Đã tạo lớp {class_name}."
                )

                st.rerun()

            except sqlite3.IntegrityError:

                st.error(
                    "Mã lớp này đã tồn tại."
                )

    st.divider()

    st.subheader(
        "Các lớp của bạn"
    )

    classes = fetch(
        """
        SELECT *
        FROM classes
        WHERE teacher_id=?
        ORDER BY created_at DESC
        """,
        (teacher_id,)
    )

    if not classes:

        st.info(
            "Bạn chưa tạo lớp nào."
        )

        return

    for classroom in classes:

        student_count = fetch(
            """
            SELECT COUNT(*) AS n
            FROM users
            WHERE role='student'
            AND class_code=?
            """,
            (classroom["class_code"],)
        )[0]["n"]

        with st.container(border=True):

            st.subheader(
                classroom["class_name"]
            )

            st.code(
                classroom["class_code"],
                language=None
            )

            st.write(
                f"Số học sinh: {student_count}"
            )

            st.caption(
                f"Tạo lúc: {classroom['created_at']}"
            )


# ============================================================

# TEACHER LESSONS

# ============================================================

def teacher_lessons():

    teacher_id = st.session_state.user["id"]

    st.title("Bài giảng")

    lessons = fetch(
        """
        SELECT
            l.*,
            COUNT(v.id) AS viewed_count
        FROM lessons l
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

        with st.container(border=True):

            st.subheader(
                lesson["title"]
            )

            st.caption(
                f"{lesson['level']} | "
                f"{lesson['category']}"
            )

            if lesson["description"]:

                st.write(
                    lesson["description"]
                )

            st.write(
                f"Học sinh đã xem: "
                f"{lesson['viewed_count']}"
            )

            if lesson["video_path"]:

                video_file = Path(
                    lesson["video_path"]
                )

                if video_file.exists():

                    with open(
                        video_file,
                        "rb"
                    ) as file:

                        st.video(
                            file.read()
                        )

                else:

                    st.warning(
                        "Không tìm thấy file video."
                    )

                st.caption(
                    "Video: "
                    +
                    str(
                        lesson["video_name"]
                        or "Video"
                    )
                )

            with st.expander(
                "Xem nội dung bài giảng"
            ):

                st.markdown(
                    lesson["content"] or ""
                )

                if lesson["resource_url"]:

                    st.link_button(
                        "Mở tài liệu bên ngoài",
                        lesson["resource_url"]
                    )

            st.divider()

            edit_col, delete_col = st.columns(2)

            # ====================================================
            # EDIT LESSON
            # ====================================================

            with edit_col:

                with st.expander(
                    "Chỉnh sửa bài giảng"
                ):

                    with st.form(
                        f"edit_lesson_{lesson['id']}"
                    ):

                        new_title = st.text_input(
                            "Tên bài giảng",
                            value=lesson["title"],
                            key=f"title_{lesson['id']}"
                        )

                        new_description = st.text_area(
                            "Mô tả ngắn",
                            value=lesson["description"] or "",
                            key=f"description_{lesson['id']}"
                        )

                        col1, col2 = st.columns(2)

                        with col1:

                            levels = [
                                "A1",
                                "A2",
                                "B1",
                                "B2",
                                "C1",
                                "C2"
                            ]

                            current_level = (
                                lesson["level"]
                                if lesson["level"] in levels
                                else "A1"
                            )

                            new_level = st.selectbox(
                                "Trình độ CEFR",
                                levels,
                                index=levels.index(
                                    current_level
                                ),
                                key=f"level_{lesson['id']}"
                            )

                        with col2:

                            categories = [
                                "Ngữ pháp",
                                "Từ vựng",
                                "Đọc",
                                "Nghe",
                                "Nói",
                                "Viết",
                                "Luyện thi",
                                "Tiếng Anh tổng quát"
                            ]

                            current_category = (
                                lesson["category"]
                                if lesson["category"] in categories
                                else "Ngữ pháp"
                            )

                            new_category = st.selectbox(
                                "Chủ đề",
                                categories,
                                index=categories.index(
                                    current_category
                                ),
                                key=f"category_{lesson['id']}"
                            )

                        new_content = st.text_area(
                            "Nội dung bài giảng",
                            value=lesson["content"] or "",
                            height=350,
                            key=f"content_{lesson['id']}"
                        )

                        new_resource_url = st.text_input(
                            "Đường dẫn tài liệu bên ngoài",
                            value=lesson["resource_url"] or "",
                            key=f"url_{lesson['id']}"
                        )

                        new_video = st.file_uploader(
                            "Thay video mới (không bắt buộc)",
                            type=[
                                "mp4",
                                "mov",
                                "webm",
                                "m4v"
                            ],
                            key=f"video_{lesson['id']}"
                        )

                        update_lesson = st.form_submit_button(
                            "Lưu thay đổi",
                            use_container_width=True
                        )

                    if update_lesson:

                        if not new_title.strip():

                            st.error(
                                "Tên bài giảng không được để trống."
                            )

                        else:

                            video_path = lesson["video_path"]
                            video_name = lesson["video_name"]

                            # Nếu giáo viên upload video mới
                            if new_video:

                                # Xóa video cũ nếu có
                                if video_path:

                                    old_video = Path(
                                        video_path
                                    )

                                    if old_video.exists():

                                        try:

                                            old_video.unlink()

                                        except Exception:

                                            pass

                                extension = Path(
                                    new_video.name
                                ).suffix.lower()

                                unique_name = (
                                    str(uuid.uuid4())
                                    +
                                    extension
                                )

                                save_path = (
                                    VIDEO_DIR
                                    /
                                    unique_name
                                )

                                with open(
                                    save_path,
                                    "wb"
                                ) as file:

                                    file.write(
                                        new_video.getbuffer()
                                    )

                                video_path = str(
                                    save_path
                                )

                                video_name = (
                                    new_video.name
                                )

                            execute(
                                """
                                UPDATE lessons
                                SET
                                    title=?,
                                    description=?,
                                    level=?,
                                    category=?,
                                    content=?,
                                    resource_url=?,
                                    video_path=?,
                                    video_name=?
                                WHERE id=?
                                AND teacher_id=?
                                """,
                                (
                                    new_title.strip(),
                                    new_description.strip(),
                                    new_level,
                                    new_category,
                                    new_content,
                                    new_resource_url.strip(),
                                    video_path,
                                    video_name,
                                    lesson["id"],
                                    teacher_id
                                )
                            )

                            st.success(
                                "Đã cập nhật bài giảng thành công."
                            )

                            st.rerun()

            # ====================================================
            # DELETE LESSON
            # ====================================================

            with delete_col:

                with st.expander(
                    "Xóa bài giảng"
                ):

                    st.warning(
                        "Thao tác này không thể hoàn tác."
                    )

                    confirm_delete = st.checkbox(
                        "Tôi xác nhận muốn xóa bài giảng này",
                        key=f"confirm_delete_{lesson['id']}"
                    )

                    if st.button(
                        "Xóa bài giảng vĩnh viễn",
                        key=f"delete_lesson_{lesson['id']}",
                        use_container_width=True,
                        disabled=not confirm_delete
                    ):

                        # Xóa file video khỏi server
                        if lesson["video_path"]:

                            video_file = Path(
                                lesson["video_path"]
                            )

                            if video_file.exists():

                                try:

                                    video_file.unlink()

                                except Exception:

                                    pass

                        # Xóa các lượt xem liên quan
                        execute(
                            """
                            DELETE FROM lesson_views
                            WHERE lesson_id=?
                            """,
                            (lesson["id"],)
                        )

                        # Bỏ liên kết bài tập với bài giảng này
                        execute(
                            """
                            UPDATE exercises
                            SET lesson_id=NULL
                            WHERE lesson_id=?
                            """,
                            (lesson["id"],)
                        )

                        # Xóa bài giảng
                        execute(
                            """
                            DELETE FROM lessons
                            WHERE id=?
                            AND teacher_id=?
                            """,
                            (
                                lesson["id"],
                                teacher_id
                            )
                        )

                        st.success(
                            "Đã xóa bài giảng thành công."
                        )

                        st.rerun()


# ============================================================
# CREATE LESSON
# ============================================================

def create_lesson():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Tạo bài giảng"
    )

    st.write(
        "Bạn có thể đăng nội dung và upload video trực tiếp từ máy tính."
    )

    with st.form(
        "create_lesson_form"
    ):

        title = st.text_input(
            "Tên bài giảng"
        )

        description = st.text_area(
            "Mô tả ngắn"
        )

        a, b = st.columns(2)

        with a:

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

        with b:

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
            height=350,
            placeholder=(
                "Ví dụ:\n\n"
                "# Present Perfect\n\n"
                "## Công thức\n\n"
                "Subject + have/has + V3\n\n"
                "## Ví dụ\n\n"
                "I have studied English for three years."
            )
        )

        resource_url = st.text_input(
            "Đường dẫn tài liệu bên ngoài (nếu có)"
        )

        video = st.file_uploader(
            "Upload video bài giảng",
            type=[
                "mp4",
                "mov",
                "webm",
                "m4v"
            ],
            help=(
                "Chọn video từ máy tính. "
                "Video sẽ được lưu vào thư mục uploaded_videos."
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

        if not content.strip() and not video:

            st.error(
                "Hãy nhập nội dung hoặc upload video."
            )

            return

        video_path = None
        video_name = None

        if video:

            extension = Path(
                video.name
            ).suffix.lower()

            unique_name = (
                str(uuid.uuid4())
                +
                extension
            )

            save_path = (
                VIDEO_DIR
                /
                unique_name
            )

            with open(
                save_path,
                "wb"
            ) as file:

                file.write(
                    video.getbuffer()
                )

            video_path = str(
                save_path
            )

            video_name = video.name

        execute(
            """
            INSERT INTO lessons
            (
                teacher_id,
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
            """,
            (
                teacher_id,
                title.strip(),
                description.strip(),
                level,
                category,
                content,
                resource_url.strip(),
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
# CREATE EXERCISE
# ============================================================

def create_exercise():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Tạo bài tập"
    )

    lessons = fetch(
        """
        SELECT id, title
        FROM lessons
        WHERE teacher_id=?
        ORDER BY title
        """,
        (teacher_id,)
    )

    lesson_dict = {
        "Không liên kết bài giảng": None
    }

    for lesson in lessons:

        lesson_dict[
            lesson["title"]
        ] = lesson["id"]

    with st.form(
        "create_exercise_form"
    ):

        title = st.text_input(
            "Tên bài tập"
        )

        linked = st.selectbox(
            "Bài giảng liên quan",
            list(
                lesson_dict.keys()
            )
        )

        instructions = st.text_area(
            "Hướng dẫn làm bài"
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
                "Tên bài tập là bắt buộc."
            )

            return

        if not questions.strip():

            st.error(
                "Nội dung câu hỏi là bắt buộc."
            )

            return

        execute(
            """
            INSERT INTO exercises
            (
                teacher_id,
                title,
                lesson_id,
                instructions,
                questions,
                max_score,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                teacher_id,
                title.strip(),
                lesson_dict[linked],
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
# TEACHER EXERCISES / GRADING
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
            u.username AS student_username,
            e.title AS exercise_title,
            e.max_score
        FROM submissions s
        JOIN users u
        ON u.id=s.student_id
        JOIN exercises e
        ON e.id=s.exercise_id
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

        with st.container(border=True):

            st.subheader(
                f"{submission['student_name']} — "
                f"{submission['exercise_title']}"
            )

            st.caption(
                submission["submitted_at"]
            )

            st.write(
                "Bài làm của học sinh:"
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
                        or
                        ""
                    )
                )

                save = st.form_submit_button(
                    "Lưu điểm và nhận xét",
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
                    "Đã lưu."
                )

                st.rerun()


# ============================================================
# TEACHER STUDENTS
# ============================================================

def teacher_students():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Học sinh"
    )

    students = fetch(
        """
        SELECT *
        FROM users
        WHERE role='student'
        AND class_code IN (
            SELECT class_code
            FROM classes
            WHERE teacher_id=?
        )
        ORDER BY full_name
        """,
        (teacher_id,)
    )

    if not students:

        st.info(
            "Chưa có học sinh nào tham gia lớp."
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
        s for s in students
        if s["full_name"]
        ==
        selected_name
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
        f"Mã lớp: {student['class_code']}"
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
            v.first_viewed AS "Lần xem đầu",
            v.last_viewed AS "Lần xem gần nhất",
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
                [
                    dict(v)
                    for v in views
                ]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Học sinh chưa xem bài giảng nào."
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
        AND e.teacher_id=?
        ORDER BY s.submitted_at DESC
        """,
        (
            student["id"],
            teacher_id
        )
    )

    if results:

        st.dataframe(
            pd.DataFrame(
                [
                    dict(r)
                    for r in results
                ]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Học sinh chưa nộp bài."
        )


# ============================================================
# TEACHER LESSON VIEWS
# ============================================================

def teacher_lesson_views():

    teacher_id = st.session_state.user["id"]

    st.title(
        "Lượt xem bài giảng"
    )

    lessons = fetch(
        """
        SELECT id, title
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
            x["title"]
    )

    rows = fetch(
        """
        SELECT
            u.full_name AS "Họ và tên",
            u.username AS "Tên đăng nhập",
            u.class_code AS "Mã lớp",
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

    st.subheader(
        selected["title"]
    )

    if rows:

        st.dataframe(
            pd.DataFrame(
                [
                    dict(r)
                    for r in rows
                ]
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

    st.title(
        "Hoạt động học tập"
    )

    rows = fetch(
        """
        SELECT
            a.created_at AS "Thời gian",
            u.full_name AS "Học sinh",
            u.class_code AS "Mã lớp",
            a.action AS "Hoạt động",
            a.object_name AS "Nội dung"
        FROM activity a
        LEFT JOIN users u
        ON u.id=a.student_id
        WHERE u.class_code IN (
            SELECT class_code
            FROM classes
            WHERE teacher_id=?
        )
        ORDER BY a.created_at DESC
        LIMIT 500
        """,
        (teacher_id,)
    )

    if rows:

        st.dataframe(
            pd.DataFrame(
                [
                    dict(r)
                    for r in rows
                ]
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Chưa có hoạt động."
        )


# ============================================================
# STUDENT SIDEBAR
# ============================================================

def student_sidebar():

    with st.sidebar:

        st.title(
            "EnglishHub LMS"
        )

        st.caption(
            "Học sinh: "
            +
            st.session_state.user[
                "full_name"
            ]
        )

        st.caption(
            "Mã lớp: "
            +
            str(
                st.session_state.user[
                    "class_code"
                ]
            )
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
# STUDENT DASHBOARD
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
        "Chào mừng bạn quay lại EnglishHub."
    )

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

    st.progress(
        p["participation"] / 100
    )

    st.divider()

    st.subheader(
        "Bài giảng mới nhất"
    )

    lessons = fetch(
        """
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
        WHERE l.teacher_id IN (
            SELECT teacher_id
            FROM classes
            WHERE class_code=?
        )
        ORDER BY l.created_at DESC
        LIMIT 8
        """,
        (
            user["id"],
            user["class_code"]
        )
    )

    if not lessons:

        st.info(
            "Giáo viên chưa đăng bài giảng nào."
        )

        return

    for lesson in lessons:

        with st.container(border=True):

            st.subheader(
                lesson["title"]
            )

            st.caption(
                f"{lesson['level']} | "
                f"{lesson['category']}"
            )

            if lesson["description"]:

                st.write(
                    lesson["description"]
                )

            if lesson["viewed"]:

                st.success(
                    "Bạn đã xem bài này."
                )

            else:

                st.warning(
                    "Bạn chưa xem bài này."
                )

            if st.button(
                "Mở bài giảng",
                key=(
                    f"dashboard_lesson_"
                    f"{lesson['id']}"
                )
            ):

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

    st.title(
        "Bài giảng"
    )

    lessons = fetch(
        """
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
        WHERE l.teacher_id IN (
            SELECT teacher_id
            FROM classes
            WHERE class_code=?
        )
        ORDER BY l.created_at DESC
        """,
        (
            user["id"],
            user["class_code"]
        )
    )

    if not lessons:

        st.info(
            "Chưa có bài giảng."
        )

        return

    for lesson in lessons:

        with st.container(border=True):

            st.subheader(
                lesson["title"]
            )

            st.caption(
                f"{lesson['level']} | "
                f"{lesson['category']}"
            )

            st.write(
                lesson["description"]
                or
                ""
            )

            if lesson["viewed"]:

                st.success(
                    "Đã xem"
                )

            else:

                st.warning(
                    "Chưa xem"
                )

            if st.button(
                "Mở bài giảng",
                key=(
                    f"student_lesson_"
                    f"{lesson['id']}"
                )
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
        (lesson_id,)
    )

    if not rows:

        st.session_state.open_lesson = None

        st.error(
            "Không tìm thấy bài giảng."
        )

        return

    lesson = rows[0]

    # Ghi nhận lượt xem
    record_lesson_view(
        lesson["id"],
        user["id"],
        lesson["title"]
    )

    st.title(
        lesson["title"]
    )

    st.caption(
        f"{lesson['level']} | "
        f"{lesson['category']}"
    )

    if lesson["description"]:

        st.write(
            lesson["description"]
        )

    st.divider()

    # VIDEO
    if lesson["video_path"]:

        video_file = Path(
            lesson["video_path"]
        )

        if video_file.exists():

            st.subheader(
                "Video bài giảng"
            )

            with open(
                video_file,
                "rb"
            ) as file:

                video_bytes = file.read()

            st.video(
                video_bytes
            )

        else:

            st.warning(
                "Không tìm thấy file video trên máy chủ."
            )

    # CONTENT
    if lesson["content"]:

        st.subheader(
            "Nội dung bài giảng"
        )

        st.markdown(
            lesson["content"]
        )

    # EXTERNAL RESOURCE
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

    st.title(
        "Bài tập"
    )

    exercises = fetch(
        """
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
        WHERE e.teacher_id IN (
            SELECT teacher_id
            FROM classes
            WHERE class_code=?
        )
        ORDER BY e.created_at DESC
        """,
        (
            user["id"],
            user["class_code"]
        )
    )

    if not exercises:

        st.info(
            "Chưa có bài tập."
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

            if exercise["lesson_title"]:

                st.caption(
                    "Bài giảng: "
                    +
                    exercise["lesson_title"]
                )

            if exercise["instructions"]:

                st.write(
                    exercise["instructions"]
                )

            st.subheader(
                "Yêu cầu bài tập"
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
                        or
                        ""
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
                    "Đã nộp bài thành công."
                )

                st.rerun()

            if exercise["feedback"]:

                st.success(
                    "Nhận xét giáo viên: "
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

    st.title(
        "Tiến độ học tập"
    )

    st.write(
        user["full_name"]
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

    st.divider()

    st.subheader(
        "Lịch sử học bài"
    )

    views = fetch(
        """
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
        """,
        (user["id"],)
    )

    if views:

        st.dataframe(
            pd.DataFrame(
                [
                    dict(v)
                    for v in views
                ]
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
            s.feedback AS "Nhận xét giáo viên",
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
                [
                    dict(r)
                    for r in results
                ]
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

        elif page == "Quản lý lớp":

            teacher_classes()

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
