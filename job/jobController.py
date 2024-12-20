from flask import Blueprint, request, jsonify, g
from datetime import datetime
from auth.authController import requireAuthentication
from utils.dbHelper import getDatabaseConnection

jobBlueprint = Blueprint('job', __name__)

@jobBlueprint.route('/', methods=['GET'], endpoint='list_jobs')
def listJobs():
    searchKeyword = request.args.get('keyword')
    companyName = request.args.get('company')
    employmentType = request.args.get('employment_type')
    positionTitle = request.args.get('position')
    locationId = request.args.get('location_id')
    salaryInfo = request.args.get('salary_info')
    experienceLevel = request.args.get('experience_level')
    sortField = request.args.get('sort_field', 'created_at')
    sortOrder = request.args.get('sort_order', 'desc')
    jobCategories = request.args.getlist('job_categories')
    techStacks = request.args.getlist('tech_stacks')
    pageNumber = int(request.args.get('page', 1))

    query = """
    SELECT DISTINCT
        jp.posting_id,
        jp.title,
        jp.job_description,
        jp.job_link,
        jp.experience_level,
        jp.education_level,
        jp.employment_type,
        jp.salary_info,
        jp.deadline_date,
        c.name as company_name,
        CONCAT(l.city, ' ', COALESCE(l.district, '')) as location,
        GROUP_CONCAT(DISTINCT ts.name) as tech_stacks,
        GROUP_CONCAT(DISTINCT jc.name) as job_categories
    FROM job_postings jp
    LEFT JOIN companies c ON jp.company_id = c.company_id
    LEFT JOIN locations l ON jp.location_id = l.location_id
    LEFT JOIN job_tech_stacks jts ON jp.posting_id = jts.posting_id
    LEFT JOIN tech_stacks ts ON jts.stack_id = ts.stack_id
    LEFT JOIN job_posting_categories jpc ON jp.posting_id = jpc.posting_id
    LEFT JOIN job_categories jc ON jpc.category_id = jc.category_id
    """

    queryParams = []

    if searchKeyword:
        query += " AND (jp.title LIKE %s OR jp.job_description LIKE %s)"
        queryParams.extend([f"%{searchKeyword}%", f"%{searchKeyword}%"])
    if companyName:
        query += " AND c.name LIKE %s"
        queryParams.append(f"%{companyName}%")
    if employmentType:
        query += " AND jp.employment_type = %s"
        queryParams.append(employmentType)
    if positionTitle:
        query += " AND jp.title LIKE %s"
        queryParams.append(f"%{positionTitle}%")
    if locationId:
        query += " AND jp.location_id = %s"
        queryParams.append(locationId)
    if salaryInfo:
        query += " AND jp.salary_info LIKE %s"
        queryParams.append(f"%{salaryInfo}%")
    if experienceLevel:
        query += " AND jp.experience_level = %s"
        queryParams.append(experienceLevel)
    if techStacks:
        query += f" AND ts.name IN ({','.join(['%s'] * len(techStacks))})"
        queryParams.extend(techStacks)
    if jobCategories:
        query += f" AND jc.name IN ({','.join(['%s'] * len(jobCategories))})"
        queryParams.extend(jobCategories)

    query += " GROUP BY jp.posting_id"

    validSortFields = {
        'created_at': 'jp.created_at',
        'view_count': 'jp.view_count',
        'deadline_date': 'jp.deadline_date',
        'title': 'jp.title'
    }

    sortFieldQuery = validSortFields.get(sortField, 'jp.created_at')
    sortDirection = 'DESC' if sortOrder.lower() == 'desc' else 'ASC'
    query += f" ORDER BY {sortFieldQuery} {sortDirection}"

    pageSize = 20
    offset = (pageNumber - 1) * pageSize
    query += f" LIMIT {pageSize} OFFSET {offset}"

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(query, queryParams)
        jobs = cursor.fetchall()

        for job in jobs:
            if job['tech_stacks']:
                job['tech_stacks'] = job['tech_stacks'].split(',')
            else:
                job['tech_stacks'] = []

            if job['job_categories']:
                job['job_categories'] = job['job_categories'].split(',')
            else:
                job['job_categories'] = []

        return jsonify({
            "jobs": jobs,
            "page": pageNumber,
            "page_size": pageSize,
            "sort_field": sortField,
            "sort_order": sortOrder
        })
    finally:
        cursor.close()

