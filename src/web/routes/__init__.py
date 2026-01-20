from .project_routes import bp as project_bp
from .dataset_routes import bp as dataset_bp
from .annotation_routes import bp as annotation_bp
from .training_routes import bp as training_bp
from .model_routes import bp as model_bp
from .file_routes import bp as file_bp
from .video_routes import bp as video_bp

def register_blueprints(app):
    app.register_blueprint(project_bp)
    app.register_blueprint(dataset_bp)
    app.register_blueprint(annotation_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(model_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(video_bp)
