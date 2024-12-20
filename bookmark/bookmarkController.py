from flask import Blueprint, request, jsonify, g
from utils.dbHelper import getDatabaseConnection
from auth.authController import requireAuthentication

bookmarkBlueprint = Blueprint('bookmark', __name__)

@bookmarkBlueprint.route('/', methods=['GET'])
@requireAuthentication
def listBookmarks():
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        query = """
        SELECT 
            b.*,
            j.title as job_title,
            c.name as company_name
        FROM bookmarks b
        JOIN job_postings j ON b.posting_id = j.posting_id
        JOIN companies c ON j.company_id = c.company_id
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
        """
        
        cursor.execute(query, (g.currentUser['user_id'],))
        bookmarks = cursor.fetchall()
        
        return jsonify({"bookmarks": bookmarks})
    finally:
        cursor.close()

@bookmarkBlueprint.route('/', methods=['POST'])
@requireAuthentication
def toggleBookmark():
    data = request.get_json()
    if not data or 'posting_id' not in data:
        return jsonify({"message": "posting_id is required"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        # 채용공고가 존재하는지 먼저 확인
        cursor.execute(
            "SELECT posting_id FROM job_postings WHERE posting_id = %s AND status != 'deleted'",
            (data['posting_id'],)
        )
        if not cursor.fetchone():
            return jsonify({"message": "Invalid posting_id"}), 400

        # 이미 북마크했는지 확인
        cursor.execute(
            "SELECT * FROM bookmarks WHERE user_id = %s AND posting_id = %s",
            (g.currentUser['user_id'], data['posting_id'])
        )
        existing = cursor.fetchone()

        if existing:
            # 북마크 제거
            cursor.execute(
                "DELETE FROM bookmarks WHERE user_id = %s AND posting_id = %s",
                (g.currentUser['user_id'], data['posting_id'])
            )
            message = "Bookmark removed"
        else:
            # 북마크 추가
            cursor.execute(
                """
                INSERT INTO bookmarks (user_id, posting_id)
                VALUES (%s, %s)
                """,
                (g.currentUser['user_id'], data['posting_id'])
            )
            message = "Bookmark added"

        database.commit()
        return jsonify({"message": message})

    except Exception as e:
        database.rollback()
        print(f"Bookmark error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500
    finally:
        cursor.close() 