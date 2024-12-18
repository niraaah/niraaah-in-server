from datetime import datetime, timedelta
from typing import Optional
import base64
from flask import Blueprint, request, jsonify, g
from jose import JWTError, jwt
import secrets
from utils.dbHelper import getDatabaseConnection

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
    requestData = request.get_json()
    if not requestData:
        return jsonify({"message": "No input data provided"}), 400

    requiredFields = ['email', 'password', 'name']
    if not all(field in requestData for field in requiredFields):
        return jsonify({"message": "Missing required fields"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute("SELECT user_id FROM users WHERE email=%s", (requestData['email'],))
        if cursor.fetchone():
            return jsonify({"message": "Email already registered"}), 400

        hashedPassword = encodePassword(requestData['password'])

        cursor.execute(
            """
            INSERT INTO users(email, username, password_hash, name, phone, birth_date, status) 
            VALUES (%s, %s, %s, %s, %s, %s, 'active')
            """,
            (requestData['email'], requestData['username'], hashedPassword, requestData['name'],
            requestData.get('phone'), requestData.get('birth_date'))
        )
        database.commit()
        userId = cursor.lastrowid

        accessToken = generateAccessToken(data={"sub": str(userId)})
        refreshToken = generateRefreshToken(data={"sub": str(userId)})

        return jsonify({
            "access_token": accessToken,
            "refresh_token": refreshToken,
            "token_type": "bearer"
        })

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()

# Login endpoint
@authBlueprint.route('/login', methods=['POST'])
def loginUser():
    if request.content_type == 'application/x-www-form-urlencoded':
        username = request.form.get('username')
        password = request.form.get('password')
    else:
        requestData = request.get_json()
        if not requestData:
            return jsonify({"message": "Invalid request format"}), 400
        username = requestData.get('username')
        password = requestData.get('password')

    if not username or not password:
        return jsonify({"message": "Missing username or password"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT user_id, password_hash, status FROM users WHERE email=%s",
            (username,)
        )
        userInfo = cursor.fetchone()

        if not userInfo or userInfo['status'] != 'active':
            return jsonify({"message": "Invalid credentials"}), 401

        if not validatePassword(password, userInfo['password_hash']):
            return jsonify({"message": "Invalid credentials"}), 401

        accessToken = generateAccessToken(data={"sub": str(userInfo['user_id'])})
        refreshToken = generateRefreshToken(data={"sub": str(userInfo['user_id'])})

        cursor.execute(
            "UPDATE users SET last_login=NOW() WHERE user_id=%s",
            (userInfo['user_id'],)
        )
        database.commit()

        return jsonify({
            "access_token": accessToken,
            "refresh_token": refreshToken,
            "token_type": "bearer"
        })
    finally:
        cursor.close()

@authBlueprint.route('/refresh', methods=['POST'])
def refreshUserToken():
    requestData = request.get_json()
    if not requestData or 'refresh_token' not in requestData:
        return jsonify({"message": "Refresh token is required"}), 400

    try:
        payload = jwt.decode(requestData['refresh_token'], SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("scope") != "refresh_token":
            return jsonify({"message": "Invalid token type"}), 401

        userId = int(payload.get("sub"))
        database = getDatabaseConnection()
        cursor = database.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT user_id, status FROM users WHERE user_id=%s",
                (userId,)
            )
            userInfo = cursor.fetchone()

            if not userInfo or userInfo['status'] != 'active':
                return jsonify({"message": "User is not active"}), 401

            newAccessToken = generateAccessToken(data={"sub": str(userId)})
            newRefreshToken = generateRefreshToken(data={"sub": str(userId)})

            return jsonify({
                "access_token": newAccessToken,
                "refresh_token": newRefreshToken,
                "token_type": "bearer"
            })

        finally:
            cursor.close()

    except jwt.ExpiredSignatureError:
        return jsonify({"message": "Refresh token has expired"}), 401
    except (jwt.JWTError, ValueError):
        return jsonify({"message": "Invalid refresh token"}), 401