@jobBlueprint.route('/<int:jobId>', methods=['GET'], endpoint='get_job_detail')
def getJobDetail(jobId):
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute("UPDATE job_postings SET view_count = view_count + 1 WHERE posting_id = %s", (jobId,))
        database.commit()

        query = """
        SELECT 
            jp.*,
            c.name as company_name,
            l.city,
            l.district,
            GROUP_CONCAT(DISTINCT ts.name) as tech_stacks,
            GROUP_CONCAT(DISTINCT jc.name) as job_categories
        FROM job_postings jp
        JOIN companies c ON jp.company_id = c.company_id
        LEFT JOIN locations l ON jp.location_id = l.location_id
        LEFT JOIN job_tech_stacks jts ON jp.posting_id = jts.posting_id
        LEFT JOIN tech_stacks ts ON jts.stack_id = ts.stack_id
        LEFT JOIN job_posting_categories jpc ON jp.posting_id = jpc.posting_id
        LEFT JOIN job_categories jc ON jpc.category_id = jc.category_id
        WHERE jp.posting_id = %s AND jp.status != 'deleted'
        GROUP BY jp.posting_id
        """

        cursor.execute(query, (jobId,))
        job = cursor.fetchone()

        if not job:
            return jsonify({"message": "Job not found"}), 404

        if job['tech_stacks']:
            job['tech_stacks'] = job['tech_stacks'].split(',')
        else:
            job['tech_stacks'] = []

        if job['job_categories']:
            job['job_categories'] = job['job_categories'].split(',')
        else:
            job['job_categories'] = []

        relatedQuery = """
        SELECT DISTINCT jp.posting_id, jp.title, c.name as company_name
        FROM job_postings jp
        JOIN companies c ON jp.company_id = c.company_id
        LEFT JOIN job_tech_stacks jts ON jp.posting_id = jts.posting_id
        LEFT JOIN tech_stacks ts ON jts.stack_id = ts.stack_id
        WHERE jp.status = 'active' 
        AND jp.posting_id != %s
        AND (jp.company_id = %s 
        OR ts.name IN (SELECT ts2.name 
        FROM job_tech_stacks jts2 
        JOIN tech_stacks ts2 ON jts2.stack_id = ts2.stack_id 
        WHERE jts2.posting_id = %s))
        ORDER BY RAND()
        LIMIT 5
        """

        cursor.execute(relatedQuery, (jobId, job['company_id'], jobId))
        relatedJobs = cursor.fetchall()

        return jsonify({"job": job, "related": relatedJobs})
    finally:
        cursor.close()

