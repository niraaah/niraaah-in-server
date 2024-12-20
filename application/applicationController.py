from flask import Blueprint, request, jsonify, g
from utils.dbHelper import getDatabaseConnection
from auth.authController import requireAuthentication
from datetime import datetime

applicationBlueprint = Blueprint('application', __name__)

@applicationBlueprint.route('/', methods=['GET'])
@requireAuthentication
def listApplications():
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        query = """
        SELECT 
            a.*,
            j.title as job_title,
            c.name as company_name
        FROM applications a
        JOIN job_postings j ON a.posting_id = j.posting_id
        JOIN companies c ON j.company_id = c.company_id
        WHERE a.user_id = %s
        ORDER BY a.created_at DESC
        """
        
        cursor.execute(query, (g.currentUser['user_id'],))
        applications = cursor.fetchall()
        
        return jsonify({"applications": applications})
    finally:
        cursor.close()

@applicationBlueprint.route('/', methods=['POST'])
@requireAuthentication
def createApplication():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400

    required_fields = ['posting_id', 'cover_letter']
    if not all(field in data for field in required_fields):
        return jsonify({"message": "Missing required fields"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        # 이미 지원한 공고인지 확인
        cursor.execute(
            "SELECT * FROM applications WHERE user_id = %s AND posting_id = %s",
            (g.currentUser['user_id'], data['posting_id'])
        )
        if cursor.fetchone():
            return jsonify({"message": "Already applied to this job"}), 400

        # 지원서 생성
        cursor.execute(
            """
            INSERT INTO applications (
                user_id, posting_id, cover_letter, status
            ) VALUES (%s, %s, %s, 'pending')
            """,
            (g.currentUser['user_id'], data['posting_id'], data['cover_letter'])
        )
        database.commit()

        return jsonify({
            "message": "Application submitted successfully",
            "application_id": cursor.lastrowid
        }), 201

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close() 