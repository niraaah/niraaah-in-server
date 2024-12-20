import mysql.connector
from flask import g

def getDatabaseConnection():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234",
            database="wsd3",  # 데이터베이스 이름 추가
            auth_plugin='mysql_native_password'
        )
    return g.db

def closeDatabaseConnection(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def initDatabase():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        auth_plugin='mysql_native_password'
    )
    cursor = conn.cursor()
    
    # 데이터베이스 생성
    cursor.execute("CREATE DATABASE IF NOT EXISTS wsd3")
    cursor.execute("USE wsd3")
    
    # 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(20),
            birth_date DATE,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            logo_url VARCHAR(500),
            website_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 나머지 테이블들도 여기에 추가...
    
    conn.commit()
    cursor.close()
    conn.close()

# 서버 시작 시 데이터베이스 초기화
initDatabase()
