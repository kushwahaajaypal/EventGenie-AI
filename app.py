"""
EventGenie AI - Flask Application Factory
"""
import os
import logging
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from config import get_config
from extensions import db


def create_app(config_override=None):
    """Application factory pattern."""
    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates',
    )

    # Load config
    cfg = config_override or get_config()
    app.config.from_object(cfg)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Fix SQLite path to use instance folder (skip :memory: and absolute paths)
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if (db_uri.startswith('sqlite:///') and
            not db_uri.startswith('sqlite:////') and
            ':memory:' not in db_uri):
        db_name = db_uri.replace('sqlite:///', '')
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, db_name)}"

    # Extensions
    db.init_app(app)
    CORS(app)

    # Logging
    logging.basicConfig(
        level=logging.DEBUG if app.config.get('DEBUG') else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    # Register blueprints
    from routes.events import events_bp
    from routes.tasks import tasks_bp
    app.register_blueprint(events_bp)
    app.register_blueprint(tasks_bp)

    # Health check
    @app.route('/api/health')
    def health():
        api_key = os.getenv('GEMINI_API_KEY', '')
        api_configured = bool(api_key and api_key != 'your_gemini_api_key_here')
        return jsonify({
            'status': 'ok',
            'app': 'EventGenie AI',
            'version': '1.0.0',
            'api_configured': api_configured,
        })

    # Serve frontend
    @app.route('/')
    @app.route('/<path:path>')
    def serve_frontend(path=''):
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.template_folder, 'index.html')

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'error': 'Resource not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'success': False, 'error': 'Method not allowed'}), 405

    @app.errorhandler(413)
    def request_too_large(e):
        return jsonify({'success': False, 'error': 'Request too large'}), 413

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f'Internal error: {e}')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

    # Create tables
    with app.app_context():
        db.create_all()

    return app


# App instance for running directly
app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
