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
    WHERE jp.status = 'active'
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

@jobBlueprint.route('/<int:jobId>', methods=['GET', 'PUT'], endpoint='job_detail')
@requireAuthentication
def handleJob(jobId):
    if request.method == 'GET':
        return getJobDetail(jobId)
    elif request.method == 'PUT':
        return updateJob(jobId)

def updateJob(jobId):
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        # 먼저 해당 채용공고가 존재하는지 확인
        cursor.execute("SELECT * FROM job_postings WHERE posting_id = %s", (jobId,))
        if not cursor.fetchone():
            return jsonify({"message": "Job not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"message": "No input data provided"}), 400

        # 업데이트할 필드들 준비
        updateFields = []
        values = []

        # 각 필드 검사 및 업데이트 목록에 추가
        if 'title' in data:
            updateFields.append("title = %s")
            values.append(data['title'])
        if 'job_description' in data:
            updateFields.append("job_description = %s")
            values.append(data['job_description'])
        if 'experience_level' in data:
            updateFields.append("experience_level = %s")
            values.append(data['experience_level'])
        if 'education_level' in data:
            updateFields.append("education_level = %s")
            values.append(data['education_level'])
        if 'employment_type' in data:
            updateFields.append("employment_type = %s")
            values.append(data['employment_type'])
        if 'salary_info' in data:
            updateFields.append("salary_info = %s")
            values.append(data['salary_info'])
        if 'deadline_date' in data and data['deadline_date'] != "string":
            try:
                deadline_date = datetime.strptime(data['deadline_date'], '%Y-%m-%d').date()
                updateFields.append("deadline_date = %s")
                values.append(deadline_date)
            except ValueError:
                return jsonify({"message": "Invalid date format"}), 400

        if not updateFields:
            return jsonify({"message": "No fields to update"}), 400

        # 업데이트 쿼리 실행
        query = f"UPDATE job_postings SET {', '.join(updateFields)} WHERE posting_id = %s"
        values.append(jobId)
        
        cursor.execute(query, values)
        database.commit()

        return jsonify({"message": "Job posting updated successfully"})

    except Exception as e:
        database.rollback()
        print(f"Update error: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500
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
        
        posting_id = cursor.lastrowid
        print(f"Created job posting with ID: {posting_id}")
        database.commit()

        # tech_stacks 처리
        if 'tech_stacks' in requestData and requestData['tech_stacks']:
            for stack in requestData['tech_stacks']:
                if stack != "string":  # "string" 값 무시
                    # tech_stack이 존재하는지 확인하고 없으면 생성
                    cursor.execute("SELECT stack_id FROM tech_stacks WHERE name = %s", (stack,))
                    result = cursor.fetchone()
                    if result:
                        stack_id = result['stack_id']
                    else:
                        cursor.execute("INSERT INTO tech_stacks (name) VALUES (%s)", (stack,))
                        stack_id = cursor.lastrowid
                    
                    # job_tech_stacks에 연결
                    cursor.execute(
                        "INSERT INTO job_tech_stacks (posting_id, stack_id) VALUES (%s, %s)",
                        (posting_id, stack_id)
                    )

        # job_categories 처리
        if 'job_categories' in requestData and requestData['job_categories']:
            for category in requestData['job_categories']:
                if category != "string":
                    cursor.execute("SELECT category_id FROM job_categories WHERE name = %s", (category,))
                    result = cursor.fetchone()
                    if result:
                        category_id = result['category_id']
                        cursor.execute(
                            "INSERT INTO job_posting_categories (posting_id, category_id) VALUES (%s, %s)",
                            (posting_id, category_id)
                        )

        database.commit()
        return jsonify({
            "message": "Job posting created successfully",
            "posting_id": posting_id,  # cursor.lastrowid 대신 저장해둔 posting_id 사용
            "company_id": company_id
        }), 201

    except Exception as e:
        database.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()

def getJobDetail(jobId):
    database = getDatabaseConnection()
    cursor = database.cursor(dictionary=True)

    try:
        print(f"Fetching job details for ID: {jobId}")
        
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
        
        print(f"Query result: {job}")

        if not job:
            print(f"No job found with ID: {jobId}")
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
