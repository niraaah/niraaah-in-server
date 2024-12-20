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
    try:
        # multipart/form-data 처리
        posting_id = request.form.get('posting_id')
        resume_id = request.form.get('resume_id')
        cover_letter = request.form.get('cover_letter', '')
        resume_file = request.files.get('resume_file')

        if not posting_id:
            return jsonify({"message": "posting_id is required"}), 400

        database = getDatabaseConnection()
        cursor = database.cursor(dictionary=True)

        try:
            # 이미 지원한 공고인지 확인
            cursor.execute(
                "SELECT * FROM applications WHERE user_id = %s AND posting_id = %s",
                (g.currentUser['user_id'], posting_id)
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
                (g.currentUser['user_id'], posting_id, cover_letter)
            )
            database.commit()

            # TODO: 이력서 파일 처리 로직 추가
            if resume_file:
                # 파일 저장 로직 구현
                pass

            return jsonify({
                "message": "Application submitted successfully",
                "application_id": cursor.lastrowid
            }), 201

        finally:
            cursor.close()

    except Exception as e:
        print(f"Application error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

@applicationBlueprint.route('/<int:applicationId>', methods=['DELETE'])
@requireAuthentication
def cancelApplication(applicationId):
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        # 지원서가 존재하고 현재 사용자의 것인지 확인
        cursor.execute(
            """
            SELECT * FROM applications 
            WHERE application_id = %s AND user_id = %s
            """,
            (applicationId, g.currentUser['user_id'])
        )
        application = cursor.fetchone()

        if not application:
            return jsonify({"message": "Application not found"}), 404

        if application['status'] == 'cancelled':
            return jsonify({"message": "Application already cancelled"}), 400

        # 지원서 상태 업데이트
        cursor.execute(
            """
            UPDATE applications 
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE application_id = %s
            """,
            (applicationId,)
        )
        database.commit()

        return jsonify({"message": "Application cancelled successfully"})

    except Exception as e:
        database.rollback()
        print(f"Cancel application error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500
    finally:
        cursor.close()