import mysql.connector
from mysql.connector import pooling
from flask import g

databaseConfig = {
    "host": '113.198.66.75',
    "user": 'admin',
    "password": 'qwer1234',
    "database": 'wsd3',
    "port": 10108 
}

databasePool = pooling.MySQLConnectionPool(
    pool_name="mainPool",
    pool_size=20,
    **databaseConfig
)

def getDatabaseConnection():
    if 'database' not in g:
        g.database = databasePool.get_connection()
    return g.database

def closeDatabaseConnection(error):
    database = g.pop('database', None)
    if database is not None:
        database.close()
        database.disconnect()

def initializeDatabase():
    return databasePool
