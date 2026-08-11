
import streamlit as st
import sqlite3
import hashlib
import hmac
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

# ============================================================
# CẤU HÌNH
# ============================================================

st.set_page_config(
    page_title="EnglishHub LMS",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "englishhub.db"
VIDEO_DIR = BASE_DIR / "uploaded_videos"

VIDEO_DIR.mkdir(exist_ok=True)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}

.block-container {
    max-width: 1400px;
    padding-top: 2rem;
}

.hero {
    background: linear-gradient(
        135deg,
        #102A43 0%,
        #1D4ED8 100%
    );
    padding: 45px;
    border-radius: 24px;
    color: white;
    margin-bottom: 30px;
}

.hero h1 {
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 10px;
}

.hero p {
    font-size: 18px;
    opacity: 0.95;
}

.card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 24px;
    margin-bottom: 18px;
}

.section-title {
    font-size: 28px;
    font-weight: 800;
    color: #102A43;
    margin-bottom: 20px;
}

.student-name {
    font-size: 20px;
    font-weight: 700;
    color: #102A43;
}

.small-text {
    color: #667085;
    font-size: 14px;
}

.badge {
    display: inline-block;
    background: #E8F0FE;
    color: #1D4ED8;
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 10px;
}

.metric-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 18px;
    padding: 22px;
    text-align: center;
}

.metric-number {
    font-size: 32px;
    font-weight: 800;
    color: #1D4ED8;
}

.metric-label {
    color: #667085;
    margin-top: 5px;
}

.login-box {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 20px;
    padding: 30px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_database():

    conn = get_connection()

    conn.executescript("""

    CREATE TABLE IF NOT EXISTS users (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        full_name TEXT NOT NULL,

        username TEXT UNIQUE NOT NULL,

        password_hash TEXT NOT NULL,

        role TEXT NOT NULL,

        created_at TEXT NOT NULL

    );


    CREATE TABLE IF NOT EXISTS lessons (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        title TEXT NOT NULL,

        description TEXT,

        level TEXT,

        category TEXT,

        content TEXT,

        video_path TEXT,

        video_name TEXT,

        resource_url TEXT,

        created_at TEXT NOT NULL

    );


    CREATE TABLE IF NOT EXISTS lesson_views (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        lesson_id INTEGER NOT NULL,

        student_id INTEGER NOT NULL,

        view_count INTEGER DEFAULT 1,

        first_viewed TEXT NOT NULL,

        last_viewed TEXT NOT NULL,

        UNIQUE(lesson_id, student_id)

    );


    CREATE TABLE IF NOT EXISTS exercises (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

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


    CREATE TABLE IF NOT EXISTS activities (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        student_id INTEGER,

        action TEXT,

        object_name TEXT,

        created_at TEXT

    );

    """)

    conn.commit()
    conn.close()


init_database()


# ============================================================
# HELPER
# ============================================================

def current_time():

    return datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )


def execute_query(
    query,
    params=()
):

    conn = get_connection()

    cursor = conn.execute(
        query,
        params
    )

    conn.commit()

    result = cursor.lastrowid

    conn.close()

    return result


def fetch_all(
    query,
    params=()
):

    conn = get_connection()

    rows = conn.execute(
        query,
        params
    ).fetchall()

    conn.close()

    return rows


def hash_password(password):

    salt = os.urandom(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )

    return salt.hex() + ":" + key.hex()


def verify_password(
    password,
    stored_password
):

    try:

        salt, stored_key = stored_password.split(":")

        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            120000
        )

        return hmac.compare_digest(
            key.hex(),
            stored_key
        )

    except Exception:

        return False


def get_teacher_code():

    try:

        return st.secrets[
            "LMS_TEACHER_CODE"
        ]

    except Exception:

        return os.getenv(
            "LMS_TEACHER_CODE",
            "THAY-MA-GIAO-VIEN"
        )


