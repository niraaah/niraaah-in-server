import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.connectionManager import DatabaseManager

import mysql.connector
from mysql.connector import pooling
from flask import g

databaseConfig = {
    "host": '113.198.66.75',
    "user": 'admin',
    "password": 'qwer1234',
    "database": 'wsd3',
    "port": 19108 
}

databasePool = pooling.MySQLConnectionPool(
    pool_name="mainPool",
    pool_size=5,
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

def initializeDatabase():
    return databasePool
