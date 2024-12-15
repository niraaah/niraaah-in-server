from flask import Blueprint, request, jsonify, g
from auth.authController import requireAuthentication
from utils.dbHelper import getDatabaseConnection

userBlueprint = Blueprint('user', __name__)

@userBlueprint.route('/profile', methods=['PUT'])
@requireAuthentication
def updateUserProfile():
    requestData = request.get_json()
    if not requestData:
        return jsonify({"message": "No input data provided"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor()

    try:
        updates = {}
        allowedFields = ['name', 'phone', 'birth_date']

        for field in allowedFields:
            if field in requestData:
                updates[field] = requestData[field]

        if 'current_password' in requestData and 'new_password' in requestData:
            cursor.execute(
                "SELECT password_hash FROM users WHERE user_id = %s",
                (g.currentUser['user_id'],)
            )
            currentHash = cursor.fetchone()[0]

            if not validatePassword(requestData['current_password'], currentHash):
                return jsonify({"message": "Current password is incorrect"}), 400

            updates['password_hash'] = encodePassword(requestData['new_password'])

        if not updates:
            return jsonify({"message": "No valid fields to update"}), 400

        setClause = ", ".join(f"{key} = %s" for key in updates)
        query = f"UPDATE users SET {setClause} WHERE user_id = %s"
        cursor.execute(query, list(updates.values()) + [g.currentUser['user_id']])
        database.commit()

        return jsonify({"message": "Profile updated successfully"})

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()

@userBlueprint.route('/applications', methods=['POST'])
@requireAuthentication
def applyForJob():
    try:
        if request.content_type.startswith('multipart/form-data'):
            postingId = request.form.get('posting_id')
            resumeId = request.form.get('resume_id')
            resumeFile = request.files.get('resume_file')
        else:
            requestData = request.get_json()
            postingId = requestData.get('posting_id')
            resumeId = requestData.get('resume_id')
            resumeFile = None

        if not postingId:
            return jsonify({"message": "Posting ID is required"}), 400

        if not resumeId and not resumeFile:
            return jsonify({"message": "Either resume_id or resume_file must be provided"}), 400

        database = getDatabaseConnection()
        cursor = database.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT application_id FROM applications 
            WHERE user_id=%s AND posting_id=%s
            """,
            (g.currentUser['user_id'], postingId)
        )

        if cursor.fetchone():
            return jsonify({"message": "Already applied for this job posting"}), 400

        if resumeFile:
            if not resumeFile.filename.lower().endswith('.pdf'):
                return jsonify({"message": "Only PDF files are allowed"}), 400

            fileContent = resumeFile.read()
            cursor.execute(
                """
                INSERT INTO resumes(user_id, title, content, is_primary)
                VALUES(%s, %s, %s, 0)
                """,
                (g.currentUser['user_id'], f"Resume {datetime.now()}", fileContent)
            )
            database.commit()
            resumeId = cursor.lastrowid

        if resumeId:
            cursor.execute(
                "SELECT resume_id, user_id FROM resumes WHERE resume_id=%s",
                (resumeId,)
            )
            resume = cursor.fetchone()
            if not resume or resume['user_id'] != g.currentUser['user_id']:
                return jsonify({
                    "message": "Not authorized to use this resume or resume does not exist"
                }), 403

        cursor.execute(
            """
            INSERT INTO applications(user_id, posting_id, resume_id, status)
            VALUES (%s, %s, %s, 'pending')
            """,
            (g.currentUser['user_id'], postingId, resumeId)
        )
        database.commit()
        applicationId = cursor.lastrowid

        return jsonify({
            "message": "Application submitted successfully",
            "application_id": applicationId
        })

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()

@userBlueprint.route('/applications', methods=['GET'])
@requireAuthentication
def listUserApplications():
    statusFilter = request.args.get('status_filter')
    sortByDate = request.args.get('sort_by_date', 'desc')
    pageNumber = int(request.args.get('page', 1))

    query = """
    SELECT a.application_id, a.posting_id, jp.title, a.status, a.applied_at
    FROM applications a
    JOIN job_postings jp ON a.posting_id=jp.posting_id
    WHERE a.user_id=%s
    """
    params = [g.currentUser['user_id']]

    if statusFilter:
        query += " AND a.status=%s"
        params.append(statusFilter)

    if sortByDate == "asc":
        query += " ORDER BY a.applied_at ASC"
    else:
        query += " ORDER BY a.applied_at DESC"

    pageSize = 20
    offset = (pageNumber - 1) * pageSize
    query += f" LIMIT {pageSize} OFFSET {offset}"

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(query, params)
        applications = cursor.fetchall()
        return jsonify(applications)
    finally:
        cursor.close()

@userBlueprint.route('/applications/<int:applicationId>', methods=['DELETE'])
@requireAuthentication
def cancelApplication(applicationId):
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT user_id FROM applications WHERE application_id=%s",
            (applicationId,)
        )
        application = cursor.fetchone()

        if not application:
            return jsonify({"message": "Application not found"}), 404

        if application['user_id'] != g.currentUser['user_id']:
            return jsonify({"message": "Not authorized to cancel this application"}), 403

        cursor.execute(
            "DELETE FROM applications WHERE application_id=%s",
            (applicationId,)
        )
        database.commit()

        return jsonify({"message": "Application cancelled successfully"})

    finally:
        cursor.close()

@userBlueprint.route('/bookmarks', methods=['POST'])
@requireAuthentication
def toggleBookmark():
    requestData = request.get_json()
    if not requestData or 'posting_id' not in requestData:
        return jsonify({"message": "Posting ID is required"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT bookmark_id FROM bookmarks 
            WHERE user_id=%s AND posting_id=%s
            """,
            (g.currentUser['user_id'], requestData['posting_id'])
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "DELETE FROM bookmarks WHERE bookmark_id=%s",
                (existing['bookmark_id'],)
            )
            database.commit()
            return jsonify({"message": "Bookmark removed"})
        else:
            cursor.execute(
                "INSERT INTO bookmarks(user_id, posting_id) VALUES(%s,%s)",
                (g.currentUser['user_id'], requestData['posting_id'])
            )
            database.commit()
            return jsonify({"message": "Bookmark added"})

    finally:
        cursor.close()

@userBlueprint.route('/bookmarks', methods=['GET'])
@requireAuthentication
def listBookmarks():
    pageNumber = int(request.args.get('page', 1))
    sortOrder = request.args.get('sort', 'desc')

    query = """
    SELECT 
        b.bookmark_id, 
        b.posting_id, 
        jp.title,
        jp.job_description,
        jp.experience_level,
        jp.education_level,
        jp.employment_type,
        jp.salary_info,
        CONCAT(l.city, ' ', COALESCE(l.district, '')) as location,
        jp.deadline_date,
        jp.view_count,
        c.name as company_name,
        GROUP_CONCAT(DISTINCT ts.name) as tech_stacks,
        GROUP_CONCAT(DISTINCT jc.name) as job_categories
    FROM bookmarks b
    JOIN job_postings jp ON b.posting_id = jp.posting_id
    JOIN companies c ON jp.company_id = c.company_id
    LEFT JOIN locations l ON jp.location_id = l.location_id
    LEFT JOIN posting_tech_stacks pts ON jp.posting_id = pts.posting_id
    LEFT JOIN tech_stacks ts ON pts.stack_id = ts.stack_id
    LEFT JOIN posting_categories pc ON jp.posting_id = pc.posting_id
    LEFT JOIN job_categories jc ON pc.category_id = jc.category_id
    WHERE b.user_id = %s
    GROUP BY b.bookmark_id
    """

    if sortOrder == "asc":
        query += " ORDER BY b.created_at ASC"
    else:
        query += " ORDER BY b.created_at DESC"

    pageSize = 20
    offset = (pageNumber - 1) * pageSize
    query += f" LIMIT {pageSize} OFFSET {offset}"

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(query, (g.currentUser['user_id'],))
        bookmarks = cursor.fetchall()

        for bookmark in bookmarks:
            if bookmark['tech_stacks']:
                bookmark['tech_stacks'] = bookmark['tech_stacks'].split(',')
            else:
                bookmark['tech_stacks'] = []

            if bookmark['job_categories']:
                bookmark['job_categories'] = bookmark['job_categories'].split(',')
            else:
                bookmark['job_categories'] = []

        return jsonify(bookmarks)
    finally:
        cursor.close()
