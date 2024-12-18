from flask import Flask, g
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from auth.authController import authBlueprint
from job.jobController import jobBlueprint
from user.userController import userBlueprint
from utils.dbHelper import initializeDatabase, closeDatabaseConnection
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
CORS(app)

# MySQL 설정으로 변경
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://admin:qwer1234@113.198.66.75:10108/wsd3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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

# 데이터베이스 초기화
initializeDatabase()

@app.teardown_appcontext
def cleanup(error):
    closeDatabaseConnection(error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

