# -*- coding: utf-8 -*-
"""Web 应用工厂：创建 Flask 实例并注册各功能蓝图。"""
import os

from web import context
from flask import Flask
from flask_cors import CORS

from web import (auth, douyin, brands, competitors, dashboard, analysis, scripts,
                 ad, price_research, trend, intent, trendradar, videos, prompts, pages,
                 comic, ai_clip, aiclip_fetch)


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(context.BASE_DIR, 'templates'),
        static_folder=os.path.join(context.BASE_DIR, 'static'))

    app.secret_key = os.environ.get('SECRET_KEY', 'douyin-spider-internal-secret-key-2026')
    # 开发期模板自动重载。默认 Jinja2 在生产模式**缓存模板**：改了
    # templates/index.html 而不重启容器，页面会继续发旧 HTML ——
    # 实测踩过：新加的 CSS 一条都没加载，DOM（JS 实时生成）全对、样式全缺，
    # 弹窗以普通 div 出现在文档流末尾，看起来像"代码没生效"。
    # 生产部署时设 TEMPLATES_AUTO_RELOAD=0 关掉。
    app.config['TEMPLATES_AUTO_RELOAD'] = os.environ.get(
        'TEMPLATES_AUTO_RELOAD', '1') not in ('0', 'false', 'False', 'no')
    app.jinja_env.auto_reload = app.config['TEMPLATES_AUTO_RELOAD']
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
        comic.bp,
        ai_clip.bp,
        aiclip_fetch.bp,
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

    @app.after_request
    def _no_cache(resp):
        """全局禁用缓存：前端模板/JS 改动后刷新即可见效，避免浏览器展示旧界面。

        注：首次生效需用户强刷一次（旧 HTML 无此头、浏览器启发式缓存可能直接复用），
        之后所有响应都带 no-cache，会强制随请求重新验证。
        """
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
