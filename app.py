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
# Teacher security code
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

# ============================================================
# MÃ BẢO MẬT GIÁO VIÊN
# ============================================================
# Giáo viên phải nhập mã này khi ĐĂNG KÝ và ĐĂNG NHẬP.
# Bạn có thể đổi mã này nếu muốn.
TEACHER_CODE = "ENGLISHHUB2026"

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
            class_id INTEGER NOT NU
