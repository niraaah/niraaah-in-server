import mysql.connector
from mysql.connector import pooling
from flask import g

import atexit
import time

# 데이터베이스 설정
databaseConfig = {
    "host": "113.198.66.75",  # 실제 DB 서버 주소
    "port": 10108,            # 실제 포트
    "user": "admin",
    "password": "qwer1234",
    "database": "wsd3"
}

# 커넥션 풀 설정
poolConfig = {
    "pool_name": "mypool",
    "pool_size": 32,          # 풀 크기
    "pool_reset_session": True,
    **databaseConfig         # 데이터베이스 설정을 풀 설정에 포함
}

# 재시도 관련 설정
RETRY_COUNT = 3
RETRY_DELAY = 0.1
CONNECTION_TIMEOUT = 3

# 커넥션 풀 생성
databasePool = mysql.connector.pooling.MySQLConnectionPool(**poolConfig)

def getDatabaseConnection():
    if 'database' not in g:
        for _ in range(RETRY_COUNT):
            try:
                g.database = databasePool.get_connection()
                break
            except mysql.connector.Error:
                time.sleep(RETRY_DELAY)
        else:
            raise mysql.connector.Error("Could not get database connection after 3 retries")
    return g.database

def closeDatabaseConnection(error):
    database = g.pop('database', None)
    if database is not None:
        try:
            database.close()
        except:
            pass

# 프로그램 종료 시 모든 연결 정리
def cleanup_connections():
    for cnx in databasePool._cnx_queue.queue:
        try:
            cnx.close()
        except:
            pass

atexit.register(cleanup_connections)

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

# 서버 시작 시 데���터베이스 초기화
initDatabase()
