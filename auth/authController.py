from datetime import datetime, timedelta
from typing import Optional
import base64
from flask import Blueprint, request, jsonify, g, make_response
from jose import JWTError, jwt
import secrets
from utils.dbHelper import getDatabaseConnection
import bcrypt

authBlueprint = Blueprint('auth', __name__)

SECRET_KEY = secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

def encodePassword(rawPassword: str) -> str:
    return base64.b64encode(rawPassword.encode('utf-8')).decode('utf-8')

def validatePassword(plainPassword: str, encodedPassword: str) -> bool:
    return encodePassword(plainPassword) == encodedPassword

def generateAccessToken(data: dict, expiresIn: Optional[timedelta] = None):
    if "sub" in data and not isinstance(data["sub"], str):
        data["sub"] = str(data["sub"])
    
    tokenData = data.copy()
    if expiresIn:
        expireTime = datetime.now() + expiresIn
    else:
        expireTime = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    tokenData.update({"exp": expireTime})
    return jwt.encode(tokenData, SECRET_KEY, algorithm=ALGORITHM)

def generateRefreshToken(data: dict):
    if "sub" in data and not isinstance(data["sub"], str):
        data["sub"] = str(data["sub"])

    expireTime = datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    tokenData = data.copy()
    tokenData.update({"exp": expireTime, "scope": "refresh_token"})
    return jwt.encode(tokenData, SECRET_KEY, algorithm=ALGORITHM)

def getCurrentUser():
    authHeader = request.headers.get('Authorization')
    if not authHeader or not authHeader.startswith('Bearer '):
        return None

    token = authHeader.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        userId = int(payload.get("sub"))

        database = getDatabaseConnection()
        cursor = database.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_id, email, name, status, phone, birth_date 
            FROM users 
            WHERE user_id=%s
            """,
            (userId,)
        )
        userInfo = cursor.fetchone()
        cursor.close()

        if not userInfo or userInfo['status'] in ['inactive', 'blocked']:
            return None

        return userInfo

    except (JWTError, ValueError):
        return None

def requireAuthentication(f):
    def decoratedFunction(*args, **kwargs):
        userInfo = getCurrentUser()
        if userInfo is None:
            return jsonify({"message": "Authentication required"}), 401
        g.currentUser = userInfo
        return f(*args, **kwargs)
    return decoratedFunction

@authBlueprint.route('/register', methods=['POST'])
def registerUser():
    try:
        requestData = request.get_json()
        
        # 필수 필드 검증
        requiredFields = ['email', 'password', 'name']
        if not all(field in requestData for field in requiredFields):
            return jsonify({"message": "Missing required fields"}), 400

        database = None
        cursor = None
        try:
            database = getDatabaseConnection()
            cursor = database.cursor(dictionary=True)
            
            # 이메일 중복 체크
            cursor.execute("SELECT user_id FROM users WHERE email=%s", (requestData['email'],))
            if cursor.fetchone():
                return jsonify({"message": "Email already exists"}), 409
            
            # 비밀번호 해싱 - salt 생성 및 해싱
            hashedPassword = bcrypt.hashpw(requestData['password'].encode('utf-8'), bcrypt.gensalt())
            
            # users 테이블이 없으면 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT PRIMARY KEY AUTO_INCREMENT,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    phone VARCHAR(20),
                    birth_date DATE,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL
                )
            """)
            
            # 사용자 정보 삽입
            sql = """
                INSERT INTO users (email, username, password_hash, name, phone, birth_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                requestData['email'],
                requestData['email'],
                hashedPassword,
                requestData['name'],
                requestData.get('phone'),
                requestData.get('birth_date'),
                'active'
            )
            
            cursor.execute(sql, values)
            database.commit()
            
            return jsonify({
                "message": "User registered successfully",
                "user_id": cursor.lastrowid
            }), 201
            
        except Exception as e:
            if database:
                database.rollback()
            print(f"Database error: {str(e)}")
            return jsonify({"message": "Internal server error"}), 500
            
        finally:
            if cursor:
                cursor.close()
            
    except Exception as e:
        print(f"Request error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

# Login endpoint
@authBlueprint.route('/login', methods=['POST'])
def loginUser():
    try:
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return jsonify({"message": "Missing username or password"}), 400

        database = getDatabaseConnection()
        cursor = database.cursor(dictionary=True)

        try:
            # 디버깅을 위한 로그 추가
            print(f"Attempting login with username: {username}")
            
            email = username.replace('%40', '@')
            cursor.execute(
                "SELECT user_id, password_hash FROM users WHERE email=%s",
                (email,)
            )
            userInfo = cursor.fetchone()

            if not userInfo:
                print(f"User not found for email: {email}")
                return jsonify({"message": "Invalid credentials"}), 401

            # 디버깅을 위한 로그 추가
            print(f"Found user with id: {userInfo['user_id']}")
            
            # 저장된 해시와 입력된 비밀번호 비교
            stored_hash = userInfo['password_hash']
            if isinstance(stored_hash, str):
                stored_hash = stored_hash.encode('utf-8')
                
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                print("Password verification failed")
                return jsonify({"message": "Invalid credentials"}), 401

            print("Password verified successfully")
            
            # 토큰 생성
            accessToken = generateAccessToken(data={"sub": userInfo['user_id']})
            refreshToken = generateRefreshToken(data={"sub": userInfo['user_id']})

            return jsonify({
                "access_token": accessToken,
                "refresh_token": refreshToken,
                "token_type": "bearer"
            })

        finally:
            cursor.close()

    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

@authBlueprint.route('/refresh', methods=['POST'])
def refreshUserToken():
    try:
        requestData = request.get_json()
        if not requestData or 'refresh_token' not in requestData:
            return jsonify({"message": "Refresh token is required"}), 400

        refresh_token = requestData['refresh_token']
        
        # 디버깅을 위한 로그
        print(f"Received refresh token: {refresh_token}")

        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            print(f"Decoded payload: {payload}")  # 디버깅 로그

            if payload.get("scope") != "refresh_token":
                return jsonify({"message": "Invalid token type"}), 401

            userId = payload.get("sub")
            if not userId:
                return jsonify({"message": "Invalid token payload"}), 401

            database = getDatabaseConnection()
            cursor = database.cursor(dictionary=True)

            try:
                cursor.execute(
                    "SELECT user_id FROM users WHERE user_id=%s",
                    (userId,)
                )
                userInfo = cursor.fetchone()

                if not userInfo:
                    return jsonify({"message": "User not found"}), 401

                # 새 토큰 생성
                newAccessToken = generateAccessToken(data={"sub": userId})
                newRefreshToken = generateRefreshToken(data={"sub": userId})

                return jsonify({
                    "access_token": newAccessToken,
                    "refresh_token": newRefreshToken,
                    "token_type": "bearer"
                })

            finally:
                cursor.close()

        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Refresh token has expired"}), 401
        except jwt.JWTError as e:
            print(f"JWT Error: {str(e)}")  # 디버깅 로그
            return jsonify({"message": "Invalid refresh token"}), 401

    except Exception as e:
        print(f"Refresh token error: {str(e)}")  # 디버깅 로그
        return jsonify({"message": "Internal server error"}), 500
