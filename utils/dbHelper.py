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

def initializeTables(cursor):
    # 기존 테이블 생성 코드...

    # job_categories 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_categories (
            category_id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # job_postings 테이블 생성 (salary_info 컬럼 추가)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_postings (
            posting_id INT PRIMARY KEY AUTO_INCREMENT,
            company_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            job_description TEXT,
            experience_level VARCHAR(50),
            education_level VARCHAR(50),
            employment_type VARCHAR(50),
            salary_info VARCHAR(100),
            location_id INT,
            deadline_date DATE,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(company_id),
            FOREIGN KEY (location_id) REFERENCES locations(location_id)
        )
    """)

    # job_posting_categories 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_posting_categories (
            posting_id INT,
            category_id INT,
            PRIMARY KEY (posting_id, category_id),
            FOREIGN KEY (posting_id) REFERENCES job_postings(posting_id),
            FOREIGN KEY (category_id) REFERENCES job_categories(category_id)
        )
    """)

    # 기본 카테고리 데이터 삽입
    categories = ['신입', '경력', '신입·경력', '경력무관', '인턴', '전문연구요원']
    for category in categories:
        cursor.execute("""
            INSERT IGNORE INTO job_categories (name) 
            VALUES (%s)
        """, (category,))

def getDatabaseConnection():
    try:
        if not hasattr(g, 'mysql_db'):
            g.mysql_db = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            
            # 데이터베이스 연결 시 테이블 초기화
            cursor = g.mysql_db.cursor()
            initializeTables(cursor)
            g.mysql_db.commit()
            cursor.close()
            
        return g.mysql_db
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        raise e

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
