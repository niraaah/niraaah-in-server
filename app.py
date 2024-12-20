from flask import Flask
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from auth.authController import authBlueprint
from job.jobController import jobBlueprint
from user.userController import userBlueprint
from utils.dbHelper import closeDatabaseConnection
from application.applicationController import applicationBlueprint

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Swagger 설정
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'
swaggerBlueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Job API",
        'securityDefinitions': {
            'Bearer': {
                'type': 'apiKey',
                'name': 'Authorization',
                'in': 'header',
                'description': 'Enter your bearer token in the format: Bearer <token>'
            }
        },
        'security': [{'Bearer': []}]
    }
)

# 블루프린트 등록
app.register_blueprint(swaggerBlueprint, url_prefix=SWAGGER_URL)
app.register_blueprint(authBlueprint, url_prefix='/auth')
app.register_blueprint(jobBlueprint, url_prefix='/jobs')
app.register_blueprint(userBlueprint, url_prefix='/users')
app.register_blueprint(applicationBlueprint, url_prefix='/applications')

# 데이터베이스 연결 해제를 위한 teardown 함수 등록
@app.teardown_appcontext
def cleanup(error):
    closeDatabaseConnection(error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

