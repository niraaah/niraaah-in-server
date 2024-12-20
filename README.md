# niraaah-in-server

사람인 채용정보 API 서버

## 프로젝트 구조

```
niraaah-in-server/
├── auth/
│   └── authController.py       # 인증/로그인 관련 컨트롤러
├── job/
│   └── jobController.py        # 채용정보 관련 컨트롤러
├── application/
│   └── applicationController.py # 지원서 관련 컨트롤러
├── bookmark/
│   └── bookmarkController.py   # 북마크 관련 컨트롤러
├── user/
│   └── userController.py       # 사용자 관련 컨트롤러
├── utils/
│   └── dbHelper.py            # DB 연결 및 테이블 관리
├── static/
│   └── swagger.json           # API 문서
├── app.py                     # 메인 애플리케이션
└── requirements.txt           # 의존성 패키지 목록
```

## 설치 방법

1. 가상환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

2. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

3. 데이터베이스 설정

```python
databaseConfig = {
    "host": "your_db_host",
    "port": your_db_port,
    "user": "your_db_user",
    "password": "your_db_password",
    "database": "your_db_name"
}
```

## 실행 방법

1. 가상환경 활성화 확인
```bash
# 터미널에 (venv)가 표시되어 있는지 확인
# 활성화가 안 되어있다면:
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

2. 개발 모드

```bash
python app.py
```

3. 프로덕션 모드

```bash
gunicorn -w 4 -b 0.0.0.0:10031 app:app
```

## API 엔드포인트

### 인증
- POST /auth/login - 로그인
- POST /auth/refresh - 토큰 갱신
- GET /auth/profile - 내 프로필 조회
- PUT /auth/profile - 프로필 수정

### 채용공고
- GET /jobs - 채용공고 목록 조회
- GET /jobs/{id} - 채용공고 상세 조회
- POST /jobs - 채용공고 등록
- PUT /jobs/{id} - 채용공고 수정
- DELETE /jobs/{id} - 채용공고 삭제

### 지원서
- GET /applications - 지원 내역 조회
- POST /applications - 지원서 제출
- DELETE /applications/{id} - 지원 취소

### 북마크
- GET /bookmarks - 북마크 목록 조회
- POST /bookmarks - 북마크 토글

## 보안 설정

- 비밀번호는 bcrypt로 해싱
- JWT 기반 인증
  - Access Token: 24시간
  - Refresh Token: 30일
- CORS 설정 적용

## 에러 코드

- 400: 잘못된 요청 (유효하지 않은 입력값)
- 401: 인증 실패 (토큰 없음 또는 만료)
- 403: 권한 없음
- 404: 리소스 없음
- 500: 서버 에러

## API 문서

- Swagger UI: `http://your-server:10031/api/docs`
- API 테스트 및 문서 확인 가능