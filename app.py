```python
import streamlit as st
import sqlite3
import hashlib
import hmac
import os
from pathlib import Path
from datetime import datetime
import pandas as pd


# ============================================================
# 1. CẤU HÌNH
# ============================================================

st.set_page_config(
    page_title="EnglishHub LMS",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


BASE_DIR = Path(__file__).parent

DATABASE = BASE_DIR / "englishhub.db"

UPLOAD_FOLDER = BASE_DIR / "uploads"

VIDEO_FOLDER = UPLOAD_FOLDER / "videos"

DOCUMENT_FOLDER = UPLOAD_FOLDER / "documents"

VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

DOCUMENT_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. MÃ GIÁO VIÊN
# ============================================================

TEACHER_CODE = os.environ.get(
    "LMS_TEACHER_CODE",
    "TOM2026"
)


# ============================================================
# 3. GIAO DIỆN
# ============================================================

st.title("EnglishHub LMS")

st.caption(
    "Nền tảng học tiếng Anh dành cho lớp học của Tom và các bạn."
)


# ============================================================
# 4. DATABASE
# ============================================================

def connect_database():

    connection = sqlite3.connect(
        DATABASE,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():

    connection = connect_database()

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


        CREATE TABLE IF NOT EXISTS participation (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id INTEGER NOT NULL,

            lesson_id INTEGER NOT NULL,

            points REAL DEFAULT 0,

            note TEXT,

            updated_at TEXT,

            UNIQUE(student_id, lesson_id)

        );

        """
    )

    connection.commit()

    connection.close()


initialize_database()


# ============================================================
# 5. DATABASE FUNCTIONS
# ============================================================

def execute_query(
    query,
    parameters=()
):

    connection = connect_database()

    cursor = connection.execute(
        query,
        parameters
    )

    connection.commit()

    last_id = cursor.lastrowid

    connection.close()

    return last_id


def fetch_all(
    query,
    parameters=()
):

    connection = connect_database()

    rows = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return rows


def get_time():

    return datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )


# ============================================================
# 6. MẬT KHẨU
# ============================================================

def hash_password(password):

    salt = os.urandom(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )

    return (
        salt.hex()
        + ":"
        + key.hex()
    )


def verify_password(
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
# 7. SESSION
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


# ============================================================
# 8. ĐĂNG NHẬP
# ============================================================

def login():

    st.header("Đăng nhập")

    role_display = st.radio(
        "Bạn là:",
        [
            "Học sinh",
            "Giáo viên"
        ],
        horizontal=True
    )


    if role_display == "Học sinh":

        role = "student"

    else:

        role = "teacher"


    username = st.text_input(
        "Tên đăng nhập"
    )


    password = st.text_input(
        "Mật khẩu",
        type="password"
    )


    if st.button(
        "Đăng nhập",
        type="primary",
        use_container_width=True
    ):

        users = fetch_all(
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

            st.error(
                "Không tìm thấy tài khoản."
            )

            return


        user = users[0]


        if verify_password(
            password,
            user["password"]
        ):

            st.session_state.user = dict(user)

            st.success(
                "Đăng nhập thành công."
            )

            st.rerun()

        else:

            st.error(
                "Mật khẩu không đúng."
            )


# ============================================================
# 9. TẠO TÀI KHOẢN
# ============================================================

def register():

    st.header("Tạo tài khoản")


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


    role_display = st.selectbox(
        "Loại tài khoản",
        [
            "Học sinh",
            "Giáo viên"
        ]
    )


    teacher_code = ""


    if role_display == "Giáo viên":

        teacher_code = st.text_input(
            "Mã giáo viên",
            type="password"
        )


        st.info(
            "Mã giáo viên mặc định hiện tại là TOM2026."
        )


    if st.button(
        "Tạo tài khoản",
        use_container_width=True
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


        if role_display == "Giáo viên":

            if teacher_code != TEACHER_CODE:

                st.error(
                    "Mã giáo viên không đúng."
                )

                return


        role = (
            "teacher"
            if role_display == "Giáo viên"
            else "student"
        )


        try:

            execute_query(
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
                    hash_password(password),
                    role,
                    get_time()
                )
            )


            st.success(
                "Tạo tài khoản thành công. Bạn có thể đăng nhập."
            )


        except sqlite3.IntegrityError:

            st.error(
                "Tên đăng nhập này đã tồn tại."
            )


# ============================================================
# 10. TRANG ĐĂNG NHẬP
# ============================================================

def login_page():

    st.divider()

    left, right = st.columns(
        2
    )


    with left:

        login()


    with right:

        register()


# ============================================================
# 11. GHI HOẠT ĐỘNG
# ============================================================

def save_activity(
    student_id,
    action,
    lesson_name
):

    execute_query(
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
# 12. GHI LƯỢT XEM
# ============================================================

def record_view(
    lesson_id,
    student_id,
    lesson_name
):

    existing = fetch_all(
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

        execute_query(
            """
            UPDATE lesson_views

            SET
                view_count = view_count + 1,
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

        execute_query(
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
        lesson_name
    )


# ============================================================
# 13. MENU GIÁO VIÊN
# ============================================================

def teacher_menu():

    user = st.session_state.user


    st.sidebar.title(
        "Khu vực giáo viên"
    )


    st.sidebar.write(
        "Xin chào,"
    )


    st.sidebar.subheader(
        user["full_name"]
    )


    page = st.sidebar.radio(
        "Chức năng",
        [
            "Tổng quan",
            "Đăng bài giảng",
            "Quản lý bài giảng",
            "Học sinh",
            "Theo dõi lượt xem",
            "Đánh giá học sinh",
            "Hoạt động học tập"
        ]
    )


    st.sidebar.divider()


    if st.sidebar.button(
        "Đăng xuất",
        use_container_width=True
    ):

        st.session_state.user = None

        st.rerun()


    return page


# ============================================================
# 14. TỔNG QUAN GIÁO VIÊN
# ============================================================

def teacher_dashboard():

    st.header(
        "Tổng quan lớp học"
    )


    students = fetch_all(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE role = 'student'
        """
    )[0]["total"]


    lessons = fetch_all(
        """
        SELECT COUNT(*) AS total
        FROM lessons
        """
    )[0]["total"]


    views = fetch_all(
        """
        SELECT COALESCE(SUM(view_count), 0) AS total
        FROM lesson_views
        """
    )[0]["total"]


    activities = fetch_all(
        """
        SELECT COUNT(*) AS total
        FROM activities
        """
    )[0]["total"]


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
        "Lượt xem",
        views
    )


    d.metric(
        "Hoạt động",
        activities
    )


    st.divider()


    st.subheader(
        "Danh sách học sinh"
    )


    student_rows = fetch_all(
        """
        SELECT
            id,
            full_name,
            username,
            created_at
        FROM users
        WHERE role = 'student'
        ORDER BY full_name
        """
    )


    table = []


    for student in student_rows:

        viewed = fetch_all(
            """
            SELECT COUNT(*) AS total
            FROM lesson_views
            WHERE student_id = ?
            """,
            (student["id"],)
        )[0]["total"]


        points = fetch_all(
            """
            SELECT COALESCE(SUM(points), 0) AS total
            FROM participation
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

                "Điểm tham gia":
                    round(points, 1),

                "Ngày tham gia":
                    student["created_at"]
            }
        )


    if table:

        st.dataframe(
            pd.DataFrame(table),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Chưa có học sinh."
        )


# ============================================================
# 15. ĐĂNG BÀI GIẢNG
# ============================================================

def create_lesson():

    st.header(
        "Đăng bài giảng"
    )


    title = st.text_input(
        "Tên bài giảng *"
    )


    description = st.text_area(
        "Mô tả"
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
                "Khác"
            ]
        )


    content = st.text_area(
        "Nội dung bài giảng",
        height=250
    )


    st.subheader(
        "Video bài giảng"
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

        st.video(
            video
        )


    st.subheader(
        "Tài liệu"
    )


    document = st.file_uploader(
        "Upload tài liệu",
        type=[
            "pdf",
            "doc",
            "docx",
            "ppt",
            "pptx"
        ]
    )


    if st.button(
        "Đăng bài giảng",
        type="primary",
        use_container_width=True
    ):

        if not title.strip():

            st.error(
                "Bạn chưa nhập tên bài giảng."
            )

            return


        video_file = ""

        video_name = ""


        if video:

            filename = (
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


            video_path = (
                VIDEO_FOLDER / filename
            )


            with open(
                video_path,
                "wb"
            ) as file:

                file.write(
                    video.getbuffer()
                )


            video_file = str(
                video_path
            )

            video_name = video.name


        document_file = ""

        document_name = ""


        if document:

            filename = (
                str(
                    int(
                        datetime.now().timestamp()
                    )
                )
                + "_"
                + document.name.replace(
                    " ",
                    "_"
                )
            )


            document_path = (
                DOCUMENT_FOLDER / filename
            )


            with open(
                document_path,
                "wb"
            ) as file:

                file.write(
                    document.getbuffer()
                )


            document_file = str(
                document_path
            )

            document_name = document.name


        execute_query(
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
                video_file,
                video_name,
                document_file,
                document_name,
                get_time()
            )
        )


        st.success(
            "Bài giảng đã được đăng thành công."
        )


        st.rerun()


# ============================================================
# 16. QUẢN LÝ BÀI GIẢNG
# ============================================================

def manage_lessons():

    st.header(
        "Quản lý bài giảng"
    )


    lessons = fetch_all(
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

            st.write(
                "Trình độ:",
                lesson["level"]
            )


            st.write(
                "Chủ đề:",
                lesson["category"]
            )


            st.write(
                lesson["description"] or ""
            )


            if lesson["video_file"]:

                path = Path(
                    lesson["video_file"]
                )


                if path.exists():

                    st.video(
                        str(path)
                    )


            if lesson["content"]:

                st.markdown(
                    lesson["content"]
                )


            if lesson["document_file"]:

                path = Path(
                    lesson["document_file"]
                )


                if path.exists():

                    with open(
                        path,
                        "rb"
                    ) as file:

                        st.download_button(
                            "Tải tài liệu",
                            file,
                            file_name=
                            lesson["document_name"]
                        )


# ============================================================
# 17. DANH SÁCH HỌC SINH
# ============================================================

def students_page():

    st.header(
        "Danh sách học sinh"
    )


    students = fetch_all(
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

        views = fetch_all(
            """
            SELECT
                COALESCE(SUM(view_count), 0) AS total
            FROM lesson_views
            WHERE student_id = ?
            """,
            (student["id"],)
        )[0]["total"]


        points = fetch_all(
            """
            SELECT
                COALESCE(SUM(points), 0) AS total
            FROM participation
            WHERE student_id = ?
            """,
            (student["id"],)
        )[0]["total"]


        st.subheader(
            student["full_name"]
        )


        st.write(
            "Tên đăng nhập:",
            student["username"]
        )


        col1, col2 = st.columns(2)


        col1.metric(
            "Tổng lượt xem",
            views
        )


        col2.metric(
            "Điểm tham gia",
            round(points, 1)
        )


        st.divider()


# ============================================================
# 18. THEO DÕI LƯỢT XEM
# ============================================================

def views_page():

    st.header(
        "Theo dõi lượt xem bài giảng"
    )


    rows = fetch_all(
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


    if not rows:

        st.info(
            "Chưa có dữ liệu lượt xem."
        )

        return


    data = []


    for row in rows:

        data.append(
            {
                "Bài giảng":
                    row["lesson"],

                "Học sinh":
                    row["student"],

                "Lượt xem":
                    row["views"],

                "Lần đầu":
                    row["first_view"],

                "Gần nhất":
                    row["last_view"]
            }
        )


    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 19. ĐÁNH GIÁ HỌC SINH
# ============================================================

def evaluate_students():

    st.header(
        "Đánh giá mức độ tham gia"
    )


    students = fetch_all(
        """
        SELECT id, full_name
        FROM users
        WHERE role = 'student'
        ORDER BY full_name
        """
    )


    lessons = fetch_all(
        """
        SELECT id, title
        FROM lessons
        ORDER BY id DESC
        """
    )


    if not students:

        st.info(
            "Chưa có học sinh."
        )

        return


    if not lessons:

        st.info(
            "Chưa có bài giảng."
        )

        return


    student_options = {
        student["full_name"]: student["id"]
        for student in students
    }


    lesson_options = {
        lesson["title"]: lesson["id"]
        for lesson in lessons
    }


    selected_student = st.selectbox(
        "Chọn học sinh",
        list(student_options.keys())
    )


    selected_lesson = st.selectbox(
        "Chọn bài giảng",
        list(lesson_options.keys())
    )


    points = st.number_input(
        "Điểm tham gia",
        min_value=0.0,
        max_value=10.0,
        value=5.0,
        step=0.5
    )


    note = st.text_area(
        "Nhận xét"
    )


    if st.button(
        "Lưu đánh giá",
        type="primary"
    ):

        student_id = student_options[
            selected_student
        ]


        lesson_id = lesson_options[
            selected_lesson
        ]


        existing = fetch_all(
            """
            SELECT id
            FROM participation
            WHERE student_id = ?
            AND lesson_id = ?
            """,
            (
                student_id,
                lesson_id
            )
        )


        if existing:

            execute_query(
                """
                UPDATE participation

                SET
                    points = ?,
                    note = ?,
                    updated_at = ?

                WHERE student_id = ?

                AND lesson_id = ?
                """,
                (
                    points,
                    note,
                    get_time(),
                    student_id,
                    lesson_id
                )
            )


        else:

            execute_query(
                """
                INSERT INTO participation
                (
                    student_id,
                    lesson_id,
                    points,
                    note,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    lesson_id,
                    points,
                    note,
                    get_time()
                )
            )


        st.success(
            "Đã lưu đánh giá."
        )


    st.divider()


    results = fetch_all(
        """
        SELECT

            users.full_name AS student,

            lessons.title AS lesson,

            participation.points,

            participation.note,

            participation.updated_at

        FROM participation

        JOIN users
        ON users.id = participation.student_id

        JOIN lessons
        ON lessons.id = participation.lesson_id

        ORDER BY participation.updated_at DESC
        """
    )


    if results:

        data = []


        for row in results:

            data.append(
                {
                    "Học sinh":
                        row["student"],

                    "Bài giảng":
                        row["lesson"],

                    "Điểm":
                        row["points"],

                    "Nhận xét":
                        row["note"],

                    "Cập nhật":
                        row["updated_at"]
                }
            )


        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# 20. HOẠT ĐỘNG HỌC TẬP
# ============================================================

def activities_page():

    st.header(
        "Hoạt động học tập"
    )


    rows = fetch_all(
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


    if not rows:

        st.info(
            "Chưa có hoạt động."
        )

        return


    data = []


    for row in rows:

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
# 21. MENU HỌC SINH
# ============================================================

def student_menu():

    user = st.session_state.user


    st.sidebar.title(
        "Khu vực học sinh"
    )


    st.sidebar.write(
        "Xin chào,"
    )


    st.sidebar.subheader(
        user["full_name"]
    )


    page = st.sidebar.radio(
        "Chức năng",
        [
            "Trang chủ",
            "Bài giảng",
            "Tiến độ học tập"
        ]
    )


    st.sidebar.divider()


    if st.sidebar.button(
        "Đăng xuất",
        use_container_width=True
    ):

        st.session_state.user = None

        st.rerun()


    return page


# ============================================================
# 22. TRANG CHỦ HỌC SINH
# ============================================================

def student_home():

    user = st.session_state.user


    st.header(
        "Trang chủ"
    )


    st.subheader(
        "Xin chào, "
        + user["full_name"]
        + "!"
    )


    total_lessons = fetch_all(
        """
        SELECT COUNT(*) AS total
        FROM lessons
        """
    )[0]["total"]


    viewed_lessons = fetch_all(
        """
        SELECT COUNT(*) AS total
        FROM lesson_views
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    total_views = fetch_all(
        """
        SELECT COALESCE(SUM(view_count), 0) AS total
        FROM lesson_views
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    total_points = fetch_all(
        """
        SELECT COALESCE(SUM(points), 0) AS total
        FROM participation
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    a, b, c, d = st.columns(4)


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


    d.metric(
        "Điểm tham gia",
        round(total_points, 1)
    )


# ============================================================
# 23. BÀI GIẢNG HỌC SINH
# ============================================================

def student_lessons():

    user = st.session_state.user


    st.header(
        "Bài giảng"
    )


    lessons = fetch_all(
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

            st.write(
                "Trình độ:",
                lesson["level"]
            )


            st.write(
                "Chủ đề:",
                lesson["category"]
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
                        "Video không còn khả dụng."
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
# 24. TIẾN ĐỘ HỌC SINH
# ============================================================

def student_progress():

    user = st.session_state.user


    st.header(
        "Tiến độ học tập"
    )


    total = fetch_all(
        """
        SELECT COUNT(*) AS total
        FROM lessons
        """
    )[0]["total"]


    viewed = fetch_all(
        """
        SELECT COUNT(*) AS total
        FROM lesson_views
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    if total > 0:

        progress = viewed / total

    else:

        progress = 0


    st.progress(
        progress
    )


    st.write(
        f"Bạn đã xem {viewed}/{total} bài giảng."
    )


    points = fetch_all(
        """
        SELECT
            COALESCE(SUM(points), 0) AS total
        FROM participation
        WHERE student_id = ?
        """,
        (user["id"],)
    )[0]["total"]


    st.metric(
        "Tổng điểm tham gia",
        round(points, 1)
    )


    rows = fetch_all(
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


    if rows:

        data = []


        for row in rows:

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
# 25. CHẠY ỨNG DỤNG
# ============================================================

if st.session_state.user is None:

    login_page()


else:

    user = st.session_state.user


    if user["role"] == "teacher":

        page = teacher_menu()


        if page == "Tổng quan":

            teacher_dashboard()


        elif page == "Đăng bài giảng":

            create_lesson()


        elif page == "Quản lý bài giảng":

            manage_lessons()


        elif page == "Học sinh":

            students_page()


        elif page == "Theo dõi lượt xem":

            views_page()


        elif page == "Đánh giá học sinh":

            evaluate_students()


        elif page == "Hoạt động học tập":

            activities_page()


    else:

        page = student_menu()


        if page == "Trang chủ":

            student_home()


        elif page == "Bài giảng":

            student_lessons()


        elif page == "Tiến độ học tập":

            student_progress()
```
