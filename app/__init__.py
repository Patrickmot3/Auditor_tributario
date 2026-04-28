import logging
import os
from flask import Flask
from config import config
from app.extensions import db, migrate, login_manager, csrf


def create_app(config_name=None):
    if config_name is None:
        env = os.environ.get('FLASK_ENV', 'development')
        # Railway define FLASK_ENV=production, mas aceita também "production"
        config_name = env if env in ('development', 'production') else 'development'

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))

    # Criar pasta de uploads
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)

    # Inicializar extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    # Registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.empresa import empresa_bp
    from app.routes.consulta import consulta_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(empresa_bp, url_prefix='/empresas')
    app.register_blueprint(consulta_bp, url_prefix='/consulta')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # Rota raiz
    from flask import redirect, url_for
    @app.route('/')
    def index():
        return redirect(url_for('consulta.individual'))

    # Carregar usuário para Flask-Login
    from app.models.usuario import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    # Registrar comando seed
    from app.commands import register_commands
    register_commands(app)

    # Iniciar scheduler se habilitado
    if app.config.get('SCHEDULER_ENABLED') and not app.debug:
        from app.services.scheduler import start_scheduler
        start_scheduler(app)

    return app
