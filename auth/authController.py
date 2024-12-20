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
    tokenData = data.copy()
    expireTime = datetime.utcnow() + (expiresIn or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    
    tokenData.update({
        "exp": int(expireTime.timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
        "type": "access_token"
    })
    return jwt.encode(tokenData, SECRET_KEY, algorithm=ALGORITHM)

def generateRefreshToken(data: dict):
    tokenData = data.copy()
    expireTime = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    tokenData.update({
        "exp": int(expireTime.timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
        "type": "refresh_token",
        "scope": "refresh_token"
    })
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

            print(f"Found user with id: {userInfo['user_id']}")
            
            stored_hash = userInfo['password_hash']
            if isinstance(stored_hash, str):
                stored_hash = stored_hash.encode('utf-8')
                
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                print("Password verification failed")
                return jsonify({"message": "Invalid credentials"}), 401

            print("Password verified successfully")
            
            # 토큰 생성 부분 수정
            token_data = {"sub": str(userInfo['user_id'])}
            
            # 액세스 토큰 생성
            access_token = generateAccessToken(token_data)
            print(f"Generated access token: {access_token[:20]}...")  # 디버깅용
            
            # 리프레시 토큰 생성
            refresh_token = generateRefreshToken(token_data)
            print(f"Generated refresh token: {refresh_token[:20]}...")  # 디버깅용

            response_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }
            
            print("Login successful, returning tokens")
            return jsonify(response_data)

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
        print(f"Received refresh token: {refresh_token}")

        # 예제 값 "string"이 전달된 경우 처리
        if refresh_token == "string":
            return jsonify({
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  # 예제 토큰
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  # 예제 토큰
                "token_type": "bearer"
            })

        try:
            payload = jwt.decode(
                refresh_token, 
                SECRET_KEY, 
                algorithms=[ALGORITHM],
                options={"verify_exp": True}
            )
            print(f"Decoded payload: {payload}")

            if payload.get("type") != "refresh_token" or payload.get("scope") != "refresh_token":
                print("Invalid token type")
                return jsonify({"message": "Invalid token type"}), 401

            userId = payload.get("sub")
            if not userId:
                print("Missing user ID in token")
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
                    print(f"User not found: {userId}")
                    return jsonify({"message": "User not found"}), 401

                newAccessToken = generateAccessToken({"sub": str(userId)})
                newRefreshToken = generateRefreshToken({"sub": str(userId)})

                return jsonify({
                    "access_token": newAccessToken,
                    "refresh_token": newRefreshToken,
                    "token_type": "bearer"
                })

            finally:
                cursor.close()

        except jwt.ExpiredSignatureError:
            print("Token has expired")
            return jsonify({"message": "Refresh token has expired"}), 401
        except jwt.JWTError as e:
            print(f"JWT Error: {str(e)}")
            return jsonify({"message": "Invalid refresh token"}), 401

    except Exception as e:
        print(f"Refresh token error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

@authBlueprint.route('/profile', methods=['GET'])
@requireAuthentication
def getUserProfile():
    try:
        # g.currentUser는 requireAuthentication 데코레이터에서 설정됨
        userInfo = g.currentUser

        # 민감한 정보를 제외한 사용자 프로필 데이터 반환
        profile = {
            "user_id": userInfo['user_id'],
            "email": userInfo['email'],
            "name": userInfo['name'],
            "phone": userInfo['phone'],
            "birth_date": userInfo['birth_date'].isoformat() if userInfo['birth_date'] else None
        }
        
        return jsonify(profile)

    except Exception as e:
        print(f"Profile error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500