@jobBlueprint.route('/<int:jobId>', methods=['PUT'], endpoint='update_job')
@requireAuthentication
def updateJob(jobId):
    requestData = request.get_json()
    if not requestData:
        return jsonify({"message": "No input data provided"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT jp.*, l.city, l.district 
            FROM job_postings jp
            LEFT JOIN locations l ON jp.location_id = l.location_id
            WHERE jp.posting_id = %s
            """,
            (jobId,)
        )
        existingJob = cursor.fetchone()
        if not existingJob:
            return jsonify({"message": "Job posting not found"}), 404

        updates = {}
        updateFields = [
            'title', 'job_description', 'experience_level', 'education_level',
            'employment_type', 'salary_info', 'deadline_date', 'status'
        ]

        for field in updateFields:
            if field in requestData:
                updates[field] = requestData[field]

        if 'location' in requestData:
            cursor.execute(
                """
                SELECT location_id FROM locations 
                WHERE city = %s AND (district = %s OR (district IS NULL AND %s IS NULL))
                """,
                (requestData['location']['city'], requestData['location'].get('district'),
                requestData['location'].get('district'))
            )
            locationResult = cursor.fetchone()

            if locationResult:
                updates['location_id'] = locationResult['location_id']
            else:
                cursor.execute(
                    "INSERT INTO locations (city, district) VALUES (%s, %s)",
                    (requestData['location']['city'], requestData['location'].get('district'))
                )
                updates['location_id'] = cursor.lastrowid

        if updates:
            setClause = ", ".join(f"{key} = %s" for key in updates)
            query = f"UPDATE job_postings SET {setClause} WHERE posting_id = %s"
            cursor.execute(query, list(updates.values()) + [jobId])

        if 'tech_stacks' in requestData:
            cursor.execute("DELETE FROM posting_tech_stacks WHERE posting_id = %s", (jobId,))
            for tech in requestData['tech_stacks']:
                cursor.execute("SELECT stack_id FROM tech_stacks WHERE name = %s", (tech,))
                result = cursor.fetchone()
                if result:
                    stackId = result['stack_id']
                else:
                    cursor.execute(
                        "INSERT INTO tech_stacks (name) VALUES (%s)",
                        (tech,)
                    )
                    stackId = cursor.lastrowid

                cursor.execute(
                    """
                    INSERT INTO posting_tech_stacks (posting_id, stack_id)
                    VALUES (%s, %s)
                    """,
                    (jobId, stackId)
                )

        if 'job_categories' in requestData:
            cursor.execute("DELETE FROM posting_categories WHERE posting_id = %s", (jobId,))
            for category in requestData['job_categories']:
                cursor.execute(
                    "SELECT category_id FROM job_categories WHERE name = %s",
                    (category,)
                )
                result = cursor.fetchone()
                if result:
                    categoryId = result['category_id']
                else:
                    cursor.execute(
                        "INSERT INTO job_categories (name) VALUES (%s)",
                        (category,)
                    )
                    categoryId = cursor.lastrowid

                cursor.execute(
                    """
                    INSERT INTO posting_categories (posting_id, category_id)
                    VALUES (%s, %s)
                    """,
                    (jobId, categoryId)
                )

        database.commit()
        return jsonify({"message": "Job posting updated successfully"})

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()

@jobBlueprint.route('/<int:jobId>', methods=['DELETE'], endpoint='delete_job')
@requireAuthentication
def deleteJob(jobId):
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT status FROM job_postings WHERE posting_id = %s",
            (jobId,)
        )
        job = cursor.fetchone()

        if not job:
            return jsonify({"message": "Job posting not found"}), 404

        if job['status'] == 'deleted':
            return jsonify({"message": "Job posting already deleted"}), 400

        cursor.execute(
            "UPDATE job_postings SET status='deleted' WHERE posting_id=%s",
            (jobId,)
        )
        database.commit()

        return jsonify({"message": "Job posting deleted successfully"})

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()

@jobBlueprint.route('/', methods=['POST'], endpoint='create_job')
@requireAuthentication
def createJob():
    requestData = request.get_json()
    if not requestData:
        return jsonify({"message": "No input data provided"}), 400

    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        # 회사 ID가 0이면 새로운 회사 생성
        company_id = requestData['company_id']
        if company_id == 0:
            # 회사명 중복 체크
            company_name = requestData.get('company_name', 'New Company')  # 회사명이 없으면 기본값 사용
            cursor.execute("SELECT company_id FROM companies WHERE name = %s", (company_name,))
            existing_company = cursor.fetchone()
            
            if existing_company:
                company_id = existing_company['company_id']
            else:
                cursor.execute(
                    "INSERT INTO companies (name) VALUES (%s)",
                    (company_name,)
                )
                company_id = cursor.lastrowid
                database.commit()

        # 날짜 형식 변환
        deadline_date = None
        if 'deadline_date' in requestData and requestData['deadline_date'] != "string":
            try:
                if isinstance(requestData['deadline_date'], str):
                    deadline_date = datetime.strptime(requestData['deadline_date'], '%Y-%m-%d').date()
                else:
                    return jsonify({
                        "message": "deadline_date must be a string in YYYY-MM-DD format"
                    }), 400
            except ValueError:
                return jsonify({
                    "message": "Invalid date format. Please use YYYY-MM-DD format"
                }), 400

        locationId = None
        if 'location' in requestData:
            cursor.execute(
                """
                SELECT location_id FROM locations 
                WHERE city = %s AND (district = %s OR (district IS NULL AND %s IS NULL))
                """,
                (requestData['location']['city'], requestData['location'].get('district'),
                requestData['location'].get('district'))
            )
            locationResult = cursor.fetchone()

            if locationResult:
                locationId = locationResult['location_id']
            else:
                cursor.execute(
                    "INSERT INTO locations (city, district) VALUES (%s, %s)",
                    (requestData['location']['city'], requestData['location'].get('district'))
                )
                locationId = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO job_postings(
                company_id, title, job_description, experience_level,
                education_level, employment_type, salary_info,
                location_id, deadline_date, status, view_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', 0)
            """,
            (company_id, requestData['title'], requestData['job_description'],
            requestData.get('experience_level'), requestData.get('education_level'),
            requestData.get('employment_type'), requestData.get('salary_info'),
            locationId, deadline_date)
        )
        database.commit()

        return jsonify({
            "message": "Job posting created successfully",
            "posting_id": cursor.lastrowid,
            "company_id": company_id
        }), 201

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
