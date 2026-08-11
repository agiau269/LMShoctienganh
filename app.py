
import streamlit as st
import sqlite3
import hashlib
import hmac
import os
from pathlib import Path
from datetime import datetime
import pandas as pd


# ============================================================
# CẤU HÌNH ỨNG DỤNG
# ============================================================

st.set_page_config(
    page_title="EnglishHub LMS",
    page_icon="📚",
    layout="wide"
)


BASE_DIR = Path(__file__).parent

DB_FILE = BASE_DIR / "englishhub.db"

UPLOAD_DIR = BASE_DIR / "uploads"

VIDEO_DIR = UPLOAD_DIR / "videos"

DOCUMENT_DIR = UPLOAD_DIR / "documents"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# MÃ GIÁO VIÊN
# ============================================================

TEACHER_CODE = os.environ.get(
    "LMS_TEACHER_CODE",
    "TOM2026"
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
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
        padding-top: 30px;
    }

    .hero {
        padding: 45px;
        border-radius: 24px;
        background: linear-gradient(
            135deg,
            #102A43,
            #2563EB
        );
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
        margin-bottom: 0;
    }

    .section-title {
        font-size: 30px;
        font-weight: 800;
        color: #102A43;
        margin-bottom: 25px;
    }

    .card {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 18px;
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

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():

    connection = get_connection()

    connection.executescript(
        """

        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            full_name TEXT NOT NULL,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

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

            video_file TEXT,

            video_name TEXT,

            document_file TEXT,

            document_name TEXT,

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


        CREATE TABLE IF NOT EXISTS activities (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id INTEGER,

            action TEXT,

            lesson_name TEXT,

            created_at TEXT

        );

        """
    )

    connection.commit()

    connection.close()


initialize_database()


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def run_query(
    query,
    parameters=()
):

    connection = get_connection()

    cursor = connection.execute(
        query,
        parameters
    )

    connection.commit()

    result = cursor.lastrowid

    connection.close()

    return result


def get_rows(
    query,
    parameters=()
):

    connection = get_connection()

    rows = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return rows


# ============================================================
# PASSWORD
# ============================================================

def create_password_hash(password):

    salt = os.urandom(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )

    return salt.hex() + ":" + key.hex()


def check_password(
    password,
    saved_password
):

    try:

        salt, saved_key = saved_password.split(":")

        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            120000
        )

        return hmac.compare_digest(
            key.hex(),
            saved_key
        )

    except Exception:

        return False


# ============================================================
# THỜI GIAN
# ============================================================

def get_time():

    return datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )


# ============================================================
# HOẠT ĐỘNG
# ============================================================

def save_activity(
    student_id,
    action,
    lesson_name
):

    run_query(
        """
        INSERT INTO activities
        (
            student_id,
            action,
            lesson_name,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            student_id,
            action,
            lesson_name,
            get_time()
        )
    )


# ============================================================
# SESSION
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


# ============================================================
# ĐĂNG KÝ
# ============================================================

def register_user():

    st.markdown(
        "### Tạo tài khoản"
    )

    full_name = st.text_input(
        "Họ và tên",
        key="register_name"
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
        "Bạn là",
        [
            "Học sinh",
            "Giáo viên"
        ],
        key="register_role"
    )


    teacher_code = ""

    if role == "Giáo viên":

        teacher_code = st.text_input(
            "Mã giáo viên",
            type="password",
            key="register_teacher_code"
        )


    if st.button(
        "Tạo tài khoản",
        use_container_width=True,
        key="register_button"
    ):

        if not full_name.strip():

            st.error(
                "Vui lòng nhập họ và tên."
            )

            return


        if not username.strip():

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
                TEACHER_CODE
            ):

                st.error(
                    "Mã giáo viên không đúng."
                )

                return


        role_database = (
            "teacher"
            if role == "Giáo viên"
            else "student"
        )


        try:

            run_query(
                """
                INSERT INTO users
                (
                    full_name,
                    username,
                    password,
                    role,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    full_name.strip(),
                    username.strip().lower(),
                    create_password_hash(password),
                    role_database,
                    get_time()
                )
            )


            st.success(
                "Tạo tài khoản thành công. Hãy đăng nhập."
            )


        except sqlite3.IntegrityError:

            st.error(
                "Tên đăng nhập đã tồn tại."
            )


# ============================================================
# ĐĂNG NHẬP
# ============================================================

def authenticate_user(
    username,
    password,
    role
):

    users = get_rows(
        """
        SELECT *
        FROM users
        WHERE username = ?
        AND role = ?
        """,
        (
            username.strip().lower(),
            role
        )
    )


    if not users:

        return None


    user = users[0]


    if check_password(
        password,
        user["password"]
    ):

        return dict(user)


    return None


# ============================================================
# TRANG ĐĂNG NHẬP
# ============================================================

