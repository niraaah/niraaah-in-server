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

def createTables():
    database = getDatabaseConnection()
    cursor = database.cursor()
    
    try:
        # 데이터베이스 선택
        cursor.execute("USE wsd3")
        
        # 회사 테이블
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
        
        # 채용 공고 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_postings (
                posting_id INT PRIMARY KEY AUTO_INCREMENT,
                company_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                job_description TEXT NOT NULL,
                experience_level VARCHAR(50),
                education_level VARCHAR(50),
                employment_type VARCHAR(50),
                salary_info VARCHAR(100),
                location_city VARCHAR(100),
                location_district VARCHAR(100),
                deadline_date DATE,
                status VARCHAR(20) DEFAULT 'active',
                view_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        # 직무 카테고리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_categories (
                category_id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 채용 공고-직무 카테고리 연결 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posting_categories (
                posting_id INT,
                category_id INT,
                PRIMARY KEY (posting_id, category_id),
                FOREIGN KEY (posting_id) REFERENCES job_postings(posting_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES job_categories(category_id) ON DELETE CASCADE
            )
        """)
        
        # 기술 스택 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tech_stacks (
                stack_id INT PRIMARY KEY AUTO_INCREMENT,
                stack_name VARCHAR(50) UNIQUE NOT NULL,
                category VARCHAR(50) DEFAULT 'Other'
            )
        """)
        
        # 채용 공고-기술 스택 연결 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posting_tech_stacks (
                posting_id INT,
                stack_id INT,
                PRIMARY KEY (posting_id, stack_id),
                FOREIGN KEY (posting_id) REFERENCES job_postings(posting_id) ON DELETE CASCADE,
                FOREIGN KEY (stack_id) REFERENCES tech_stacks(stack_id) ON DELETE CASCADE
            )
        """)
        
        database.commit()
        print("Tables created successfully")
        
    except Exception as e:
        print(f"Error creating tables: {e}")
        database.rollback()
        raise
    finally:
        cursor.close()
        database.close()

# 서버 시작 시 테이블 생성
createTables()
