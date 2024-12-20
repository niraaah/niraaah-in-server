import mysql.connector
from mysql.connector import pooling
from flask import g
import atexit
import time

# 데이터베이스 설정
databaseConfig = {
    "host": "113.198.66.75",  # 실제 DB 서버 주소로 변경
    "port": 10108,            # 실제 포트로 변경
    "user": "admin",
    "password": "qwer1234",
    "database": "wsd3"
}

# 커넥션 풀 설정
poolConfig = {
    "pool_name": "mypool",
    "pool_size": 32,          # 풀 크기 증가
    "pool_reset_session": True,
    "time_to_sleep": 0.1,     # 재시도 간격
    "get_timeout": 3,         # 연결 획득 타임아웃
    **databaseConfig
}

# 커넥션 풀 생성
databasePool = mysql.connector.pooling.MySQLConnectionPool(**poolConfig)

def getDatabaseConnection():
    if 'database' not in g:
        for _ in range(3):  # 최대 3번 재시도
            try:
                g.database = databasePool.get_connection(timeout=poolConfig['get_timeout'])
                break
            except mysql.connector.Error:
                time.sleep(poolConfig['time_to_sleep'])
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
