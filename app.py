from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS

app = Flask(__name__)

CORS(app)

app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/app.db'

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

from routes.auth import auth
from routes.subscriptions import subscriptions
from routes.scanner import scanner

app.register_blueprint(auth)
app.register_blueprint(subscriptions)
app.register_blueprint(scanner)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)