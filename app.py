import streamlit as st
import sqlite3
import hashlib
import hmac
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

# ============================================================
# ENGLISHHUB LMS - PHIÊN BẢN GIAO DIỆN TIẾNG VIỆT
# Copy toàn bộ file này thành app.py
# ============================================================

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "englishhub.db"

st.set_page_config(
    page_title="EnglishHub LMS",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== GIAO DIỆN ====================
st.markdown("""
<style>
.block-container {max-width: 1400px; padding-top: 1.5rem;}
.hero {
    padding: 32px;
    border-radius: 20px;
    background: linear-gradient(135deg,#102A43,#2563EB);
    color: white;
    margin-bottom: 24px;
}
.hero h1 {font-size: 38px; margin: 0 0 7px 0;}
.hero p {font-size: 16px; margin: 0; opacity: .92;}
.card {
    padding: 20px;
    border: 1px solid #E5E7EB;
    border-radius: 16px;
    background: white;
    box-shadow: 0 5px 18px rgba(16,42,67,.06);
    margin-bottom: 12px;
}
.student-name {
    font-size: 21px;
    font-weight: 750;
    color: #102A43;
    margin-top: 7px;
}
.small {color:#667085; font-size:13px;}
.badge {
    display:inline-block;
    padding:4px 10px;
    border-radius:999px;
    background:#EAF2FF;
    color:#2563EB;
    font-size:12px;
    font-weight:700;
}
</style>
""", unsafe_allow_html=True)

# ==================== CƠ SỞ DỮ LIỆU ====================
def connect():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
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

    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        level TEXT,
        category TEXT,
        content TEXT,
        resource_url TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    con.close()

init_db()

# ==================== HỆ THỐNG ====================
def now():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def teacher_code():
    try:
        return st.secrets["LMS_TEACHER_CODE"]
    except Exception:
        return os.getenv("LMS_TEACHER_CODE", "THAY-MA-GIAO-VIEN")

def password_hash(password):
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120000)
    return salt.hex() + ":" + key.hex()

def check_password(password, stored):
    try:
        salt, key = stored.split(":")
        new_key = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), 120000
        )
        return hmac.compare_digest(new_key.hex(), key)
    except Exception:
        return False

def execute(sql, params=()):
    con = connect()
    cur = con.execute(sql, params)
    con.commit()
    result = cur.lastrowid
    con.close()
    return result

def fetch(sql, params=()):
    con = connect()
    rows = con.execute(sql, params).fetchall()
    con.close()
    return rows

def log_activity(student_id, action, object_name=""):
    execute("""
        INSERT INTO activity(student_id,action,object_name,created_at)
        VALUES(?,?,?,?)
    """, (student_id, action, object_name, now()))

# ==================== ĐĂNG KÝ / ĐĂNG NHẬP ====================
def register(full_name, username, password, role, code=""):
    full_name = full_name.strip()
    username = username.strip().lower()

    if not full_name or not username or not password:
        return False, "Vui lòng điền đầy đủ thông tin."

    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự."

    if role == "teacher":
        if not hmac.compare_digest(code, teacher_code()):
            return False, "Mã truy cập giáo viên không chính xác."

    try:
        execute("""
            INSERT INTO users
            (full_name,username,password_hash,role,created_at)
            VALUES(?,?,?,?,?)
        """, (
            full_name,
            username,
            password_hash(password),
            role,
            now()
        ))
        return True, "Tạo tài khoản thành công."
    except sqlite3.IntegrityError:
        return False, "Tên đăng nhập này đã tồn tại."

def login(username, password, role):
    rows = fetch("""
        SELECT *
        FROM users
        WHERE username=? AND role=?
    """, (username.strip().lower(), role))

    if rows and check_password(password, rows[0]["password_hash"]):
        return dict(rows[0])

    return None

