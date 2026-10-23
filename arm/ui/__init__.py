"""Main arm ui file"""
import sys  # noqa: F401
import os  # noqa: F401
from getpass import getpass  # noqa: F401
from logging.config import dictConfig
from flask import Flask, logging, current_app  # noqa: F401
from flask.logging import default_handler  # noqa: F401
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_wtf import CSRFProtect
from arm.ripper.logger import short_format

from flask_login import LoginManager
import bcrypt  # noqa: F401
import arm.config.config as cfg
from arm.ui.security import load_or_create_flask_secret_key

sqlitefile = 'sqlite:///' + cfg.arm_config['DBFILE']

# Setup logging, but because of werkzeug issues, we need to set up that later down file
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': short_format,
        'datefmt': cfg.arm_config["DATE_FORMAT"],
    }},
    'handlers': {
        'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        },
        "console": {"class": "logging.StreamHandler"},
        "null": {"class": "logging.NullHandler"},
    },
    'root': {
        'level': cfg.arm_config["LOGLEVEL"],
        'handlers': ['wsgi']
    },
})

app = Flask(__name__)
csrf = CSRFProtect()
csrf.init_app(app)
CORS(app, resources={r"/*": {"origins": "*", "send_wildcard": "False"}})

login_manager = LoginManager()
login_manager.init_app(app)

# Set Flask database connection configurations
app.config['SQLALCHEMY_DATABASE_URI'] = sqlitefile
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Wait for short-lived concurrent SQLite writes instead of failing after the default timeout.
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"connect_args": {"timeout": 30}}
# Use a per-installation random key to prevent forged Flask sessions.
app.config['SECRET_KEY'] = load_or_create_flask_secret_key(cfg.arm_config, cfg.arm_config_path)
# Set the global Flask Login state, set to True will ignore any @login_required
app.config['LOGIN_DISABLED'] = cfg.arm_config['DISABLE_LOGIN']
app.logger.debug(f"Disable Login: {cfg.arm_config['DISABLE_LOGIN']}")
# Do not override Werkzeug's debugger PIN with a known value.

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Register route blueprints
# loaded post database declaration to avoid circular loops
from arm.ui.settings.settings import route_settings  # noqa: E402,F811
from arm.ui.logs.logs import route_logs  # noqa: E402,F811
from arm.ui.auth.auth import route_auth  # noqa: E402,F811
from arm.ui.database.database import route_database  # noqa: E402,F811
from arm.ui.history.history import route_history  # noqa: E402,F811
from arm.ui.jobs.jobs import route_jobs  # noqa: E402,F811
from arm.ui.sendmovies.sendmovies import route_sendmovies  # noqa: E402,F811
from arm.ui.notifications.notifications import route_notifications  # noqa: E402,F811
app.register_blueprint(route_settings)
app.register_blueprint(route_logs)
app.register_blueprint(route_auth)
app.register_blueprint(route_database)
app.register_blueprint(route_history)
app.register_blueprint(route_jobs)
app.register_blueprint(route_sendmovies)
app.register_blueprint(route_notifications)

# Keep JSON/AJAX endpoints separate from browser page blueprints.
from arm.api.routes import route_api  # noqa: E402,F811
app.register_blueprint(route_api)

# Remove GET/page loads from logging
import logging  # noqa: E402,F811
logging.getLogger('werkzeug').setLevel(logging.ERROR)