def show_login_page():

    st.markdown(
        """
        <div class="hero">

            <h1>EnglishHub LMS</h1>

            <p>Nền tảng học tiếng Anh dành cho lớp học của Tom và các bạn.</p>

        </div>
        """,
        unsafe_allow_html=True
    )


    left, right = st.columns(
        2,
        gap="large"
    )


    # ---------------- ĐĂNG NHẬP ----------------

    with left:

        st.markdown(
            "## Đăng nhập"
        )


        role = st.radio(
            "Bạn là:",
            [
                "Học sinh",
                "Giáo viên"
            ],
            horizontal=True
        )


        role_database = (
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
            type="primary",
            use_container_width=True,
            key="login_button"
        ):

            user = authenticate_user(
                username,
                password,
                role_database
            )


            if user:

                st.session_state.user = user

                st.rerun()

            else:

                st.error(
                    "Tên đăng nhập hoặc mật khẩu không đúng."
                )


    # ---------------- ĐĂNG KÝ ----------------

    with right:

        register_user()


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
            "MENU",
            [
                "Tổng quan",
                "Tạo bài giảng",
                "Quản lý bài giảng",
                "Danh sách học sinh",
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
# DASHBOARD GIÁO VIÊN
# ============================================================

def teacher_dashboard():

    st.markdown(
        '<div class="section-title">Tổng quan lớp học</div>',
        unsafe_allow_html=True
    )


    student_count = get_rows(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE role = 'student'
        """
    )[0]["total"]


    lesson_count = get_rows(
        """
        SELECT COUNT(*) AS total
        FROM lessons
        """
    )[0]["total"]


    view_count = get_rows(
        """
        SELECT COALESCE(SUM(view_count), 0) AS total
        FROM lesson_views
        """
    )[0]["total"]


    activity_count = get_rows(
        """
        SELECT COUNT(*) AS total
        FROM activities
        """
    )[0]["total"]


    a, b, c, d = st.columns(4)


    a.metric(
        "Học sinh",
        student_count
    )


    b.metric(
        "Bài giảng",
        lesson_count
    )


    c.metric(
        "Tổng lượt xem",
        view_count
    )


    d.metric(
        "Hoạt động",
        activity_count
    )


    st.divider()


    st.markdown(
        "### Học sinh trong lớp"
    )


    students = get_rows(
        """
        SELECT id, full_name, username, created_at
        FROM users
        WHERE role = 'student'
        ORDER BY full_name
        """
    )


    if students:

        table = []


        for student in students:

            viewed = get_rows(
                """
                SELECT COUNT(*) AS total
                FROM lesson_views
                WHERE student_id = ?
                """,
                (student["id"],)
            )[0]["total"]


            total_views = get_rows(
                """
                SELECT COALESCE(SUM(view_count), 0) AS total
                FROM lesson_views
                WHERE student_id = ?
                """,
                (student["id"],)
            )[0]["total"]


            table.append(
                {
                    "Họ và tên":
                        student["full_name"],

                    "Tên đăng nhập":
                        student["username"],

                    "Bài giảng đã xem":
                        viewed,

                    "Tổng lượt xem":
                        total_views,

                    "Ngày tham gia":
                        student["created_at"]
                }
            )


        st.dataframe(
            pd.DataFrame(table),
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
        "Bạn có thể tải video và tài liệu trực tiếp từ máy tính."
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
        ],
        key="lesson_video"
    )


    if video:

        st.success(
            f"Đã chọn: {video.name}"
        )

        st.caption(
            f"Dung lượng: {video.size / 1024 / 1024:.2f} MB"
        )


    st.markdown(
        "### Tài liệu"
    )


    document = st.file_uploader(
        "Upload PDF hoặc tài liệu",
        type=[
            "pdf",
            "doc",
            "docx",
            "ppt",
            "pptx"
        ],
        key="lesson_document"
    )


    if document:

        st.success(
            f"Đã chọn tài liệu: {document.name}"
        )


    if st.button(
        "ĐĂNG BÀI GIẢNG",
        type="primary",
        use_container_width=True
    ):

        if not title.strip():

            st.error(
                "Bạn chưa nhập tên bài giảng."
            )

            return


        video_path = ""

        video_name = ""


        if video:

            timestamp = str(
                int(
                    datetime.now().timestamp()
                )
            )


            safe_name = (

                timestamp
                + "_"
                + video.name.replace(
                    " ",
                    "_"
                )

            )


            saved_video = (
                VIDEO_DIR / safe_name
            )


            with open(
                saved_video,
                "wb"
            ) as file:

                file.write(
                    video.getbuffer()
                )


            video_path = str(
                saved_video
            )

            video_name = video.name


        document_path = ""

        document_name = ""


        if document:

            timestamp = str(
                int(
                    datetime.now().timestamp()
                )
            )


            safe_name = (

                timestamp
                + "_"
                + document.name.replace(
                    " ",
                    "_"
                )

            )


            saved_document = (
                DOCUMENT_DIR / safe_name
            )


            with open(
                saved_document,
                "wb"
            ) as file:

                file.write(
                    document.getbuffer()
                )


            document_path = str(
                saved_document
            )

            document_name = document.name


        run_query(
            """
            INSERT INTO lessons
            (
                title,
                description,
                level,
                category,
                content,
                video_file,
                video_name,
                document_file,
                document_name,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                level,
                category,
                content,
                video_path,
                video_name,
                document_path,
                document_name,
                get_time()
            )
        )


        st.success(
            "Đã đăng bài giảng thành công!"
        )


        st.rerun()


# ============================================================
# QUẢN LÝ BÀI GIẢNG
# ============================================================

def manage_lessons():

    st.markdown(
        '<div class="section-title">Quản lý bài giảng</div>',
        unsafe_allow_html=True
    )


    lessons = get_rows(
        """
        SELECT *
        FROM lessons
        ORDER BY id DESC
        """
    )


    if not lessons:

        st.info(
            "Chưa có bài giảng."
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


            st.write(
                lesson["description"] or ""
            )


            if lesson["video_file"]:

                video_path = Path(
                    lesson["video_file"]
                )


                if video_path.exists():

                    st.video(
                        str(video_path)
                    )

                else:

                    st.warning(
                        "Không tìm thấy video."
                    )


            if lesson["document_file"]:

                document_path = Path(
                    lesson["document_file"]
                )


                if document_path.exists():

                    with open(
                        document_path,
                        "rb"
                    ) as file:

                        st.download_button(
                            "Tải tài liệu",
                            file,
                            file_name=
                            lesson["document_name"]
                        )


            if lesson["content"]:

                st.markdown(
                    lesson["content"]
                )


# ============================================================
# DANH SÁCH HỌC SINH
# ============================================================

def show_students():

    st.markdown(
        '<div class="section-title">Danh sách học sinh</div>',
        unsafe_allow_html=True
    )


    students = get_rows(
        """
        SELECT *
        FROM users
        WHERE role = 'student'
        ORDER BY full_name
        """
    )


    if not students:

        st.info(
            "Chưa có học sinh."
        )

        return


    for student in students:

        viewed = get_rows(
            """
            SELECT COUNT(*) AS total
            FROM lesson_views
            WHERE student_id = ?
            """,
            (student["id"],)
        )[0]["total"]


        total_views = get_rows(
            """
            SELECT COALESCE(SUM(view_count), 0) AS total
            FROM lesson_views
            WHERE student_id = ?
            """,
            (student["id"],)
        )[0]["total"]


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

                <b>Tổng lượt xem:</b>
                {total_views}

            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# LƯỢT XEM BÀI GIẢNG
# ============================================================

def show_lesson_views():

    st.markdown(
        '<div class="section-title">Lượt xem bài giảng</div>',
        unsafe_allow_html=True
    )


    views = get_rows(
        """
        SELECT

            lessons.title AS lesson,

            users.full_name AS student,

            lesson_views.view_count AS views,

            lesson_views.first_viewed AS first_view,

            lesson_views.last_viewed AS last_view

        FROM lesson_views

        JOIN lessons
        ON lessons.id = lesson_views.lesson_id

        JOIN users
        ON users.id = lesson_views.student_id

        ORDER BY lesson_views.last_viewed DESC
        """
    )


    if not views:

        st.info(
            "Chưa có dữ liệu lượt xem."
        )

        return


    data = []


    for row in views:

        data.append(
            {
                "Bài giảng":
                    row["lesson"],

                "Học sinh":
                    row["student"],

                "Lượt xem":
                    row["views"],

                "Xem lần đầu":
                    row["first_view"],

                "Xem gần nhất":
                    row["last_view"]
            }
        )


    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# HOẠT ĐỘNG
# ============================================================

def show_activities():

    st.markdown(
        '<div class="section-title">Hoạt động học tập</div>',
        unsafe_allow_html=True
    )


    activities = get_rows(
        """
        SELECT

            users.full_name AS student,

            activities.action,

            activities.lesson_name,

            activities.created_at

        FROM activities

        LEFT JOIN users

        ON users.id = activities.student_id

        ORDER BY activities.id DESC
        """
    )


    if not activities:

        st.info(
            "Chưa có hoạt động."
        )

        return


    data = []


    for row in activities:

        data.append(
            {
                "Học sinh":
                    row["student"],

                "Hoạt động":
                    row["action"],

                "Bài giảng":
                    row["lesson_name"],

                "Thời gian":
                    row["created_at"]
            }
        )


    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True
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
            "MENU",
            [
                "Trang chủ",
                "Bài giảng",
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

def record_view(
    lesson_id,
    student_id,
    lesson_title
):

    existing = get_rows(
        """
        SELECT *
        FROM lesson_views
        WHERE lesson_id = ?
        AND student_id = ?
        """,
        (
            lesson_id,
            student_id
        )
    )


    if existing:

        run_query(
            """
            UPDATE lesson_views

            SET

                view_count =
                    view_count + 1,

                last_viewed = ?

            WHERE lesson_id = ?

            AND student_id = ?
            """,
            (
                get_time(),
                lesson_id,
                student_id
            )
        )


    else:

        run_query(
            """
            INSERT INTO lesson_views
            (
                lesson_id,
                student_id,
                view_count,
                first_viewed,
                last_viewed
            )
            VALUES (?, ?, 1, ?, ?)
            """,
            (
                lesson_id,
                student_id,
                get_time(),
                get_time()
            )
        )


    save_activity(
        student_id,
        "Xem bài giảng",
        lesson_title
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


    lessons = get_rows(
        """
        SELECT *
        FROM lessons
        ORDER BY id DESC
        """
    )


    if not lessons:

        st.info(
            "Giáo viên chưa đăng bài giảng."
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


            if lesson["video_file"]:

                video_path = Path(
                    lesson["video_file"]
                )


                if video_path.exists():

                    st.video(
                        str(video_path)
                    )


                    record_view(
                        lesson["id"],
                        user["id"],
                        lesson["title"]
                    )

                else:

                    st.warning(
                        "Video không khả dụng."
                    )


            if lesson["content"]:

                st.markdown(
                    lesson["content"]
                )


            if lesson["document_file"]:

                document_path = Path(
                    lesson["document_file"]
                )


                if document_path.exists():

                    with open(
                        document_path,
                        "rb"
                    ) as file:

                        st.download_button(
                            "Tải tài liệu",
                            file,
                            file_name=
                            lesson["document_name"]
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


    total_lessons = get_rows(
        """
        SELECT COUNT(*) AS total
        FROM lessons
        """
    )[0]["total"]


    viewed_lessons = get_rows(
        """
        SELECT COUNT(*) AS total
        FROM lesson_views
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    total_views = get_rows(
        """
        SELECT COALESCE(SUM(view_count), 0) AS total
        FROM lesson_views
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    a, b, c = st.columns(3)


    a.metric(
        "Tổng bài giảng",
        total_lessons
    )


    b.metric(
        "Bài đã xem",
        viewed_lessons
    )


    c.metric(
        "Tổng lượt xem",
        total_views
    )


# ============================================================
# TIẾN ĐỘ
# ============================================================

def student_progress():

    user = st.session_state.user


    st.markdown(
        '<div class="section-title">Tiến độ học tập</div>',
        unsafe_allow_html=True
    )


    total = get_rows(
        """
        SELECT COUNT(*) AS total
        FROM lessons
        """
    )[0]["total"]


    viewed = get_rows(
        """
        SELECT COUNT(*) AS total
        FROM lesson_views
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    if total > 0:

        percentage = viewed / total

    else:

        percentage = 0


    st.progress(
        percentage
    )


    st.write(
        f"Bạn đã xem **{viewed}/{total}** bài giảng."
    )


    views = get_rows(
        """
        SELECT

            lessons.title,

            lesson_views.view_count,

            lesson_views.last_viewed

        FROM lesson_views

        JOIN lessons

        ON lessons.id =
            lesson_views.lesson_id

        WHERE lesson_views.student_id = ?

        ORDER BY lesson_views.last_viewed DESC
        """,
        (user["id"],)
    )


    if views:

        data = []


        for row in views:

            data.append(
                {
                    "Bài giảng":
                        row["title"],

                    "Lượt xem":
                        row["view_count"],

                    "Xem gần nhất":
                        row["last_viewed"]
                }
            )


        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# MAIN
# ============================================================

if st.session_state.user is None:

    show_login_page()


else:

    user = st.session_state.user


    # ========================================================
    # GIÁO VIÊN
    # ========================================================

    if user["role"] == "teacher":

        page = teacher_sidebar()


        if page == "Tổng quan":

            teacher_dashboard()


        elif page == "Tạo bài giảng":

            create_lesson()


        elif page == "Quản lý bài giảng":

            manage_lessons()


        elif page == "Danh sách học sinh":

            show_students()


        elif page == "Lượt xem bài giảng":

            show_lesson_views()


        elif page == "Hoạt động học tập":

            show_activities()


    # ========================================================
    # HỌC SINH
    # ========================================================

    else:

        page = student_sidebar()


        if page == "Trang chủ":

            student_home()


        elif page == "Bài giảng":

            student_lessons()


        elif page == "Tiến độ học tập":

            student_progress()

