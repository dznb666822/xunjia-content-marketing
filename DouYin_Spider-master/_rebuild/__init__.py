# -*- coding: utf-8 -*-
"""Web 应用工厂：创建 Flask 实例并注册各功能蓝图。"""
import os

from web import context
from flask import Flask
from flask_cors import CORS

from web import (auth, douyin, brands, competitors, dashboard, analysis, scripts,
                 ad, price_research, trend, intent, trendradar, videos, prompts, pages)


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(context.BASE_DIR, 'templates'),
        static_folder=os.path.join(context.BASE_DIR, 'static'))

    app.secret_key = os.environ.get('SECRET_KEY', 'douyin-spider-internal-secret-key-2026')
    CORS(app, supports_credentials=True)

    blueprints = [
        auth.bp,
        douyin.bp,
        brands.bp,
        competitors.bp,
        dashboard.bp,
        analysis.bp,
        scripts.bp,
        ad.bp,
        price_research.bp,
        trend.bp,
        intent.bp,
        trendradar.bp,
        videos.bp,
        prompts.bp,
        pages.bp,
    ]
    for bp in blueprints:
        app.register_blueprint(bp)

    _register_hooks(app)
    return app


def _register_hooks(app):
    from flask import session
    from services.storage import set_current_user, clear_current_user
    from services import user_auth

    @app.before_request
    def _load_current_user():
        """根据 session 设置当前用户上下文（供 storage 门面做数据隔离）。"""
        user_id = session.get('user_id')
        if user_id:
            user = user_auth.get_user(user_id)
            if user:
                set_current_user(user['id'], user.get('role'))
                return
            clear_current_user()
        else:
            clear_current_user()

    @app.teardown_request
    def _clear_current_user(exc=None):
        clear_current_user()