# ==================== TIẾN ĐỘ ====================
def student_progress(student_id):
    total_lessons = fetch(
        "SELECT COUNT(*) n FROM lessons"
    )[0]["n"]

    viewed_lessons = fetch("""
        SELECT COUNT(*) n
        FROM lesson_views
        WHERE student_id=?
    """, (student_id,))[0]["n"]

    total_exercises = fetch(
        "SELECT COUNT(*) n FROM exercises"
    )[0]["n"]

    completed_exercises = fetch("""
        SELECT COUNT(*) n
        FROM submissions
        WHERE student_id=?
    """, (student_id,))[0]["n"]

    avg = fetch("""
        SELECT AVG(score) a
        FROM submissions
        WHERE student_id=?
    """, (student_id,))[0]["a"]

    average = float(avg or 0)

    lesson_rate = (
        viewed_lessons / total_lessons * 100
        if total_lessons else 0
    )

    exercise_rate = (
        completed_exercises / total_exercises * 100
        if total_exercises else 0
    )

    # Điểm tham gia:
    # 40% mức độ học bài + 60% mức độ hoàn thành bài tập
    # có điều chỉnh theo điểm bài tập.
    participation = round(
        lesson_rate * 0.4 +
        exercise_rate * 0.6 * (
            average / 100 if total_exercises else 0
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

# ==================== TRANG ĐĂNG NHẬP ====================
def login_page():
    st.markdown("""
    <div class="hero">
        <h1>EnglishHub LMS</h1>
        <p>Nền tảng học tiếng Anh dành cho lớp học của bạn.</p>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown("### Đăng nhập")

        role = st.radio(
            "Bạn là:",
            ["Học sinh", "Giáo viên"],
            horizontal=True
        )

        role_db = "student" if role == "Học sinh" else "teacher"

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

    with right:
        st.markdown("### Tạo tài khoản")

        st.info(
            "Học sinh có thể tự đăng ký. "
            "Tài khoản giáo viên bắt buộc phải có Mã truy cập giáo viên."
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
                ["Học sinh", "Giáo viên"]
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
# GIAO DIỆN GIÁO VIÊN
# ============================================================

def teacher_sidebar():
    with st.sidebar:
        st.markdown("## EnglishHub LMS")

        st.caption(
            f"Giáo viên: {st.session_state.user['full_name']}"
        )

        page = st.radio(
            "MENU GIÁO VIÊN",
            [
                "Tổng quan",
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

def teacher_dashboard():
    st.markdown("""
    <div class="hero">
        <h1>Tổng quan lớp học</h1>
        <p>
            Quản lý bài giảng, bài tập và theo dõi tiến độ của từng học sinh.
        </p>
    </div>
    """, unsafe_allow_html=True)

    students = fetch("""
        SELECT COUNT(*) n
        FROM users
        WHERE role='student'
    """)[0]["n"]

    lessons = fetch(
        "SELECT COUNT(*) n FROM lessons"
    )[0]["n"]

    exercises = fetch(
        "SELECT COUNT(*) n FROM exercises"
    )[0]["n"]

    submissions = fetch(
        "SELECT COUNT(*) n FROM submissions"
    )[0]["n"]

    a,b,c,d = st.columns(4)

    a.metric("Học sinh", students)
    b.metric("Bài giảng", lessons)
    c.metric("Bài tập", exercises)
    d.metric("Bài đã nộp", submissions)

    st.markdown("### Tiến độ học sinh")

    students_data = fetch("""
        SELECT id, full_name, username, created_at
        FROM users
        WHERE role='student'
        ORDER BY full_name
    """)

    data = []

    for student in students_data:
        p = student_progress(student["id"])

        data.append({
            "Họ và tên": student["full_name"],
            "Tên đăng nhập": student["username"],
            "Bài giảng": f"{p['viewed_lessons']}/{p['total_lessons']}",
            "Bài tập": f"{p['completed_exercises']}/{p['total_exercises']}",
            "Điểm trung bình": f"{p['average']}%",
            "Mức độ tham gia": f"{p['participation']}%"
        })

    if data:
        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Chưa có học sinh đăng ký.")

def teacher_lessons():
    st.markdown("## Danh sách bài giảng")

    lessons = fetch("""
        SELECT
            l.*,
            COUNT(v.id) AS so_hoc_sinh_da_xem
        FROM lessons l
        LEFT JOIN lesson_views v
            ON v.lesson_id=l.id
        GROUP BY l.id
        ORDER BY l.created_at DESC
    """)

    if not lessons:
        st.info(
            "Chưa có bài giảng. Hãy tạo bài giảng đầu tiên."
        )
        return

    for lesson in lessons:
        st.markdown(f"""
        <div class="card">
            <span class="badge">
                {lesson["level"]} • {lesson["category"]}
            </span>

            <div class="student-name">
                {lesson["title"]}
            </div>

            <p>
                {lesson["description"] or ""}
            </p>

            <span class="small">
                Số học sinh đã xem: {lesson["so_hoc_sinh_da_xem"]}
            </span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Xem nội dung bài giảng"):
            st.markdown(
                lesson["content"] or ""
            )

            if lesson["resource_url"]:
                st.link_button(
                    "Mở tài liệu bên ngoài",
                    lesson["resource_url"]
                )

def create_lesson():
    st.markdown("## Tạo bài giảng mới")

    with st.form("create_lesson"):
        title = st.text_input(
            "Tên bài giảng"
        )

        description = st.text_area(
            "Mô tả ngắn"
        )

        a,b = st.columns(2)

        level = a.selectbox(
            "Trình độ CEFR",
            ["A1","A2","B1","B2","C1","C2"]
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
Ví dụ:

# Present Perfect

## Công thức

Subject + have/has + V3

## Ví dụ

I have studied English for three years.

## Bài tập

Complete the sentences...
"""
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
        else:
            execute("""
                INSERT INTO lessons
                (title,description,level,category,content,resource_url,created_at)
                VALUES(?,?,?,?,?,?,?)
            """, (
                title,
                description,
                level,
                category,
                content,
                resource,
                now()
            ))

            st.success(
                "Đã đăng bài giảng thành công."
            )
            st.rerun()

def create_exercise():
    st.markdown("## Tạo bài tập mới")

    lessons = fetch("""
        SELECT id,title
        FROM lessons
        ORDER BY title
    """)

    lesson_dict = {
        "Không liên kết bài giảng": None
    }

    for lesson in lessons:
        lesson_dict[lesson["title"]] = lesson["id"]

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
        else:
            execute("""
                INSERT INTO exercises
                (title,lesson_id,instructions,questions,max_score,created_at)
                VALUES(?,?,?,?,?,?)
            """, (
                title,
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

def teacher_exercises():
    st.markdown("## Bài tập và chấm điểm")

    submissions = fetch("""
        SELECT
            s.id,
            s.answer,
            s.score,
            s.feedback,
            s.submitted_at,
            u.full_name AS student_name,
            e.title AS exercise_title,
            e.max_score
        FROM submissions s
        JOIN users u ON u.id=s.student_id
        JOIN exercises e ON e.id=s.exercise_id
        ORDER BY s.submitted_at DESC
    """)

    if not submissions:
        st.info(
            "Chưa có học sinh nộp bài."
        )
        return

    for submission in submissions:
        st.markdown(
            f"### {submission['student_name']} — "
            f"{submission['exercise_title']}"
        )

        st.write("**Bài làm của học sinh:**")
        st.write(
            submission["answer"] or "(Không có nội dung)"
        )

        with st.form(
            f"grade_{submission['id']}"
        ):
            score = st.number_input(
                "Điểm",
                0.0,
                float(submission["max_score"]),
                float(submission["score"] or 0),
                step=1.0
            )

            feedback = st.text_area(
                "Nhận xét cho học sinh",
                value=submission["feedback"] or ""
            )

            save = st.form_submit_button(
                "Lưu điểm và nhận xét",
                use_container_width=True
            )

        if save:
            execute("""
                UPDATE submissions
                SET score=?, feedback=?
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

def teacher_students():
    st.markdown("## Quản lý học sinh")

    students = fetch("""
        SELECT *
        FROM users
        WHERE role='student'
        ORDER BY full_name
    """)

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
        s for s in students
        if s["full_name"] == selected_name
    )

    p = student_progress(
        student["id"]
    )

    st.markdown(f"""
    <div class="card">
        <div class="student-name">
            {student["full_name"]}
        </div>

        <div class="small">
            Tên đăng nhập: {student["username"]}
        </div>

        <div class="small">
            Ngày tham gia: {student["created_at"]}
        </div>
    </div>
    """, unsafe_allow_html=True)

    a,b,c,d = st.columns(4)

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
        p["participation"]/100,
        text=f"Mức độ tham gia: {p['participation']}%"
    )

    st.markdown("### Lịch sử học bài")

    views = fetch("""
        SELECT
            l.title AS "Bài giảng",
            l.level AS "Trình độ",
            l.category AS "Chủ đề",
            v.first_viewed AS "Lần xem đầu",
            v.last_viewed AS "Lần xem gần nhất",
            v.view_count AS "Số lần xem"
        FROM lesson_views v
        JOIN lessons l ON l.id=v.lesson_id
        WHERE v.student_id=?
        ORDER BY v.last_viewed DESC
    """, (student["id"],))

    if views:
        st.dataframe(
            pd.DataFrame([dict(v) for v in views]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "Học sinh này chưa xem bài giảng nào."
        )

    st.markdown("### Kết quả bài tập")

    results = fetch("""
        SELECT
            e.title AS "Bài tập",
            s.score AS "Điểm",
            e.max_score AS "Điểm tối đa",
            s.feedback AS "Nhận xét",
            s.submitted_at AS "Thời gian nộp"
        FROM submissions s
        JOIN exercises e ON e.id=s.exercise_id
        WHERE s.student_id=?
        ORDER BY s.submitted_at DESC
    """, (student["id"],))

    if results:
        st.dataframe(
            pd.DataFrame([dict(r) for r in results]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "Học sinh này chưa nộp bài tập nào."
        )

def teacher_lesson_views():
    st.markdown("## Lượt xem bài giảng")

    lessons = fetch("""
        SELECT id,title
        FROM lessons
        ORDER BY title
    """)

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
        JOIN users u ON u.id=v.student_id
        WHERE v.lesson_id=?
        ORDER BY v.last_viewed DESC
    """, (selected["id"],))

    st.markdown(
        f"### Học sinh đã xem: {selected['title']}"
    )

    if rows:
        st.dataframe(
            pd.DataFrame([dict(r) for r in rows]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "Chưa có học sinh nào xem bài giảng này."
        )

def teacher_activity():
    st.markdown("## Hoạt động học tập")

    rows = fetch("""
        SELECT
            a.created_at AS "Thời gian",
            u.full_name AS "Học sinh",
            a.action AS "Hoạt động",
            a.object_name AS "Nội dung"
        FROM activity a
        LEFT JOIN users u ON u.id=a.student_id
        ORDER BY a.created_at DESC
        LIMIT 300
    """)

    if rows:
        st.dataframe(
            pd.DataFrame([dict(r) for r in rows]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "Chưa có hoạt động học tập."
        )

# ============================================================
# GIAO DIỆN HỌC SINH
# ============================================================

def student_sidebar():
    with st.sidebar:
        st.markdown("## EnglishHub LMS")

        st.caption(
            f"Học sinh: {st.session_state.user['full_name']}"
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

def student_dashboard():
    user = st.session_state.user
    p = student_progress(user["id"])

    st.markdown(f"""
    <div class="hero">
        <h1>Xin chào, {user["full_name"]}!</h1>
        <p>
            Chào mừng bạn quay lại EnglishHub.
            Hãy tiếp tục hành trình học tiếng Anh của mình.
        </p>
    </div>
    """, unsafe_allow_html=True)

    a,b,c,d = st.columns(4)

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

    st.markdown("### Tiếp tục học")

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
        ORDER BY viewed ASC, l.created_at DESC
    """, (user["id"],))

    if not lessons:
        st.info(
            "Giáo viên chưa đăng bài giảng nào."
        )
        return

    for lesson in lessons[:8]:
        st.markdown(f"""
        <div class="card">
            <span class="badge">
                {lesson["level"]} • {lesson["category"]}
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
            st.session_state.open_lesson = lesson["id"]
            st.rerun()

def record_lesson_view(
    lesson_id,
    student_id,
    lesson_title
):
    existing = fetch("""
        SELECT *
        FROM lesson_views
        WHERE lesson_id=? AND student_id=?
    """, (lesson_id, student_id))

    if existing:
        execute("""
            UPDATE lesson_views
            SET last_viewed=?,
                view_count=view_count+1
            WHERE lesson_id=? AND student_id=?
        """, (
            now(),
            lesson_id,
            student_id
        ))
    else:
        execute("""
            INSERT INTO lesson_views
            (lesson_id,student_id,first_viewed,last_viewed,view_count)
            VALUES(?,?,?,?,1)
        """, (
            lesson_id,
            student_id,
            now(),
            now(),
            1
        ))

    log_activity(
        student_id,
        "Đã xem bài giảng",
        lesson_title
    )

def student_lessons():
    user = st.session_state.user

    if st.session_state.get("open_lesson"):
        open_student_lesson(
            st.session_state.open_lesson
        )
        return

    st.markdown("## Bài giảng")

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
        ORDER BY l.created_at DESC
    """, (user["id"],))

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
                {lesson["level"]} • {lesson["category"]} • {status}
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

            st.session_state.open_lesson = lesson["id"]
            st.rerun()

def open_student_lesson(lesson_id):
    user = st.session_state.user

    rows = fetch(
        "SELECT * FROM lessons WHERE id=?",
        (lesson_id,)
    )

    if not rows:
        st.session_state.open_lesson = None
        return

    lesson = rows[0]

    record_lesson_view(
        lesson["id"],
        user["id"],
        lesson["title"]
    )

    st.markdown(f"""
    <div class="hero">
        <span class="badge">
            {lesson["level"]} • {lesson["category"]}
        </span>

        <h1>{lesson["title"]}</h1>

        <p>
            {lesson["description"] or ""}
        </p>
    </div>
    """, unsafe_allow_html=True)

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

def student_exercises():
    user = st.session_state.user

    st.markdown("## Bài tập")

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
        ORDER BY e.created_at DESC
    """, (user["id"],))

    if not exercises:
        st.info(
            "Giáo viên chưa đăng bài tập nào."
        )
        return

    for exercise in exercises:
        status = (
            f"Đã nộp • {exercise['score']}/{exercise['max_score']}"
            if exercise["submitted_at"]
            else "Chưa nộp"
        )

        with st.expander(
            f"{exercise['title']} — {status}"
        ):
            if exercise["lesson_title"]:
                st.caption(
                    f"Bài giảng: {exercise['lesson_title']}"
                )

            st.write(
                exercise["instructions"] or ""
            )

            st.markdown("### Yêu cầu bài tập")

            st.markdown(
                exercise["questions"]
            )

            with st.form(
                f"submit_{exercise['id']}"
            ):
                answer = st.text_area(
                    "Bài làm của bạn",
                    value=exercise["answer"] or "",
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
                    WHERE exercise_id=? AND student_id=?
                """, (
                    exercise["id"],
                    user["id"]
                ))

                if existing:
                    execute("""
                        UPDATE submissions
                        SET answer=?, submitted_at=?
                        WHERE id=?
                    """, (
                        answer,
                        now(),
                        existing[0]["id"]
                    ))
                else:
                    execute("""
                        INSERT INTO submissions
                        (exercise_id,student_id,answer,score,submitted_at)
                        VALUES(?,?,?,?,?)
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
                    f"Nhận xét của giáo viên: "
                    f"{exercise['feedback']}"
                )

def student_progress_page():
    user = st.session_state.user
    p = student_progress(user["id"])

    st.markdown(f"""
    <div class="hero">
        <h1>Tiến độ học tập</h1>
        <p>{user["full_name"]}</p>
    </div>
    """, unsafe_allow_html=True)

    st.progress(
        p["participation"]/100,
        text=f"Mức độ tham gia: {p['participation']}%"
    )

    a,b,c,d = st.columns(4)

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

    st.markdown("### Lịch sử học bài")

    views = fetch("""
        SELECT
            l.title AS "Bài giảng",
            l.level AS "Trình độ",
            l.category AS "Chủ đề",
            v.first_viewed AS "Lần xem đầu tiên",
            v.last_viewed AS "Lần xem gần nhất",
            v.view_count AS "Số lần xem"
        FROM lesson_views v
        JOIN lessons l ON l.id=v.lesson_id
        WHERE v.student_id=?
        ORDER BY v.last_viewed DESC
    """, (user["id"],))

    if views:
        st.dataframe(
            pd.DataFrame([dict(v) for v in views]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "Bạn chưa xem bài giảng nào."
        )

    st.markdown("### Kết quả bài tập")

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
    """, (user["id"],))

    if results:
        st.dataframe(
            pd.DataFrame([dict(r) for r in results]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "Bạn chưa nộp bài tập nào."
        )

# ============================================================
# CHẠY WEBSITE
# ============================================================

if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    login_page()

else:
    user = st.session_state.user

    if user["role"] == "teacher":

        page = teacher_sidebar()

        if page == "Tổng quan":
            teacher_dashboard()

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
