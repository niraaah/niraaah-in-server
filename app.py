from flask import Flask, make_response
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from auth.authController import authBlueprint
from job.jobController import jobBlueprint
from user.userController import userBlueprint
from utils.dbHelper import closeDatabaseConnection

app = Flask(__name__)
CORS(app, 
     resources={r"/*": {"origins": "*"}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://113.198.66.75:10031')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Swagger 설정
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'
swaggerBlueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Job API"}
)

# 블루프린트 등록
app.register_blueprint(swaggerBlueprint, url_prefix=SWAGGER_URL)
app.register_blueprint(authBlueprint, url_prefix='/auth')
app.register_blueprint(jobBlueprint, url_prefix='/jobs')
app.register_blueprint(userBlueprint, url_prefix='/users')

# 데이터베이스 연결 해제를 위한 teardown 함수 등록
@app.teardown_appcontext
def cleanup(error):
    closeDatabaseConnection(error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

