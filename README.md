# niraaah-in-server

사람인 채용정보 API 서버

## 프로젝트 구조

```
niraaah-in-server/
├── auth/
│   └── authController.py       # 인증 관련 컨트롤러
├── job/
│   └── jobController.py        # 채용정보 관련 컨트롤러
├── static/
│   └── swagger.json           # API 문서
├── user/
│   └── userController.py       # 사용자 관련 컨트롤러
├── utils/
│   ├── dbHelper.py            # DB 유틸리티
│   └── app.py                 # 메인 애플리케이션
└── requirements.txt           # 의존성 패키지 목록
```

## 설치 방법

1. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

2. 환경 변수 설정

- `.env.example` 파일을 참고하여 `.env` 파일 생성

```
PORT=3000
JWT_SECRET=your_secret_key
API_KEY=your_api_key
```

## 실행 방법

1. 개발 모드

```bash
python utils/app.py
```

2. 프로덕션 모드

```bash
nohup python utils/app.py &
```

## API 문서

- Swagger UI: `http://localhost:3000/api-docs`
- API 엔드포인트 목록:
  - GET /api/jobs - 채용 공고 목록 조회
  - GET /api/jobs/{id} - 채용 공고 상세 조회
  - POST /api/search - 채용 공고 검색

## 보안 설정

- 모든 비밀번호는 Base64로 인코딩
- JWT 토큰 만료 시간: 24시간
- API 요청 제한: 분당 100회

## 에러 코드

- 400: 잘못된 요청
- 401: 인증 실패
- 403: 권한 없음
- 404: 리소스 없음
- 500: 서버 에러