def log_activity(
    student_id,
    action,
    object_name=""
):

    execute_query("""

        INSERT INTO activities
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
        current_time()

    ))


# ============================================================
# SESSION
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


# ============================================================
# ĐĂNG KÝ
# ============================================================

def create_account():

    st.markdown(
        "### Tạo tài khoản mới"
    )

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
        "Bạn là",
        [
            "Học sinh",
            "Giáo viên"
        ]
    )

    teacher_code = ""

    if role == "Giáo viên":

        teacher_code = st.text_input(
            "Mã truy cập giáo viên",
            type="password"
        )

        st.caption(
            "Mã này do giáo viên tự đặt."
        )


    if st.button(
        "Tạo tài khoản",
        use_container_width=True
    ):

        if not full_name:

            st.error(
                "Vui lòng nhập họ và tên."
            )

            return

        if not username:

            st.error(
                "Vui lòng nhập tên đăng nhập."
            )

            return

        if len(password) < 6:

            st.error(
                "Mật khẩu phải có ít nhất 6 ký tự."
            )

            return


        if role == "Giáo viên":

            if not hmac.compare_digest(
                teacher_code,
                get_teacher_code()
            ):

                st.error(
                    "Mã giáo viên không chính xác."
                )

                return


        role_db = (
            "teacher"
            if role == "Giáo viên"
            else "student"
        )


        try:

            execute_query("""

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

                full_name.strip(),

                username.strip().lower(),

                hash_password(password),

                role_db,

                current_time()

            ))

            st.success(
                "Tạo tài khoản thành công. Bạn có thể đăng nhập."
            )

        except sqlite3.IntegrityError:

            st.error(
                "Tên đăng nhập này đã tồn tại."
            )


# ============================================================
# ĐĂNG NHẬP
# ============================================================

def login_user(
    username,
    password,
    role
):

    rows = fetch_all("""

        SELECT *

        FROM users

        WHERE username = ?

        AND role = ?

    """, (

        username.strip().lower(),

        role

    ))


    if not rows:

        return None


    user = rows[0]


    if verify_password(
        password,
        user["password_hash"]
    ):

        return dict(user)


    return None


# ============================================================
# TRANG ĐĂNG NHẬP
# ============================================================

def login_page():

    st.markdown("""

    <div class="hero">

        <h1>EnglishHub LMS</h1>

        <p>Nền tảng học tiếng Anh dành cho lớp học của Tom và các bạn.</p>

    </div>

    """, unsafe_allow_html=True)


    left, right = st.columns(
        [1, 1],
        gap="large"
    )


    # ---------------- LOGIN ----------------

    with left:

        st.markdown(
            '<div class="login-box">',
            unsafe_allow_html=True
        )

        st.subheader(
            "Đăng nhập"
        )


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


        username = st.text_input(
            "Tên đăng nhập",
            key="login_username"
        )


        password = st.text_input(
            "Mật khẩu",
            type="password",
            key="login_password"
        )


        if st.button(
            "Đăng nhập",
            use_container_width=True
        ):

            user = login_user(
                username,
                password,
                role_db
            )


            if user:

                st.session_state.user = user

                st.rerun()

            else:

                st.error(
                    "Tên đăng nhập, mật khẩu hoặc loại tài khoản không đúng."
                )


        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


    # ---------------- REGISTER ----------------

    with right:

        st.markdown(
            '<div class="login-box">',
            unsafe_allow_html=True
        )

        create_account()

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


# ============================================================
# SIDEBAR GIÁO VIÊN
# ============================================================

