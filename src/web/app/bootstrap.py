"""统一注册 Flask 蓝图入口。"""

from app.file_blueprint import bp as file_bp
from contexts.auth.api.blueprint import bp as auth_bp
from contexts.dataset.api.blueprint import bp as dataset_bp
from contexts.dataset.api.snapshot_blueprint import bp as dataset_snapshot_bp
from contexts.model.api.blueprint import bp as model_bp
from contexts.project.api.blueprint import bp as project_bp
from contexts.task.api.blueprint import bp as task_bp
from contexts.annotation.api.blueprint import bp as annotation_bp
from contexts.training.api.blueprint import bp as training_bp
from contexts.video.api.blueprint import bp as video_bp


def register_blueprints(app):
    """把各业务域的蓝图统一挂载到 Flask 应用。"""
    app.register_blueprint(file_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dataset_bp)
    app.register_blueprint(dataset_snapshot_bp)
    app.register_blueprint(model_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(annotation_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(video_bp)
    app.register_blueprint(task_bp)