def teacher_sidebar():

    user = st.session_state.user

    with st.sidebar:

        st.markdown(
            "## EnglishHub LMS"
        )

        st.caption(
            "Khu vực giáo viên"
        )

        st.divider()

        st.markdown(
            f"**{user['full_name']}**"
        )

        st.caption(
            "Giáo viên"
        )

        st.divider()


        page = st.radio(

            "QUẢN LÝ",

            [

                "Tổng quan",

                "Bài giảng",

                "Tạo bài giảng",

                "Học sinh",

                "Lượt xem bài giảng",

                "Bài tập",

                "Tạo bài tập",

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
# DASHBOARD GIÁO VIÊN
# ============================================================

def teacher_dashboard():

    st.markdown(
        '<div class="section-title">Tổng quan lớp học</div>',
        unsafe_allow_html=True
    )


    students = fetch_all("""

        SELECT COUNT(*) AS total

        FROM users

        WHERE role = 'student'

    """)[0]["total"]


    lessons = fetch_all("""

        SELECT COUNT(*) AS total

        FROM lessons

    """)[0]["total"]


    exercises = fetch_all("""

        SELECT COUNT(*) AS total

        FROM exercises

    """)[0]["total"]


    submissions = fetch_all("""

        SELECT COUNT(*) AS total

        FROM submissions

    """)[0]["total"]


    a, b, c, d = st.columns(4)


    with a:

        st.metric(
            "Học sinh",
            students
        )


    with b:

        st.metric(
            "Bài giảng",
            lessons
        )


    with c:

        st.metric(
            "Bài tập",
            exercises
        )


    with d:

        st.metric(
            "Bài đã nộp",
            submissions
        )


    st.divider()


    st.markdown(
        "### Học sinh trong lớp"
    )


    student_rows = fetch_all("""

        SELECT

            u.id,

            u.full_name,

            u.username,

            u.created_at

        FROM users u

        WHERE u.role = 'student'

        ORDER BY u.full_name

    """)


    if student_rows:

        data = []


        for student in student_rows:

            viewed = fetch_all("""

                SELECT COUNT(*) AS total

                FROM lesson_views

                WHERE student_id = ?

            """, (

                student["id"],

            ))[0]["total"]


            data.append({

                "Họ và tên":
                    student["full_name"],

                "Tên đăng nhập":
                    student["username"],

                "Bài giảng đã xem":
                    viewed,

                "Ngày tham gia":
                    student["created_at"]

            })


        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# TẠO BÀI GIẢNG
# ============================================================

def create_lesson():

    st.markdown(
        '<div class="section-title">Tạo bài giảng mới</div>',
        unsafe_allow_html=True
    )


    st.info(
        "Bạn có thể đăng nội dung bài học và tải video trực tiếp từ máy tính."
    )


    title = st.text_input(
        "Tên bài giảng *"
    )


    description = st.text_area(
        "Mô tả bài giảng"
    )


    col1, col2 = st.columns(2)


    with col1:

        level = st.selectbox(

            "Trình độ",

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

        placeholder=
        "Nhập nội dung bài giảng tại đây..."

    )


    st.markdown(
        "### Video bài giảng"
    )


    video = st.file_uploader(

        "Chọn video từ máy tính",

        type=[
            "mp4",
            "mov",
            "webm",
            "m4v"
        ]

    )


    if video:

        st.success(
            f"Đã chọn video: {video.name}"
        )

        st.caption(
            f"Dung lượng: {video.size / 1024 / 1024:.2f} MB"
        )


    resource_url = st.text_input(
        "Link tài liệu bổ sung (không bắt buộc)"
    )


    if st.button(
        "ĐĂNG BÀI GIẢNG",
        type="primary",
        use_container_width=True
    ):

        if not title:

            st.error(
                "Bạn chưa nhập tên bài giảng."
            )

            return


        video_path = None

        video_name = None


        if video:

            safe_name = (

                str(
                    int(
                        datetime.now().timestamp()
                    )
                )

                + "_"

                + video.name.replace(
                    " ",
                    "_"
                )

            )


            save_path = (
                VIDEO_DIR / safe_name
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


        execute_query("""

            INSERT INTO lessons

            (
                title,
                description,
                level,
                category,
                content,
                video_path,
                video_name,
                resource_url,
                created_at
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        """, (

            title,

            description,

            level,

            category,

            content,

            video_path,

            video_name,

            resource_url,

            current_time()

        ))


        st.success(
            "Đã đăng bài giảng thành công!"
        )

        st.rerun()


# ============================================================
# DANH SÁCH BÀI GIẢNG GIÁO VIÊN
# ============================================================

def teacher_lessons():

    st.markdown(
        '<div class="section-title">Quản lý bài giảng</div>',
        unsafe_allow_html=True
    )


    lessons = fetch_all("""

        SELECT *

        FROM lessons

        ORDER BY id DESC

    """)


    if not lessons:

        st.info(
            "Bạn chưa đăng bài giảng nào."
        )

        return


    for lesson in lessons:

        st.markdown(

            f"""

            <div class="card">

                <span class="badge">
                    {lesson["level"]}
                    ·
                    {lesson["category"]}
                </span>

                <div class="student-name">
                    {lesson["title"]}
                </div>

                <div class="small-text">
                    Đăng ngày: {lesson["created_at"]}
                </div>

            </div>

            """,

            unsafe_allow_html=True

        )


        with st.expander(
            "Xem bài giảng"
        ):

            if lesson["video_path"]:

                video_path = Path(
                    lesson["video_path"]
                )


                if video_path.exists():

                    st.video(
                        str(video_path)
                    )


            st.markdown(
                lesson["content"] or ""
            )


# ============================================================
# DANH SÁCH HỌC SINH
# ============================================================

def teacher_students():

    st.markdown(
        '<div class="section-title">Danh sách học sinh</div>',
        unsafe_allow_html=True
    )


    students = fetch_all("""

        SELECT *

        FROM users

        WHERE role = 'student'

        ORDER BY full_name

    """)


    if not students:

        st.info(
            "Chưa có học sinh đăng ký."
        )

        return


    for student in students:

        viewed = fetch_all("""

            SELECT COUNT(*)

            AS total

            FROM lesson_views

            WHERE student_id = ?

        """, (

            student["id"],

        ))[0]["total"]


        submitted = fetch_all("""

            SELECT COUNT(*)

            AS total

            FROM submissions

            WHERE student_id = ?

        """, (

            student["id"],

        ))[0]["total"]


        st.markdown(

            f"""

            <div class="card">

                <div class="student-name">
                    {student["full_name"]}
                </div>

                <div class="small-text">
                    Tài khoản: {student["username"]}
                </div>

                <br>

                <b>Bài giảng đã xem:</b>
                {viewed}

                &nbsp;&nbsp;&nbsp;

                <b>Bài tập đã nộp:</b>
                {submitted}

            </div>

            """,

            unsafe_allow_html=True

        )


# ============================================================
# LƯỢT XEM
# ============================================================

def teacher_views():

    st.markdown(
        '<div class="section-title">Lượt xem bài giảng</div>',
        unsafe_allow_html=True
    )


    rows = fetch_all("""

        SELECT

            l.title AS "Bài giảng",

            u.full_name AS "Học sinh",

            v.view_count AS "Lượt xem",

            v.first_viewed AS "Xem lần đầu",

            v.last_viewed AS "Xem gần nhất"

        FROM lesson_views v

        JOIN lessons l

        ON l.id = v.lesson_id

        JOIN users u

        ON u.id = v.student_id

        ORDER BY v.last_viewed DESC

    """)


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
            "Chưa có dữ liệu lượt xem."
        )


# ============================================================
# SIDEBAR HỌC SINH
# ============================================================

def student_sidebar():

    user = st.session_state.user

    with st.sidebar:

        st.markdown(
            "## EnglishHub LMS"
        )

        st.caption(
            "Khu vực học sinh"
        )

        st.divider()

        st.markdown(
            f"**{user['full_name']}**"
        )

        st.caption(
            "Học sinh"
        )

        st.divider()


        page = st.radio(

            "HỌC TẬP",

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
# GHI NHẬN LƯỢT XEM
# ============================================================

def record_lesson_view(
    lesson_id,
    student_id,
    title
):

    existing = fetch_all("""

        SELECT *

        FROM lesson_views

        WHERE lesson_id = ?

        AND student_id = ?

    """, (

        lesson_id,

        student_id

    ))


    if existing:

        execute_query("""

            UPDATE lesson_views

            SET

                view_count =
                    view_count + 1,

                last_viewed = ?

            WHERE lesson_id = ?

            AND student_id = ?

        """, (

            current_time(),

            lesson_id,

            student_id

        ))

    else:

        execute_query("""

            INSERT INTO lesson_views

            (
                lesson_id,
                student_id,
                view_count,
                first_viewed,
                last_viewed
            )

            VALUES (?, ?, 1, ?, ?)

        """, (

            lesson_id,

            student_id,

            current_time(),

            current_time()

        ))


    log_activity(

        student_id,

        "Xem bài giảng",

        title

    )


# ============================================================
# BÀI GIẢNG HỌC SINH
# ============================================================

def student_lessons():

    user = st.session_state.user


    st.markdown(
        '<div class="section-title">Bài giảng</div>',
        unsafe_allow_html=True
    )


    lessons = fetch_all("""

        SELECT *

        FROM lessons

        ORDER BY id DESC

    """)


    if not lessons:

        st.info(
            "Hiện chưa có bài giảng."
        )

        return


    for lesson in lessons:

        with st.expander(
            lesson["title"]
        ):

            st.markdown(

                f"""

                <span class="badge">
                    {lesson["level"]}
                    ·
                    {lesson["category"]}
                </span>

                """,

                unsafe_allow_html=True

            )


            if lesson["description"]:

                st.write(
                    lesson["description"]
                )


            if lesson["video_path"]:

                video_path = Path(
                    lesson["video_path"]
                )


                if video_path.exists():

                    st.video(
                        str(video_path)
                    )

                    record_lesson_view(

                        lesson["id"],

                        user["id"],

                        lesson["title"]

                    )

                else:

                    st.warning(
                        "Video hiện không khả dụng."
                    )


            st.markdown(
                lesson["content"] or ""
            )


            if lesson["resource_url"]:

                st.link_button(

                    "Mở tài liệu",

                    lesson["resource_url"]

                )


# ============================================================
# TRANG CHỦ HỌC SINH
# ============================================================

def student_home():

    user = st.session_state.user


    st.markdown(

        f"""

        <div class="hero">

            <h1>
                Xin chào, {user["full_name"]}!
            </h1>

            <p>
                Chào mừng bạn trở lại EnglishHub LMS.
            </p>

        </div>

        """,

        unsafe_allow_html=True

    )


    total_lessons = fetch_all("""

        SELECT COUNT(*)

        AS total

        FROM lessons

    """)[0]["total"]


    viewed_lessons = fetch_all("""

        SELECT COUNT(*)

        AS total

        FROM lesson_views

        WHERE student_id = ?

    """, (

        user["id"],

    ))[0]["total"]


    total_exercises = fetch_all("""

        SELECT COUNT(*)

        AS total

        FROM exercises

    """)[0]["total"]


    submitted = fetch_all("""

        SELECT COUNT(*)

        AS total

        FROM submissions

        WHERE student_id = ?

    """, (

        user["id"],

    ))[0]["total"]


    a, b, c, d = st.columns(4)


    with a:

        st.metric(
            "Tổng bài giảng",
            total_lessons
        )


    with b:

        st.metric(
            "Đã xem",
            viewed_lessons
        )


    with c:

        st.metric(
            "Tổng bài tập",
            total_exercises
        )


    with d:

        st.metric(
            "Đã nộp",
            submitted
        )


# ============================================================
# TIẾN ĐỘ HỌC SINH
# ============================================================

def student_progress():

    user = st.session_state.user


    st.markdown(
        '<div class="section-title">Tiến độ học tập</div>',
        unsafe_allow_html=True
    )


    total_lessons = fetch_all("""

        SELECT COUNT(*)

        AS total

        FROM lessons

    """)[0]["total"]


    viewed = fetch_all("""

        SELECT COUNT(*)

        AS total

        FROM lesson_views

        WHERE student_id = ?

    """, (

        user["id"],

    ))[0]["total"]


    if total_lessons > 0:

        progress = viewed / total_lessons

    else:

        progress = 0


    st.progress(
        progress
    )


    st.write(

        f"Bạn đã hoàn thành "
        f"**{viewed}/{total_lessons}** "
        f"bài giảng."

    )


    views = fetch_all("""

        SELECT

            l.title,

            v.view_count,

            v.last_viewed

        FROM lesson_views v

        JOIN lessons l

        ON l.id = v.lesson_id

        WHERE v.student_id = ?

        ORDER BY v.last_viewed DESC

    """, (

        user["id"],

    ))


    if views:

        data = []


        for row in views:

            data.append({

                "Bài giảng":
                    row["title"],

                "Lượt xem":
                    row["view_count"],

                "Xem gần nhất":
                    row["last_viewed"]

            })


        st.dataframe(

            pd.DataFrame(data),

            use_container_width=True,

            hide_index=True

        )


# ============================================================
# MAIN APP
# ============================================================

if st.session_state.user is None:

    login_page()


else:

    user = st.session_state.user


    # ========================================================
    # GIÁO VIÊN
    # ========================================================

    if user["role"] == "teacher":

        page = teacher_sidebar()


        if page == "Tổng quan":

            teacher_dashboard()


        elif page == "Bài giảng":

            teacher_lessons()


        elif page == "Tạo bài giảng":

            create_lesson()


        elif page == "Học sinh":

            teacher_students()


        elif page == "Lượt xem bài giảng":

            teacher_views()


        elif page == "Bài tập":

            st.markdown(
                '<div class="section-title">Bài tập</div>',
                unsafe_allow_html=True
            )

            st.info(
                "Khu vực quản lý bài tập."
            )


        elif page == "Tạo bài tập":

            st.markdown(
                '<div class="section-title">Tạo bài tập</div>',
                unsafe_allow_html=True
            )

            st.info(
                "Khu vực tạo bài tập sẽ được phát triển tiếp."
            )


        elif page == "Hoạt động học tập":

            st.markdown(
                '<div class="section-title">Hoạt động học tập</div>',
                unsafe_allow_html=True
            )

            activities = fetch_all("""

                SELECT

                    u.full_name,

                    a.action,

                    a.object_name,

                    a.created_at

                FROM activities a

                LEFT JOIN users u

                ON u.id = a.student_id

                ORDER BY a.id DESC

            """)


            if activities:

                st.dataframe(

                    pd.DataFrame(
                        [dict(x) for x in activities]
                    ),

                    use_container_width=True,

                    hide_index=True

                )

            else:

                st.info(
                    "Chưa có hoạt động."
                )


    # ========================================================
    # HỌC SINH
    # ========================================================

    else:

        page = student_sidebar()


        if page == "Trang chủ":

            student_home()


        elif page == "Bài giảng":

            student_lessons()


        elif page == "Bài tập":

            st.markdown(
                '<div class="section-title">Bài tập</div>',
                unsafe_allow_html=True
            )

            st.info(
                "Các bài tập của giáo viên sẽ xuất hiện tại đây."
            )


        elif page == "Tiến độ học tập":

            student_progress()
```
