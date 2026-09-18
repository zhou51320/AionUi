import os
import sys
import uuid
import socket
from datetime import datetime
from functools import wraps
from flask import (
    Blueprint, session, redirect, url_for, request, flash,
    render_template_string, jsonify, send_file, current_app, g
)
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

# WTForms 3.2+ compatibility monkey patch for Flask-Admin
try:
    from flask_admin.contrib.sqla.validators import Unique
    Unique.field_flags = {'unique': True}
except Exception:
    pass

try:
    from flask_admin.form.validators import FieldListInputRequired
    FieldListInputRequired.field_flags = {'required': True}
except Exception:
    pass

import json
from models import db, User, UserConfig, MarketFile, ClientLog, ModelTemplate, AppRelease
from crypto_utils import decrypt_api_key, encrypt_api_key
from config import Config

ALLOWED_CATEGORIES = {
    'assistant': '智能体助手',
    'plugin': '功能插件',
    'mcp': 'MCP扩展',
    'skill': 'Skill技能',
}
ALLOWED_EXTENSIONS = {'zip', 'json', 'yaml', 'yml', 'tar', 'gz'}
ALLOWED_RELEASE_EXTENSIONS = {'exe', 'zip', 'msi', '7z', 'tar', 'gz'}

def get_server_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def format_size(bytes_size):
    if not bytes_size or bytes_size < 1024:
        return f"{bytes_size or 0} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024 * 1024):.2f} MB"

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录 - AionUi 自托管服务端控制台</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-box {
            width: 100%;
            max-width: 420px;
            background: rgba(30, 41, 59, 0.85);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 36px 32px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            color: #f8fafc;
        }
        .logo-row {
            text-align: center;
            margin-bottom: 28px;
        }
        .logo-icon {
            width: 56px;
            height: 56px;
            background: linear-gradient(135deg, #3b82f6, #6366f1);
            border-radius: 14px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 12px;
            box-shadow: 0 8px 20px -4px rgba(59, 130, 246, 0.5);
        }
        .logo-title {
            font-size: 22px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.5px;
        }
        .logo-desc {
            font-size: 13px;
            color: #94a3b8;
            margin-top: 4px;
        }
        .alert {
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
        }
        .alert-error {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #fca5a5;
        }
        .alert-info {
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            color: #93c5fd;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: #cbd5e1;
            margin-bottom: 6px;
        }
        .form-input {
            width: 100%;
            padding: 12px 14px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid #334155;
            border-radius: 8px;
            font-size: 14px;
            color: #f8fafc;
            outline: none;
            transition: all 0.2s;
        }
        .form-input:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
            background: rgba(15, 23, 42, 0.9);
        }
        .btn-submit {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            border: none;
            border-radius: 8px;
            color: #ffffff;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 8px;
            box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.39);
        }
        .btn-submit:hover {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            transform: translateY(-1px);
        }
        .footer-note {
            text-align: center;
            font-size: 12px;
            color: #64748b;
            margin-top: 24px;
        }
    </style>
</head>
<body>
<div class="login-box">
    <div class="logo-row">
        <div class="logo-icon">A</div>
        <div class="logo-title">AionUi 服务端控制台</div>
        <div class="logo-desc">轻量自托管 · 模型分发 · 应用扩展中心</div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ 'error' if category == 'error' else 'info' }}">
                    {{ message }}
                </div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <form method="post" action="{{ url_for('admin.login') }}">
        <input type="hidden" name="next" value="{{ request.args.get('next', '') }}">
        <div class="form-group">
            <label class="form-label">管理员账号</label>
            <input type="text" name="username" class="form-input" placeholder="默认账号: admin" required autofocus>
        </div>
        <div class="form-group">
            <label class="form-label">管理员密码</label>
            <input type="password" name="password" class="form-input" placeholder="默认密码: admin123" required>
        </div>
        <button type="submit" class="btn-submit">立即进入管理控制台</button>
    </form>
    <div class="footer-note">AionUi Self-Hosted Server v1.0.0 (Win7 / Win10 / Linux)</div>
</div>
</body>
</html>
"""

CONSOLE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AionUi 服务端控制台</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --primary-light: #eff6ff;
            --sidebar-bg: #0f172a;
            --sidebar-text: #94a3b8;
            --sidebar-active: #38bdf8;
            --bg-main: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --purple: #8b5cf6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg-main);
            color: var(--text-main);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        /* Sidebar */
        .sidebar {
            width: 250px;
            background: var(--sidebar-bg);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            border-right: 1px solid #1e293b;
        }
        .brand {
            padding: 20px 24px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .brand-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #38bdf8, #2563eb);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 20px;
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
        }
        .brand-text h1 {
            font-size: 16px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.3px;
        }
        .brand-text p {
            font-size: 11px;
            color: #64748b;
        }
        .nav-menu {
            padding: 16px 12px;
            flex: 1;
            overflow-y: auto;
        }
        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 11px 16px;
            border-radius: 8px;
            color: var(--sidebar-text);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            margin-bottom: 4px;
            transition: all 0.15s ease;
            text-decoration: none;
            user-select: none;
        }
        .nav-item:hover {
            background: rgba(255, 255, 255, 0.05);
            color: #f8fafc;
        }
        .nav-item.active {
            background: rgba(56, 189, 248, 0.12);
            color: var(--sidebar-active);
            font-weight: 600;
        }
        .nav-badge {
            margin-left: auto;
            background: rgba(255, 255, 255, 0.1);
            color: #cbd5e1;
            font-size: 11px;
            padding: 2px 7px;
            border-radius: 10px;
        }
        .sidebar-footer {
            padding: 16px 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .user-avatar {
            width: 32px;
            height: 32px;
            background: #334155;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #38bdf8;
            font-weight: 600;
            font-size: 14px;
        }
        .user-name {
            font-size: 13px;
            color: #f1f5f9;
            font-weight: 500;
        }
        .btn-logout {
            color: #94a3b8;
            background: transparent;
            border: none;
            cursor: pointer;
            padding: 6px;
            border-radius: 6px;
            transition: color 0.15s;
            text-decoration: none;
            font-size: 13px;
        }
        .btn-logout:hover { color: #ef4444; }

        /* Main Workspace */
        .workspace {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: #f8fafc;
        }
        .topbar {
            height: 64px;
            background: #ffffff;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 32px;
            flex-shrink: 0;
        }
        .topbar-title {
            font-size: 18px;
            font-weight: 700;
            color: #0f172a;
        }
        .topbar-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .content-area {
            flex: 1;
            padding: 28px 32px;
            overflow-y: auto;
        }

        /* Buttons & Badges */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.15s;
            text-decoration: none;
            line-height: 1.4;
        }
        .btn-primary {
            background: var(--primary);
            color: #ffffff;
        }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-secondary {
            background: #ffffff;
            border-color: var(--border-color);
            color: var(--text-main);
        }
        .btn-secondary:hover { background: #f1f5f9; }
        .btn-danger {
            background: #fee2e2;
            color: #dc2626;
            border-color: #fca5a5;
        }
        .btn-danger:hover { background: #fecaca; }
        .btn-sm { padding: 5px 10px; font-size: 12px; }

        /* Stat Cards */
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 28px;
        }
        .stat-card {
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            position: relative;
        }
        .stat-label {
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--text-main);
        }
        .stat-hint {
            font-size: 12px;
            color: #64748b;
            margin-top: 6px;
        }

        /* Modern Table Card */
        .card {
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            margin-bottom: 24px;
            overflow: hidden;
        }
        .card-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #fafafa;
        }
        .card-title {
            font-size: 15px;
            font-weight: 600;
            color: #1e293b;
        }
        .table-responsive {
            width: 100%;
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13px;
        }
        th {
            background: #f8fafc;
            padding: 12px 18px;
            font-weight: 600;
            color: #475569;
            border-bottom: 1px solid var(--border-color);
        }
        td {
            padding: 14px 18px;
            border-bottom: 1px solid #f1f5f9;
            color: #334155;
            vertical-align: middle;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: #f8fafc; }

        /* Badges */
        .tag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 9px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            line-height: 1.2;
        }
        .tag-blue { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
        .tag-green { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
        .tag-orange { background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; }
        .tag-purple { background: #faf5ff; color: #7e22ce; border: 1px solid #e9d5ff; }
        .tag-gray { background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
        .tag-danger { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }

        /* Category Filter Tabs */
        .filter-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 18px;
            flex-wrap: wrap;
        }
        .filter-tab {
            padding: 7px 16px;
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
            color: var(--text-muted);
            transition: all 0.15s;
            user-select: none;
        }
        .filter-tab:hover { background: #f1f5f9; color: var(--text-main); }
        .filter-tab.active {
            background: var(--primary);
            color: #ffffff;
            border-color: var(--primary);
            font-weight: 500;
        }

        /* Modals */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(4px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 20px;
        }
        .modal-overlay.show { display: flex; }
        .modal-box {
            background: #ffffff;
            border-radius: 14px;
            width: 100%;
            max-width: 520px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            overflow: hidden;
            animation: modalIn 0.2s ease-out;
        }
        .modal-box-lg {
            max-width: 720px;
        }
        @keyframes modalIn {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
        }
        .modal-header {
            padding: 18px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .modal-title { font-size: 16px; font-weight: 700; color: #0f172a; }
        .modal-close {
            background: transparent;
            border: none;
            font-size: 20px;
            color: #94a3b8;
            cursor: pointer;
            line-height: 1;
        }
        .modal-close:hover { color: #0f172a; }
        .modal-body { padding: 24px; max-height: 75vh; overflow-y: auto; }
        .modal-footer {
            padding: 16px 24px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            background: #f8fafc;
        }

        /* Form Inputs */
        .form-row { margin-bottom: 16px; }
        .form-label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: #334155;
            margin-bottom: 6px;
        }
        .form-control {
            width: 100%;
            padding: 9px 12px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 13px;
            color: #0f172a;
            outline: none;
            transition: border-color 0.15s;
        }
        .form-control:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
        }
        .form-select {
            width: 100%;
            padding: 9px 12px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 13px;
            background: #fff;
            outline: none;
        }

        /* Drag & Drop Upload Box */
        .dropzone {
            border: 2px dashed #cbd5e1;
            border-radius: 10px;
            padding: 30px 20px;
            text-align: center;
            background: #f8fafc;
            cursor: pointer;
            transition: all 0.2s;
        }
        .dropzone:hover, .dropzone.dragover {
            border-color: var(--primary);
            background: #eff6ff;
        }
        .dropzone-icon { font-size: 36px; color: #94a3b8; margin-bottom: 8px; }
        .dropzone-text { font-size: 14px; font-weight: 500; color: #334155; }
        .dropzone-hint { font-size: 12px; color: #94a3b8; margin-top: 4px; }
        .file-selected {
            margin-top: 12px;
            padding: 8px 12px;
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
            border-radius: 6px;
            font-size: 13px;
            color: #065f46;
            display: none;
            align-items: center;
            justify-content: space-between;
        }

        /* Toast */
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: #1e293b;
            color: #ffffff;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            z-index: 2000;
            display: none;
            animation: toastIn 0.2s ease-out;
        }
        @keyframes toastIn { from { transform: translateY(-10px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .toast-success { background: #065f46; border: 1px solid #10b981; }
        .toast-error { background: #991b1b; border: 1px solid #ef4444; }

        /* Code Block */
        .code-block {
            background: #0f172a;
            color: #e2e8f0;
            padding: 14px 18px;
            border-radius: 8px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 280px;
            overflow-y: auto;
        }
        .guide-box {
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
        }
        .guide-step {
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
        }
        .step-num {
            width: 32px;
            height: 32px;
            background: var(--primary-light);
            color: var(--primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            flex-shrink: 0;
        }
        .step-content h3 {
            font-size: 15px;
            margin-bottom: 6px;
            color: #0f172a;
        }
        .step-content p {
            font-size: 13px;
            color: #64748b;
            line-height: 1.5;
        }
    </style>
</head>
<body>

<!-- Sidebar -->
<aside class="sidebar">
    <div class="brand">
        <div class="brand-icon">A</div>
        <div class="brand-text">
            <h1>AionUi 服务端</h1>
            <p>Windows 7 兼容便携版</p>
        </div>
    </div>
    <div class="nav-menu">
        <div class="nav-item active" onclick="switchTab('overview')">
            <span>📊</span> 系统概览
        </div>
        <div class="nav-item" onclick="switchTab('users')">
            <span>👥</span> 用户与模型分发
            <span class="nav-badge" id="badge_users">0</span>
        </div>
        <div class="nav-item" onclick="switchTab('templates')">
            <span>🎨</span> 模型模板管理
            <span class="nav-badge" id="badge_templates">0</span>
        </div>
        <div class="nav-item" onclick="switchTab('updates')">
            <span>🚀</span> 版本更新发布
            <span class="nav-badge" id="badge_updates">0</span>
        </div>
        <div class="nav-item" onclick="switchTab('market')">
            <span>🧩</span> 应用与扩展市场
            <span class="nav-badge" id="badge_market">0</span>
        </div>
        <div class="nav-item" onclick="switchTab('logs')">
            <span>📋</span> 客户端日志监控
            <span class="nav-badge" id="badge_logs">0</span>
        </div>
        <div class="nav-item" onclick="switchTab('guide')">
            <span>📖</span> 客户端接入指引
        </div>
    </div>
    <div class="sidebar-footer">
        <div class="user-info">
            <div class="user-avatar">管</div>
            <div class="user-name">{{ session.get('admin_username', 'admin') }}</div>
        </div>
        <a href="{{ url_for('admin.logout') }}" class="btn-logout" title="退出后台">退出</a>
    </div>
</aside>

<!-- Main Workspace -->
<main class="workspace">
    <header class="topbar">
        <div class="topbar-title" id="pageTitle">系统概览</div>
        <div class="topbar-actions" id="topbarActions">
            <!-- Dynamic Actions inserted here -->
        </div>
    </header>

    <div class="content-area">

        <!-- TAB 1: OVERVIEW -->
        <div id="tab_overview" class="tab-pane">
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-label">
                        <span>系统注册用户</span>
                        <span>👥</span>
                    </div>
                    <div class="stat-value" id="stat_user_count">-</div>
                    <div class="stat-hint" id="stat_user_sub">普通用户: - · 管理员: -</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">
                        <span>应用市场资源包</span>
                        <span>🧩</span>
                    </div>
                    <div class="stat-value" id="stat_market_count">-</div>
                    <div class="stat-hint" id="stat_market_sub">助手 · 插件 · MCP · 技能</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">
                        <span>客户端上报日志</span>
                        <span>📋</span>
                    </div>
                    <div class="stat-value" id="stat_log_count">-</div>
                    <div class="stat-hint" id="stat_log_sub" style="color: #ef4444;">错误异常: - 条</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">
                        <span>服务端运行状态</span>
                        <span>🟢</span>
                    </div>
                    <div class="stat-value" style="font-size: 20px; color: #10b981; margin-top: 6px;">正常运行中</div>
                    <div class="stat-hint">Python 3.10 · SQLite 数据库</div>
                </div>
            </div>

            <!-- Server Connection Panel -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">🚀 客户端自托管连接配置信息</div>
                    <button class="btn btn-secondary btn-sm" onclick="copyServerUrl()">复制服务端地址</button>
                </div>
                <div style="padding: 24px;">
                    <p style="font-size: 14px; color: #334155; margin-bottom: 12px;">
                        在局域网内任意计算机上的 <strong>AionUi 桌面客户端</strong> 中，进入「设置」->「自托管服务」即可连接本服务器：
                    </p>
                    <div style="background: #f1f5f9; padding: 14px 18px; border-radius: 8px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                        <div>
                            <div style="font-size: 12px; color: #64748b;">局域网访问地址 (Server Base URL)</div>
                            <div style="font-size: 16px; font-weight: 700; color: #2563eb; font-family: monospace;" id="server_url_display">
                                http://{{ server_ip }}:5000
                            </div>
                        </div>
                        <button class="btn btn-primary btn-sm" onclick="copyServerUrl()">一键复制</button>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 13px; color: #475569;">
                        <div style="background: #fafafa; padding: 12px 16px; border-radius: 6px; border: 1px solid #f1f5f9;">
                            <strong>默认管理员账号：</strong> admin / 密码：admin123
                        </div>
                        <div style="background: #fafafa; padding: 12px 16px; border-radius: 6px; border: 1px solid #f1f5f9;">
                            <strong>默认普通用户账号：</strong> user / 密码：user123
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quick Access -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🧩 最新上传的应用包</div>
                        <a href="javascript:void(0)" onclick="switchTab('market')" style="font-size: 12px; color: var(--primary); text-decoration: none;">查看全部</a>
                    </div>
                    <div id="recent_market_list" style="padding: 12px 20px;">
                        <div style="color: #94a3b8; font-size: 13px; padding: 12px 0;">加载中...</div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🚨 最新客户端错误警告</div>
                        <a href="javascript:void(0)" onclick="switchTab('logs')" style="font-size: 12px; color: var(--primary); text-decoration: none;">查看全部</a>
                    </div>
                    <div id="recent_error_list" style="padding: 12px 20px;">
                        <div style="color: #94a3b8; font-size: 13px; padding: 12px 0;">加载中...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: MARKET HUB -->
        <div id="tab_market" class="tab-pane" style="display: none;">
            <div class="filter-tabs">
                <div class="filter-tab active" onclick="filterCategory('all', this)">全部资源</div>
                <div class="filter-tab" onclick="filterCategory('assistant', this)">🤖 智能体助手</div>
                <div class="filter-tab" onclick="filterCategory('plugin', this)">🔌 功能插件</div>
                <div class="filter-tab" onclick="filterCategory('mcp', this)">🛠️ MCP 扩展</div>
                <div class="filter-tab" onclick="filterCategory('skill', this)">⚡ Skill 技能</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <div class="card-title">应用与扩展包列表</div>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="market_search" class="form-control" style="width: 200px;" placeholder="搜索名称或描述..." oninput="renderMarketTable()">
                        <button class="btn btn-primary" onclick="openModal('uploadModal')">+ 上传新资源包</button>
                    </div>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>资源包名称</th>
                                <th>应用分类</th>
                                <th>文件大小</th>
                                <th>下载量</th>
                                <th>功能说明</th>
                                <th>上传时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="market_table_body">
                            <tr><td colspan="8" style="text-align: center; color: #94a3b8;">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 3: USERS & MODELS -->
        <div id="tab_users" class="tab-pane" style="display: none;">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">用户账号与 AI 模型分发管理</div>
                    <button class="btn btn-primary" onclick="openModal('addUserModal')">+ 添加新用户</button>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>用户名</th>
                                <th>角色</th>
                                <th>状态</th>
                                <th>下发 Base URL</th>
                                <th>默认模型</th>
                                <th>API 密钥状态</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="users_table_body">
                            <tr><td colspan="9" style="text-align: center; color: #94a3b8;">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB: MODEL TEMPLATES -->
        <div id="tab_templates" class="tab-pane" style="display: none;">
            <div style="display: flex; gap: 12px; margin-bottom: 18px; align-items: center; justify-content: space-between;">
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="text" id="template_search" class="form-control" style="width: 260px;" placeholder="搜索模板名称/平台/模型..." oninput="renderTemplatesTable()">
                    <button class="btn btn-secondary" onclick="loadTemplates()">🔄 刷新</button>
                </div>
                <button class="btn btn-primary" onclick="openTemplateModal()">➕ 新建模型模板</button>
            </div>

            <div class="card">
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>模板名称</th>
                                <th>平台协议</th>
                                <th>API Base URL</th>
                                <th>默认模型</th>
                                <th>可用模型列表</th>
                                <th>视觉 / 思考</th>
                                <th>上下文限制</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="templates_table_body">
                            <tr><td colspan="9" style="text-align: center; color: #94a3b8;">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB: APP UPDATES -->
        <div id="tab_updates" class="tab-pane" style="display: none;">
            <div style="display: flex; gap: 12px; margin-bottom: 18px; align-items: center; justify-content: space-between;">
                <div style="font-size: 13px; color: #64748b;">
                    🚀 客户端将自动向本自托管服务检测并下载此处发布的升级包。
                </div>
                <button class="btn btn-primary" onclick="openPublishUpdateModal()">➕ 发布新版本安装包</button>
            </div>

            <div class="card">
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>版本号</th>
                                <th>更新标题</th>
                                <th>安装包文件名</th>
                                <th>文件大小</th>
                                <th>下载次数</th>
                                <th>状态</th>
                                <th>发布时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="updates_table_body">
                            <tr><td colspan="9" style="text-align: center; color: #94a3b8;">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 4: CLIENT LOGS -->
        <div id="tab_logs" class="tab-pane" style="display: none;">
            <div style="display: flex; gap: 12px; margin-bottom: 18px; align-items: center; justify-content: space-between;">
                <div style="display: flex; gap: 10px; align-items: center;">
                    <select id="log_level_filter" class="form-select" style="width: 140px;" onchange="loadLogs()">
                        <option value="">全部级别</option>
                        <option value="ERROR">🚨 ERROR (错误)</option>
                        <option value="WARN">⚠️ WARN (警告)</option>
                        <option value="INFO">ℹ️ INFO (信息)</option>
                        <option value="DEBUG">🐛 DEBUG (调试)</option>
                    </select>
                    <input type="text" id="log_search" class="form-control" style="width: 220px;" placeholder="检索内容/设备..." oninput="renderLogsTable()">
                    <button class="btn btn-secondary" onclick="loadLogs()">🔄 刷新</button>
                </div>
                <button class="btn btn-danger btn-sm" onclick="clearLogs()">🗑️ 清空所有日志</button>
            </div>

            <div class="card">
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>时间</th>
                                <th>级别</th>
                                <th>上报用户</th>
                                <th>客户端环境</th>
                                <th>日志内容概要</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="logs_table_body">
                            <tr><td colspan="7" style="text-align: center; color: #94a3b8;">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 5: CLIENT GUIDE -->
        <div id="tab_guide" class="tab-pane" style="display: none;">
            <div class="guide-box">
                <div class="guide-step">
                    <div class="step-num">1</div>
                    <div class="step-content">
                        <h3>打开 AionUi 桌面客户端</h3>
                        <p>启动 Windows 7 或 Windows 10/11 上的 AionUi 桌面客户端应用程序。</p>
                    </div>
                </div>
                <div class="guide-step">
                    <div class="step-num">2</div>
                    <div class="step-content">
                        <h3>进入设置并配置自托管服务器地址</h3>
                        <p>点击客户端左下角或右上角的「设置」图标 -> 选择「自托管服务端」/「账号体系」，将服务器地址填写为：</p>
                        <div style="background: #f1f5f9; padding: 10px 14px; border-radius: 6px; font-family: monospace; font-size: 14px; color: #2563eb; margin: 8px 0;">
                            http://{{ server_ip }}:5000
                        </div>
                    </div>
                </div>
                <div class="guide-step">
                    <div class="step-num">3</div>
                    <div class="step-content">
                        <h3>登录账号并自动同步模型配置</h3>
                        <p>在客户端输入服务端创建的用户名与密码（例如 <code>admin</code> 或 <code>user</code>）。登录成功后，客户端将自动同步在此后台下发的 API Key、Base URL 及默认模型，无需用户手动逐一配置。</p>
                    </div>
                </div>
                <div class="guide-step">
                    <div class="step-num">4</div>
                    <div class="step-content">
                        <h3>应用市场一键下载插件与 MCP</h3>
                        <p>客户端打开「应用市场」或「AgentHub」即可直接拉取在此后台上传的助手包、插件、MCP 扩展和技能进行离线安装。</p>
                    </div>
                </div>
            </div>
        </div>

    </div>
</main>

<!-- MODAL: UPLOAD MARKET FILE -->
<div class="modal-overlay" id="uploadModal">
    <div class="modal-box">
        <div class="modal-header">
            <div class="modal-title">上传应用扩展包</div>
            <button class="modal-close" onclick="closeModal('uploadModal')">&times;</button>
        </div>
        <form id="uploadForm" onsubmit="submitUpload(event)">
            <div class="modal-body">
                <div class="form-row">
                    <label class="form-label">应用分类 *</label>
                    <select name="category" id="upload_category" class="form-select" required>
                        <option value="assistant">🤖 智能体助手 (Assistant)</option>
                        <option value="plugin">🔌 功能插件 (Plugin)</option>
                        <option value="mcp">🛠️ MCP 扩展服务器 (MCP Tool)</option>
                        <option value="skill">⚡ Skill 技能包 (Skill)</option>
                    </select>
                </div>

                <div class="form-row">
                    <label class="form-label">选择文件 (.zip / .json) *</label>
                    <div class="dropzone" id="dropzone" onclick="document.getElementById('file_input').click()">
                        <div class="dropzone-icon">📦</div>
                        <div class="dropzone-text">点击选择文件，或直接拖拽文件到这里</div>
                        <div class="dropzone-hint">支持 .zip 压缩包、.json / .yaml 配置文件</div>
                        <input type="file" id="file_input" name="file" style="display: none;" accept=".zip,.json,.yaml,.yml,.tar,.gz" onchange="handleFileSelected(this)">
                    </div>
                    <div class="file-selected" id="file_selected_info">
                        <span id="selected_filename">filename.zip</span>
                        <span id="selected_filesize" style="color: #6b7280; font-size: 12px;">0 KB</span>
                    </div>
                </div>

                <div class="form-row">
                    <label class="form-label">描述说明</label>
                    <textarea name="description" id="upload_description" class="form-control" rows="3" placeholder="简要描述该插件、助手或 MCP 扩展的功能..."></textarea>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('uploadModal')">取消</button>
                <button type="submit" class="btn btn-primary" id="btn_upload_submit">开始上传</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL: ADD USER -->
<div class="modal-overlay" id="addUserModal">
    <div class="modal-box">
        <div class="modal-header">
            <div class="modal-title">添加新用户</div>
            <button class="modal-close" onclick="closeModal('addUserModal')">&times;</button>
        </div>
        <form id="addUserForm" onsubmit="submitAddUser(event)">
            <div class="modal-body">
                <div class="form-row">
                    <label class="form-label">用户名 *</label>
                    <input type="text" name="username" class="form-control" placeholder="如: zhangsan" required>
                </div>
                <div class="form-row">
                    <label class="form-label">初始登录密码 *</label>
                    <input type="password" name="password" class="form-control" value="123456" required>
                </div>
                <div class="form-row">
                    <label class="form-label">用户角色</label>
                    <select name="role" class="form-select">
                        <option value="user">普通用户 (user)</option>
                        <option value="admin">管理员 (admin)</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('addUserModal')">取消</button>
                <button type="submit" class="btn btn-primary">确认创建</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL: EDIT MODEL CONFIG -->
<div class="modal-overlay" id="editConfigModal">
    <div class="modal-box modal-box-lg">
        <div class="modal-header">
            <div class="modal-title" id="editConfigTitle">下发模型配置至客户端</div>
            <button class="modal-close" onclick="closeModal('editConfigModal')">&times;</button>
        </div>
        <form id="editConfigForm" onsubmit="submitEditConfig(event)">
            <input type="hidden" id="cfg_user_id" name="user_id">
            <div class="modal-body">
                <div class="form-row" style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 16px;">
                    <label class="form-label" style="margin-bottom: 4px;">⚡ 快捷套用模板预设 (内置预设 + 自定义模板)</label>
                    <select id="cfg_preset_select" class="form-select" onchange="applyTemplateToUserConfig(this.value)">
                        <option value="">-- 选择模板一键填充以下表单 --</option>
                        <optgroup label="系统内置预设">
                            <option value="builtin:deepseek">DeepSeek 官方 (deepseek-chat, deepseek-reasoner)</option>
                            <option value="builtin:openai">OpenAI 官方 (gpt-4o, gpt-4o-mini, o1)</option>
                            <option value="builtin:siliconflow">硅基流动 SiliconFlow (DeepSeek-V3, R1)</option>
                            <option value="builtin:ollama">本地 Ollama (127.0.0.1:11434)</option>
                            <option value="builtin:new-api">OneAPI / NewAPI 统一中转</option>
                        </optgroup>
                        <optgroup label="自定义模板库" id="cfg_custom_templates_group">
                        </optgroup>
                    </select>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div class="form-row">
                        <label class="form-label">供应商平台 (Platform) *</label>
                        <select id="cfg_platform" name="platform" class="form-select" required>
                            <option value="deepseek">DeepSeek</option>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic Claude</option>
                            <option value="gemini">Google Gemini</option>
                            <option value="siliconflow">硅基流动 SiliconFlow</option>
                            <option value="ollama">Ollama 本地服务</option>
                            <option value="new-api">OneAPI / NewAPI 中转</option>
                            <option value="custom">自定义供应商 (Custom)</option>
                        </select>
                    </div>
                    <div class="form-row">
                        <label class="form-label">供应商显示名称</label>
                        <input type="text" id="cfg_provider_name" name="provider_name" class="form-control" placeholder="如: 自托管模型服务">
                    </div>
                </div>

                <div class="form-row">
                    <label class="form-label">API Base URL *</label>
                    <input type="text" id="cfg_base_url" name="base_url" class="form-control" placeholder="如: https://api.deepseek.com/v1" required>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div class="form-row">
                        <label class="form-label">默认主模型 (Model Name) *</label>
                        <input type="text" id="cfg_model_name" name="model_name" class="form-control" placeholder="如: deepseek-chat" required>
                    </div>
                    <div class="form-row">
                        <label class="form-label">可用模型列表 (英文逗号分隔)</label>
                        <input type="text" id="cfg_models" name="models" class="form-control" placeholder="如: deepseek-chat, deepseek-reasoner">
                    </div>
                </div>

                <div class="form-row">
                    <label class="form-label">API 密钥 (API Key)</label>
                    <input type="text" id="cfg_api_key" name="api_key" class="form-control" placeholder="输入明文 Key (若不修改请留空)">
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">由服务端 Fernet 加密存储，仅下发给已授权登录的客户端。</div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 16px;">
                    <div class="form-row" style="margin-bottom: 0;">
                        <label class="form-label" style="font-size: 12px;">模型协议 (Protocol)</label>
                        <select id="cfg_model_protocol" name="model_protocol" class="form-select" style="font-size: 12px;">
                            <option value="openai">OpenAI 协议</option>
                            <option value="anthropic">Anthropic 协议</option>
                            <option value="gemini">Gemini 协议</option>
                        </select>
                    </div>
                    <div class="form-row" style="margin-bottom: 0;">
                        <label class="form-label" style="font-size: 12px;">视觉图片支持</label>
                        <select id="cfg_image_input" name="image_input" class="form-select" style="font-size: 12px;">
                            <option value="auto">自动 (Auto)</option>
                            <option value="supported">支持视觉</option>
                            <option value="unsupported">不支持视觉</option>
                        </select>
                    </div>
                    <div class="form-row" style="margin-bottom: 0;">
                        <label class="form-label" style="font-size: 12px;">深度思考 (Reasoning)</label>
                        <select id="cfg_thought_level" name="thought_level" class="form-select" style="font-size: 12px;">
                            <option value="auto">自动 (Auto)</option>
                            <option value="off">关闭思考</option>
                            <option value="low">低级别思考</option>
                            <option value="medium">中级别思考</option>
                            <option value="high">高级别思考</option>
                        </select>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div class="form-row">
                        <label class="form-label">API 调用模式 (OpenAI Mode)</label>
                        <select id="cfg_openai_api_mode" name="openai_api_mode" class="form-select">
                            <option value="auto">自动 (Auto)</option>
                            <option value="chat_completions">Chat Completions</option>
                            <option value="responses">Responses API</option>
                        </select>
                    </div>
                    <div class="form-row">
                        <label class="form-label">上下文 Token 上限限制</label>
                        <input type="number" id="cfg_context_limit" name="context_limit" class="form-control" placeholder="留空或0表示不限制，如 128000">
                    </div>
                </div>

                <div style="margin-top: 10px; padding: 10px 14px; background: #eff6ff; border-radius: 8px; border: 1px solid #bfdbfe;">
                    <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #1e40af; cursor: pointer;">
                        <input type="checkbox" id="cfg_save_as_template" onchange="document.getElementById('cfg_template_name_box').style.display = this.checked ? 'block' : 'none';">
                        <span>💾 同时将此配置保存为新的自定义模板</span>
                    </label>
                    <div id="cfg_template_name_box" style="display: none; margin-top: 8px;">
                        <input type="text" id="cfg_template_name_input" class="form-control" placeholder="输入模板名称，如: 公司内网 Qwen-72B">
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('editConfigModal')">取消</button>
                <button type="submit" class="btn btn-primary">保存并下发给客户端</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL: MANAGE MODEL TEMPLATE -->
<div class="modal-overlay" id="templateModal">
    <div class="modal-box modal-box-lg">
        <div class="modal-header">
            <div class="modal-title" id="templateModalTitle">新建模型模板</div>
            <button class="modal-close" onclick="closeModal('templateModal')">&times;</button>
        </div>
        <form id="templateForm" onsubmit="submitTemplate(event)">
            <input type="hidden" id="tmpl_id" name="id">
            <div class="modal-body">
                <div class="form-row">
                    <label class="form-label">模板名称 *</label>
                    <input type="text" id="tmpl_name" name="name" class="form-control" placeholder="如: 公司内网 DeepSeek-R1 服务" required>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div class="form-row">
                        <label class="form-label">供应商平台 (Platform) *</label>
                        <select id="tmpl_platform" name="platform" class="form-select" required>
                            <option value="deepseek">DeepSeek</option>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic Claude</option>
                            <option value="gemini">Google Gemini</option>
                            <option value="siliconflow">硅基流动 SiliconFlow</option>
                            <option value="ollama">Ollama 本地服务</option>
                            <option value="new-api">OneAPI / NewAPI 中转</option>
                            <option value="custom">自定义供应商 (Custom)</option>
                        </select>
                    </div>
                    <div class="form-row">
                        <label class="form-label">默认主模型 (Model Name) *</label>
                        <input type="text" id="tmpl_model_name" name="model_name" class="form-control" placeholder="如: deepseek-chat" required>
                    </div>
                </div>

                <div class="form-row">
                    <label class="form-label">API Base URL *</label>
                    <input type="text" id="tmpl_base_url" name="base_url" class="form-control" placeholder="如: https://api.deepseek.com/v1" required>
                </div>

                <div class="form-row">
                    <label class="form-label">可用模型列表 (英文逗号分隔)</label>
                    <input type="text" id="tmpl_models" name="models" class="form-control" placeholder="如: deepseek-chat, deepseek-reasoner">
                </div>

                <div class="form-row">
                    <label class="form-label">预设 API 密钥 (可选)</label>
                    <input type="text" id="tmpl_api_key" name="api_key" class="form-control" placeholder="模板预设密钥，留空表示下发时单独输入">
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 16px;">
                    <div class="form-row" style="margin-bottom: 0;">
                        <label class="form-label" style="font-size: 12px;">模型协议 (Protocol)</label>
                        <select id="tmpl_protocol" name="model_protocol" class="form-select" style="font-size: 12px;">
                            <option value="openai">OpenAI 协议</option>
                            <option value="anthropic">Anthropic 协议</option>
                            <option value="gemini">Gemini 协议</option>
                        </select>
                    </div>
                    <div class="form-row" style="margin-bottom: 0;">
                        <label class="form-label" style="font-size: 12px;">视觉图片支持</label>
                        <select id="tmpl_image_input" name="image_input" class="form-select" style="font-size: 12px;">
                            <option value="auto">自动 (Auto)</option>
                            <option value="supported">支持视觉</option>
                            <option value="unsupported">不支持视觉</option>
                        </select>
                    </div>
                    <div class="form-row" style="margin-bottom: 0;">
                        <label class="form-label" style="font-size: 12px;">深度思考 (Reasoning)</label>
                        <select id="tmpl_thought_level" name="thought_level" class="form-select" style="font-size: 12px;">
                            <option value="auto">自动 (Auto)</option>
                            <option value="off">关闭思考</option>
                            <option value="low">低级别思考</option>
                            <option value="medium">中级别思考</option>
                            <option value="high">高级别思考</option>
                        </select>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div class="form-row">
                        <label class="form-label">API 调用模式</label>
                        <select id="tmpl_openai_api_mode" name="openai_api_mode" class="form-select">
                            <option value="auto">自动 (Auto)</option>
                            <option value="chat_completions">Chat Completions</option>
                            <option value="responses">Responses API</option>
                        </select>
                    </div>
                    <div class="form-row">
                        <label class="form-label">上下文 Token 限制</label>
                        <input type="number" id="tmpl_context_limit" name="context_limit" class="form-control" placeholder="留空或0表示不限制，如 128000">
                    </div>
                </div>

                <div class="form-row" style="margin-bottom: 0;">
                    <label class="form-label">模板描述 / 备注说明</label>
                    <textarea id="tmpl_description" name="description" class="form-control" rows="2" placeholder="填写关于此模板的说明..."></textarea>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('templateModal')">取消</button>
                <button type="submit" class="btn btn-primary">保存模板</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL: PUBLISH APP UPDATE -->
<div class="modal-overlay" id="publishUpdateModal">
    <div class="modal-box">
        <div class="modal-header">
            <div class="modal-title">发布新版本桌面端安装包</div>
            <button class="modal-close" onclick="closeModal('publishUpdateModal')">&times;</button>
        </div>
        <form id="publishUpdateForm" onsubmit="submitPublishUpdate(event)">
            <div class="modal-body">
                <div class="form-row">
                    <label class="form-label">版本号 (SemVer) *</label>
                    <input type="text" id="update_version" name="version" class="form-control" placeholder="如: 2.2.3 或 2.2.4" required>
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">规范版本号，客户端检测到高于当前版本时会提示用户更新。</div>
                </div>
                <div class="form-row">
                    <label class="form-label">更新标题</label>
                    <input type="text" id="update_title" name="title" class="form-control" placeholder="如: AionUi 2.2.3 Windows 7 兼容更新版">
                </div>
                <div class="form-row">
                    <label class="form-label">更新日志 (Markdown 内容)</label>
                    <textarea id="update_changelog" name="changelog" class="form-control" rows="4" placeholder="支持 Markdown 格式，例如：&#10;### 新增功能&#10;- 支持自托管后台更新检测与一键升级&#10;- 支持模型自定义模板管理"></textarea>
                </div>
                <div class="form-row">
                    <label class="form-label">安装包文件 (.exe / .zip / .msi) *</label>
                    <input type="file" id="update_file" name="file" class="form-control" required>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('publishUpdateModal')">取消</button>
                <button type="submit" class="btn btn-primary" id="btn_submit_update">确认发布</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL: EDIT USER STATUS & PASSWORD -->
<div class="modal-overlay" id="editUserModal">
    <div class="modal-box">
        <div class="modal-header">
            <div class="modal-title" id="editUserTitle">修改用户账号信息</div>
            <button class="modal-close" onclick="closeModal('editUserModal')">&times;</button>
        </div>
        <form id="editUserForm" onsubmit="submitEditUser(event)">
            <input type="hidden" id="edit_user_id" name="user_id">
            <div class="modal-body">
                <div class="form-row">
                    <label class="form-label">重置登录密码 (留空则不修改)</label>
                    <input type="password" id="edit_user_password" name="password" class="form-control" placeholder="输入新密码">
                </div>
                <div class="form-row">
                    <label class="form-label">账号角色</label>
                    <select id="edit_user_role" name="role" class="form-select">
                        <option value="user">普通用户 (user)</option>
                        <option value="admin">管理员 (admin)</option>
                    </select>
                </div>
                <div class="form-row">
                    <label class="form-label">账号状态</label>
                    <select id="edit_user_status" name="is_active" class="form-select">
                        <option value="1">🟢 正常启用</option>
                        <option value="0">🔴 禁用该账号</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('editUserModal')">取消</button>
                <button type="submit" class="btn btn-primary">保存修改</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL: VIEW LOG DETAILS -->
<div class="modal-overlay" id="logDetailModal">
    <div class="modal-box" style="max-width: 640px;">
        <div class="modal-header">
            <div class="modal-title">客户端上报日志详情</div>
            <button class="modal-close" onclick="closeModal('logDetailModal')">&times;</button>
        </div>
        <div class="modal-body">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; font-size: 13px;">
                <div><strong>上报时间:</strong> <span id="log_dt_time">-</span></div>
                <div><strong>日志级别:</strong> <span id="log_dt_level">-</span></div>
                <div><strong>上报用户:</strong> <span id="log_dt_user">-</span></div>
                <div><strong>客户端环境:</strong> <span id="log_dt_client">-</span></div>
            </div>
            <label class="form-label">完整日志信息与报错栈:</label>
            <div class="code-block" id="log_dt_message"></div>
        </div>
        <div class="modal-footer">
            <button type="button" class="btn btn-secondary" onclick="closeModal('logDetailModal')">关闭</button>
        </div>
    </div>
</div>

<!-- Floating Toast Notification -->
<div class="toast" id="toast"></div>

<script>
    // State
    let currentCategory = 'all';
    let marketFiles = [];
    let usersData = [];
    let logsData = [];

    // Switch Tabs
    function switchTab(tabName) {
        document.querySelectorAll('.tab-pane').forEach(el => el.style.display = 'none');
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

        const targetPane = document.getElementById('tab_' + tabName);
        if (targetPane) targetPane.style.display = 'block';

        const navMap = {
            'overview': 0,
            'users': 1,
            'templates': 2,
            'updates': 3,
            'market': 4,
            'logs': 5,
            'guide': 6
        };
        const items = document.querySelectorAll('.nav-item');
        if (items[navMap[tabName]]) {
            items[navMap[tabName]].classList.add('active');
        }

        const titleMap = {
            'overview': '系统概览',
            'users': '用户账号与 AI 模型分发',
            'templates': '自定义 AI 模型模板管理',
            'updates': '桌面客户端版本更新管理',
            'market': '应用与扩展市场管理',
            'logs': '客户端日志监控',
            'guide': 'AionUi 客户端接入指引'
        };
        document.getElementById('pageTitle').innerText = titleMap[tabName] || '系统控制台';

        // Load data on switch
        if (tabName === 'overview') loadOverview();
        else if (tabName === 'users') loadUsers();
        else if (tabName === 'templates') loadTemplates();
        else if (tabName === 'updates') loadUpdates();
        else if (tabName === 'market') loadMarket();
        else if (tabName === 'logs') loadLogs();
    }

    // Toast
    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.innerText = message;
        toast.className = 'toast toast-' + type;
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 3000);
    }

    // Modal helpers
    function openModal(id) {
        document.getElementById(id).classList.add('show');
    }
    function closeModal(id) {
        document.getElementById(id).classList.remove('show');
    }

    // Copy server url
    function copyServerUrl() {
        const url = document.getElementById('server_url_display').innerText.trim();
        navigator.clipboard.writeText(url).then(() => {
            showToast('服务端地址已复制到剪贴板！');
        }).catch(() => {
            showToast('复制成功: ' + url);
        });
    }

    // Category Filter
    function filterCategory(cat, btn) {
        currentCategory = cat;
        document.querySelectorAll('.filter-tab').forEach(el => el.classList.remove('active'));
        btn.classList.add('active');
        renderMarketTable();
    }

    function getCategoryBadge(cat) {
        switch(cat) {
            case 'assistant': return '<span class="tag tag-blue">🤖 智能体助手</span>';
            case 'plugin': return '<span class="tag tag-green">🔌 功能插件</span>';
            case 'mcp': return '<span class="tag tag-orange">🛠️ MCP 扩展</span>';
            case 'skill': return '<span class="tag tag-purple">⚡ Skill 技能</span>';
            default: return `<span class="tag tag-gray">${cat}</span>`;
        }
    }

    function formatBytes(bytes) {
        if (!bytes || bytes < 1024) return (bytes || 0) + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    // 1. Overview API
    async function loadOverview() {
        try {
            const res = await fetch('/admin/api/overview');
            const d = await res.json();
            if (d.code === 0) {
                const data = d.data;
                document.getElementById('stat_user_count').innerText = data.user_count;
                document.getElementById('stat_user_sub').innerText = `普通用户: ${data.normal_user_count} · 管理员: ${data.admin_user_count}`;
                document.getElementById('stat_market_count').innerText = data.market_total;
                document.getElementById('stat_market_sub').innerText = `助手: ${data.market_by_category.assistant} · 插件: ${data.market_by_category.plugin} · MCP: ${data.market_by_category.mcp} · 技能: ${data.market_by_category.skill}`;
                document.getElementById('stat_log_count').innerText = data.log_count;
                document.getElementById('stat_log_sub').innerText = `错误异常: ${data.error_log_count} 条`;

                document.getElementById('badge_market').innerText = data.market_total;
                document.getElementById('badge_users').innerText = data.user_count;
                document.getElementById('badge_logs').innerText = data.log_count;

                // Recent market
                const rm = document.getElementById('recent_market_list');
                if (data.recent_market && data.recent_market.length > 0) {
                    rm.innerHTML = data.recent_market.map(m => `
                        <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f1f5f9;">
                            <div>
                                <span style="font-weight: 500; font-size: 13px;">${m.filename}</span>
                                <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">${formatBytes(m.file_size)} · ${m.created_at || ''}</div>
                            </div>
                            ${getCategoryBadge(m.category)}
                        </div>
                    `).join('');
                } else {
                    rm.innerHTML = '<div style="color: #94a3b8; font-size: 13px; padding: 12px 0;">暂无上传资源</div>';
                }

                // Recent errors
                const re = document.getElementById('recent_error_list');
                if (data.recent_errors && data.recent_errors.length > 0) {
                    re.innerHTML = data.recent_errors.map(l => `
                        <div style="padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 12px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                                <span class="tag tag-danger">${l.level}</span>
                                <span style="color: #94a3b8;">${l.created_at || ''}</span>
                            </div>
                            <div style="color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${l.message}</div>
                        </div>
                    `).join('');
                } else {
                    re.innerHTML = '<div style="color: #10b981; font-size: 13px; padding: 12px 0;">🟢 系统稳定，暂无异常日志</div>';
                }
                loadTemplates();
                loadUpdates();
            }
        } catch (e) {
            console.error(e);
        }
    }

    // 2. Market API
    async function loadMarket() {
        try {
            const res = await fetch('/admin/api/market');
            const d = await res.json();
            if (d.code === 0) {
                marketFiles = d.data || [];
                renderMarketTable();
            }
        } catch (e) {
            console.error(e);
        }
    }

    function renderMarketTable() {
        const tbody = document.getElementById('market_table_body');
        const q = (document.getElementById('market_search').value || '').trim().toLowerCase();
        
        let filtered = marketFiles;
        if (currentCategory !== 'all') {
            filtered = filtered.filter(f => f.category === currentCategory);
        }
        if (q) {
            filtered = filtered.filter(f => (f.filename && f.filename.toLowerCase().includes(q)) || (f.description && f.description.toLowerCase().includes(q)));
        }

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #94a3b8; padding: 30px;">暂无匹配的资源包</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(item => `
            <tr>
                <td>#${item.id}</td>
                <td>
                    <div style="font-weight: 600; color: #0f172a;">${item.filename}</div>
                </td>
                <td>${getCategoryBadge(item.category)}</td>
                <td>${formatBytes(item.file_size)}</td>
                <td><span style="font-weight: 600; color: #2563eb;">${item.download_count}</span> 次</td>
                <td style="max-width: 200px; color: #64748b;" title="${item.description || ''}">${item.description || '-'}</td>
                <td style="color: #94a3b8; font-size: 12px;">${item.created_at || '-'}</td>
                <td>
                    <a href="/api/market/download/${item.id}" class="btn btn-secondary btn-sm" title="下载安装包">⬇ 下载</a>
                    <button class="btn btn-danger btn-sm" onclick="deleteMarketFile(${item.id}, '${item.filename}')" title="删除">🗑 删除</button>
                </td>
            </tr>
        `).join('');
    }

    function handleFileSelected(input) {
        if (input.files && input.files[0]) {
            const file = input.files[0];
            document.getElementById('selected_filename').innerText = file.name;
            document.getElementById('selected_filesize').innerText = formatBytes(file.size);
            document.getElementById('file_selected_info').style.display = 'flex';
        }
    }

    async function submitUpload(e) {
        e.preventDefault();
        const fileInput = document.getElementById('file_input');
        if (!fileInput.files || !fileInput.files[0]) {
            alert('请先选择要上传的文件！');
            return;
        }

        const formData = new FormData(document.getElementById('uploadForm'));
        const btn = document.getElementById('btn_upload_submit');
        btn.disabled = true;
        btn.innerText = '正在上传中...';

        try {
            const res = await fetch('/admin/api/market/upload', {
                method: 'POST',
                body: formData
            });
            const d = await res.json();
            if (d.code === 0) {
                showToast('应用扩展包上传成功！');
                closeModal('uploadModal');
                document.getElementById('uploadForm').reset();
                document.getElementById('file_selected_info').style.display = 'none';
                loadMarket();
                loadOverview();
            } else {
                alert('上传失败: ' + d.message);
            }
        } catch (err) {
            alert('上传请求出错: ' + err.message);
        } finally {
            btn.disabled = false;
            btn.innerText = '开始上传';
        }
    }

    async function deleteMarketFile(id, name) {
        if (!confirm(`确定要删除资源包【${name}】吗？删除后客户端将无法下载该文件。`)) return;
        try {
            const res = await fetch(`/admin/api/market/${id}/delete`, { method: 'POST' });
            const d = await res.json();
            if (d.code === 0) {
                showToast('资源包已删除');
                loadMarket();
                loadOverview();
            } else {
                alert('删除失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    // 3. Users API
    async function loadUsers() {
        try {
            const res = await fetch('/admin/api/users');
            const d = await res.json();
            if (d.code === 0) {
                usersData = d.data || [];
                renderUsersTable();
            }
        } catch (e) {
            console.error(e);
        }
    }

    function renderUsersTable() {
        const tbody = document.getElementById('users_table_body');
        if (usersData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #94a3b8; padding: 24px;">暂无用户</td></tr>';
            return;
        }
        tbody.innerHTML = usersData.map(u => {
            const cfg = u.config || {};
            const modelsDesc = Array.isArray(cfg.models) && cfg.models.length > 0 ? cfg.models.join(', ') : (cfg.model_name || '未设置');
            return `
            <tr>
                <td>#${u.id}</td>
                <td><strong style="color: #0f172a;">${u.username}</strong></td>
                <td>${u.role === 'admin' ? '<span class="tag tag-orange">管理员</span>' : '<span class="tag tag-gray">普通用户</span>'}</td>
                <td>${u.is_active ? '<span class="tag tag-green">正常启用</span>' : '<span class="tag tag-danger">已禁用</span>'}</td>
                <td style="font-family: monospace; font-size: 12px; color: #475569;">${cfg.base_url || '<span style="color:#94a3b8;">未配置</span>'}</td>
                <td><span class="tag tag-blue" title="${modelsDesc}">${cfg.model_name || '未设置'}</span></td>
                <td>${cfg.has_api_key ? '<span class="tag tag-green">已配置 (安全加密)</span>' : '<span style="color:#94a3b8; font-size: 12px;">未配置</span>'}</td>
                <td style="color: #94a3b8; font-size: 12px;">${u.created_at || '-'}</td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="openEditConfigModal(${u.id})">⚙️ 下发模型</button>
                    <button class="btn btn-secondary btn-sm" onclick="openEditUserModal(${u.id}, '${u.username}', '${u.role}', ${u.is_active})">🔑 账号权限</button>
                    ${u.username !== 'admin' ? `<button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id}, '${u.username}')">🗑️</button>` : ''}
                </td>
            </tr>
        `;
        }).join('');
    }

    async function submitAddUser(e) {
        e.preventDefault();
        const form = document.getElementById('addUserForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const res = await fetch('/admin/api/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const d = await res.json();
            if (d.code === 0) {
                showToast('用户创建成功！');
                closeModal('addUserModal');
                form.reset();
                loadUsers();
                loadOverview();
            } else {
                alert('创建失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    function openEditConfigModal(userId) {
        const user = usersData.find(x => x.id === userId);
        if (!user) return;
        const cfg = user.config || {};
        document.getElementById('cfg_user_id').value = userId;
        document.getElementById('editConfigTitle').innerText = `配置【${user.username}】的模型分发`;
        document.getElementById('cfg_platform').value = cfg.platform || 'openai';
        document.getElementById('cfg_provider_name').value = cfg.provider_name || '';
        document.getElementById('cfg_base_url').value = cfg.base_url || '';
        document.getElementById('cfg_model_name').value = cfg.model_name || '';
        document.getElementById('cfg_models').value = Array.isArray(cfg.models) ? cfg.models.join(', ') : (cfg.models || '');
        document.getElementById('cfg_api_key').value = '';
        document.getElementById('cfg_model_protocol').value = cfg.model_protocol || 'openai';
        document.getElementById('cfg_image_input').value = cfg.image_input || 'auto';
        document.getElementById('cfg_openai_api_mode').value = cfg.openai_api_mode || 'auto';
        document.getElementById('cfg_thought_level').value = cfg.thought_level || 'auto';
        document.getElementById('cfg_context_limit').value = cfg.context_limit || '';
        document.getElementById('cfg_save_as_template').checked = false;
        document.getElementById('cfg_template_name_box').style.display = 'none';
        document.getElementById('cfg_template_name_input').value = '';
        document.getElementById('cfg_preset_select').value = '';
        updateTemplateDropdown();
        openModal('editConfigModal');
    }

    function applyTemplateToUserConfig(val) {
        if (!val) return;
        if (val.startsWith('builtin:')) {
            const p = val.replace('builtin:', '');
            if (p === 'deepseek') {
                document.getElementById('cfg_platform').value = 'deepseek';
                document.getElementById('cfg_provider_name').value = 'DeepSeek 官方';
                document.getElementById('cfg_base_url').value = 'https://api.deepseek.com/v1';
                document.getElementById('cfg_model_name').value = 'deepseek-chat';
                document.getElementById('cfg_models').value = 'deepseek-chat, deepseek-reasoner';
                document.getElementById('cfg_model_protocol').value = 'openai';
                document.getElementById('cfg_image_input').value = 'auto';
                document.getElementById('cfg_openai_api_mode').value = 'chat_completions';
                document.getElementById('cfg_thought_level').value = 'auto';
                document.getElementById('cfg_context_limit').value = '128000';
            } else if (p === 'openai') {
                document.getElementById('cfg_platform').value = 'openai';
                document.getElementById('cfg_provider_name').value = 'OpenAI 官方';
                document.getElementById('cfg_base_url').value = 'https://api.openai.com/v1';
                document.getElementById('cfg_model_name').value = 'gpt-4o';
                document.getElementById('cfg_models').value = 'gpt-4o, gpt-4o-mini, o1-preview, o3-mini';
                document.getElementById('cfg_model_protocol').value = 'openai';
                document.getElementById('cfg_image_input').value = 'supported';
                document.getElementById('cfg_openai_api_mode').value = 'chat_completions';
                document.getElementById('cfg_thought_level').value = 'auto';
                document.getElementById('cfg_context_limit').value = '128000';
            } else if (p === 'siliconflow') {
                document.getElementById('cfg_platform').value = 'siliconflow';
                document.getElementById('cfg_provider_name').value = '硅基流动 SiliconFlow';
                document.getElementById('cfg_base_url').value = 'https://api.siliconflow.cn/v1';
                document.getElementById('cfg_model_name').value = 'deepseek-ai/DeepSeek-V3';
                document.getElementById('cfg_models').value = 'deepseek-ai/DeepSeek-V3, deepseek-ai/DeepSeek-R1';
                document.getElementById('cfg_model_protocol').value = 'openai';
                document.getElementById('cfg_image_input').value = 'auto';
                document.getElementById('cfg_openai_api_mode').value = 'chat_completions';
                document.getElementById('cfg_thought_level').value = 'auto';
                document.getElementById('cfg_context_limit').value = '64000';
            } else if (p === 'ollama') {
                document.getElementById('cfg_platform').value = 'ollama';
                document.getElementById('cfg_provider_name').value = '本地 Ollama';
                document.getElementById('cfg_base_url').value = 'http://127.0.0.1:11434/v1';
                document.getElementById('cfg_model_name').value = 'qwen2.5:latest';
                document.getElementById('cfg_models').value = 'qwen2.5:latest, llama3.1:latest';
                document.getElementById('cfg_model_protocol').value = 'openai';
                document.getElementById('cfg_image_input').value = 'auto';
                document.getElementById('cfg_openai_api_mode').value = 'chat_completions';
                document.getElementById('cfg_thought_level').value = 'auto';
                document.getElementById('cfg_context_limit').value = '32768';
            } else if (p === 'new-api') {
                document.getElementById('cfg_platform').value = 'new-api';
                document.getElementById('cfg_provider_name').value = 'OneAPI / NewAPI 中转';
                document.getElementById('cfg_base_url').value = 'http://127.0.0.1:3000/v1';
                document.getElementById('cfg_model_name').value = 'gpt-4o';
                document.getElementById('cfg_models').value = 'gpt-4o, claude-3-5-sonnet-20241022, deepseek-chat';
                document.getElementById('cfg_model_protocol').value = 'openai';
                document.getElementById('cfg_image_input').value = 'auto';
                document.getElementById('cfg_openai_api_mode').value = 'chat_completions';
                document.getElementById('cfg_thought_level').value = 'auto';
                document.getElementById('cfg_context_limit').value = '128000';
            }
        } else if (val.startsWith('tmpl:')) {
            const id = parseInt(val.replace('tmpl:', ''));
            const tmpl = templatesData.find(t => t.id === id);
            if (tmpl) {
                document.getElementById('cfg_platform').value = tmpl.platform || 'openai';
                document.getElementById('cfg_provider_name').value = tmpl.name || '';
                document.getElementById('cfg_base_url').value = tmpl.base_url || '';
                document.getElementById('cfg_model_name').value = tmpl.model_name || '';
                document.getElementById('cfg_models').value = Array.isArray(tmpl.models) ? tmpl.models.join(', ') : (tmpl.models || '');
                if (tmpl.api_key) {
                    document.getElementById('cfg_api_key').value = tmpl.api_key;
                }
                document.getElementById('cfg_model_protocol').value = tmpl.model_protocol || 'openai';
                document.getElementById('cfg_image_input').value = tmpl.image_input || 'auto';
                document.getElementById('cfg_openai_api_mode').value = tmpl.openai_api_mode || 'auto';
                document.getElementById('cfg_thought_level').value = tmpl.thought_level || 'auto';
                document.getElementById('cfg_context_limit').value = tmpl.context_limit || '';
            }
        }
    }

    async function submitEditConfig(e) {
        e.preventDefault();
        const userId = document.getElementById('cfg_user_id').value;
        const modelsRaw = document.getElementById('cfg_models').value;
        const modelsList = modelsRaw ? modelsRaw.split(',').map(x => x.trim()).filter(Boolean) : [];
        const saveAsTemplate = document.getElementById('cfg_save_as_template').checked;
        const templateName = document.getElementById('cfg_template_name_input').value;

        const payload = {
            platform: document.getElementById('cfg_platform').value,
            provider_name: document.getElementById('cfg_provider_name').value || '自托管模型服务',
            base_url: document.getElementById('cfg_base_url').value,
            model_name: document.getElementById('cfg_model_name').value,
            models: modelsList,
            api_key: document.getElementById('cfg_api_key').value,
            model_protocol: document.getElementById('cfg_model_protocol').value,
            image_input: document.getElementById('cfg_image_input').value,
            openai_api_mode: document.getElementById('cfg_openai_api_mode').value,
            thought_level: document.getElementById('cfg_thought_level').value,
            context_limit: parseInt(document.getElementById('cfg_context_limit').value || '0') || 0,
            save_as_template: saveAsTemplate,
            template_name: templateName,
        };

        try {
            const res = await fetch(`/admin/api/users/${userId}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await res.json();
            if (d.code === 0) {
                showToast('模型配置已成功保存并下发！');
                closeModal('editConfigModal');
                loadUsers();
                if (saveAsTemplate) loadTemplates();
            } else {
                alert('保存失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    // 4. Model Templates API
    let templatesData = [];

    async function loadTemplates() {
        try {
            const res = await fetch('/admin/api/templates');
            const d = await res.json();
            if (d.code === 0) {
                templatesData = (d.data && d.data.items) ? d.data.items : [];
                renderTemplatesTable();
                updateTemplateDropdown();
                const badge = document.getElementById('badge_templates');
                if (badge) badge.innerText = templatesData.length;
            }
        } catch (e) {
            console.error(e);
        }
    }

    function updateTemplateDropdown() {
        const group = document.getElementById('cfg_custom_templates_group');
        if (!group) return;
        if (templatesData.length === 0) {
            group.innerHTML = '<option disabled>（暂无自定义模板，可在模型模板管理中添加）</option>';
        } else {
            group.innerHTML = templatesData.map(t =>
                `<option value="tmpl:${t.id}">${t.name} (${t.model_name || t.platform})</option>`
            ).join('');
        }
    }

    function renderTemplatesTable() {
        const tbody = document.getElementById('templates_table_body');
        if (!tbody) return;
        const q = (document.getElementById('template_search') ? document.getElementById('template_search').value : '').trim().toLowerCase();
        let list = templatesData;
        if (q) {
            list = list.filter(t =>
                (t.name && t.name.toLowerCase().includes(q)) ||
                (t.platform && t.platform.toLowerCase().includes(q)) ||
                (t.model_name && t.model_name.toLowerCase().includes(q))
            );
        }
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #94a3b8; padding: 24px;">暂无自定义模板，点击右上角新建</td></tr>';
            return;
        }
        tbody.innerHTML = list.map(t => {
            const modelsStr = Array.isArray(t.models) ? t.models.join(', ') : (t.models || '-');
            return `
                <tr>
                    <td>#${t.id}</td>
                    <td><strong style="color: #0f172a;">${t.name}</strong></td>
                    <td><span class="tag tag-blue">${t.platform}</span></td>
                    <td style="font-family: monospace; font-size: 12px; color: #475569;">${t.base_url || '-'}</td>
                    <td><span class="tag tag-green">${t.model_name || '-'}</span></td>
                    <td style="max-width: 180px; font-size: 12px; color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${modelsStr}">${modelsStr}</td>
                    <td style="font-size: 12px;">视觉:${t.image_input || 'auto'} / 思考:${t.thought_level || 'auto'}</td>
                    <td style="font-size: 12px; color: #64748b;">${t.context_limit ? t.context_limit + ' tokens' : '无限制'}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="openTemplateModal(${t.id})">✏️ 编辑</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteTemplate(${t.id}, '${t.name}')">🗑️</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function openTemplateModal(id) {
        const form = document.getElementById('templateForm');
        form.reset();
        if (id) {
            const t = templatesData.find(x => x.id === id);
            if (!t) return;
            document.getElementById('templateModalTitle').innerText = '编辑模型模板';
            document.getElementById('tmpl_id').value = t.id;
            document.getElementById('tmpl_name').value = t.name;
            document.getElementById('tmpl_platform').value = t.platform || 'openai';
            document.getElementById('tmpl_base_url').value = t.base_url || '';
            document.getElementById('tmpl_model_name').value = t.model_name || '';
            document.getElementById('tmpl_models').value = Array.isArray(t.models) ? t.models.join(', ') : (t.models || '');
            document.getElementById('tmpl_api_key').value = t.api_key || '';
            document.getElementById('tmpl_protocol').value = t.model_protocol || 'openai';
            document.getElementById('tmpl_image_input').value = t.image_input || 'auto';
            document.getElementById('tmpl_openai_api_mode').value = t.openai_api_mode || 'auto';
            document.getElementById('tmpl_thought_level').value = t.thought_level || 'auto';
            document.getElementById('tmpl_context_limit').value = t.context_limit || '';
            document.getElementById('tmpl_description').value = t.description || '';
        } else {
            document.getElementById('templateModalTitle').innerText = '新建模型模板';
            document.getElementById('tmpl_id').value = '';
            document.getElementById('tmpl_platform').value = 'deepseek';
            document.getElementById('tmpl_base_url').value = 'https://api.deepseek.com/v1';
            document.getElementById('tmpl_model_name').value = 'deepseek-chat';
            document.getElementById('tmpl_models').value = 'deepseek-chat, deepseek-reasoner';
            document.getElementById('tmpl_protocol').value = 'openai';
            document.getElementById('tmpl_image_input').value = 'auto';
            document.getElementById('tmpl_openai_api_mode').value = 'chat_completions';
            document.getElementById('tmpl_thought_level').value = 'auto';
            document.getElementById('tmpl_context_limit').value = '128000';
        }
        openModal('templateModal');
    }

    async function submitTemplate(e) {
        e.preventDefault();
        const idVal = document.getElementById('tmpl_id').value;
        const modelsRaw = document.getElementById('tmpl_models').value;
        const modelsList = modelsRaw ? modelsRaw.split(',').map(x => x.trim()).filter(Boolean) : [];

        const payload = {
            id: idVal ? parseInt(idVal) : undefined,
            name: document.getElementById('tmpl_name').value.trim(),
            platform: document.getElementById('tmpl_platform').value,
            base_url: document.getElementById('tmpl_base_url').value.trim(),
            model_name: document.getElementById('tmpl_model_name').value.trim(),
            models: modelsList,
            api_key: document.getElementById('tmpl_api_key').value.trim(),
            model_protocol: document.getElementById('tmpl_protocol').value,
            image_input: document.getElementById('tmpl_image_input').value,
            openai_api_mode: document.getElementById('tmpl_openai_api_mode').value,
            thought_level: document.getElementById('tmpl_thought_level').value,
            context_limit: parseInt(document.getElementById('tmpl_context_limit').value || '0') || 0,
            description: document.getElementById('tmpl_description').value.trim(),
        };

        try {
            const res = await fetch('/admin/api/templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await res.json();
            if (d.code === 0) {
                showToast('模型模板保存成功！');
                closeModal('templateModal');
                loadTemplates();
            } else {
                alert('保存模板失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    async function deleteTemplate(id, name) {
        if (!confirm(`确定要删除模型模板【${name}】吗？`)) return;
        try {
            const res = await fetch(`/admin/api/templates/${id}/delete`, { method: 'POST' });
            const d = await res.json();
            if (d.code === 0) {
                showToast('模板已删除');
                loadTemplates();
            } else {
                alert('删除失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    // 5. App Updates API
    let updatesData = [];

    async function loadUpdates() {
        try {
            const res = await fetch('/admin/api/releases');
            const d = await res.json();
            if (d.code === 0) {
                updatesData = (d.data && d.data.items) ? d.data.items : [];
                renderUpdatesTable();
                const badge = document.getElementById('badge_updates');
                if (badge) badge.innerText = updatesData.length;
            }
        } catch (e) {
            console.error(e);
        }
    }

    function renderUpdatesTable() {
        const tbody = document.getElementById('updates_table_body');
        if (!tbody) return;
        if (updatesData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #94a3b8; padding: 24px;">暂无发布的版本安装包，点击右上角发布</td></tr>';
            return;
        }
        tbody.innerHTML = updatesData.map(u => `
            <tr>
                <td>#${u.id}</td>
                <td><strong style="color: #2563eb; font-size: 14px;">v${u.version}</strong></td>
                <td style="font-weight: 600; color: #0f172a;">${u.title || '-'}</td>
                <td style="font-family: monospace; font-size: 12px;">${u.filename}</td>
                <td>${formatBytes(u.file_size)}</td>
                <td><span style="font-weight: 600; color: #10b981;">${u.download_count}</span> 次</td>
                <td>${u.is_active ? '<span class="tag tag-green">已启用 (可检测更新)</span>' : '<span class="tag tag-gray">已停用</span>'}</td>
                <td style="color: #94a3b8; font-size: 12px;">${u.created_at || '-'}</td>
                <td>
                    <a href="/api/update/download/${u.id}" class="btn btn-secondary btn-sm" title="下载安装包">⬇️ 下载</a>
                    <button class="btn btn-secondary btn-sm" onclick="toggleReleaseStatus(${u.id})">${u.is_active ? '⏸️ 下架' : '▶️ 上架'}</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteRelease(${u.id}, 'v${u.version}')">🗑️</button>
                </td>
            </tr>
        `).join('');
    }

    function openPublishUpdateModal() {
        document.getElementById('publishUpdateForm').reset();
        openModal('publishUpdateModal');
    }

    async function submitPublishUpdate(e) {
        e.preventDefault();
        const fileInput = document.getElementById('update_file');
        if (!fileInput.files || !fileInput.files[0]) {
            alert('请选择安装包文件！');
            return;
        }

        const formData = new FormData(document.getElementById('publishUpdateForm'));
        const btn = document.getElementById('btn_submit_update');
        btn.disabled = true;
        btn.innerText = '正在上传发布中...';

        try {
            const res = await fetch('/admin/api/releases/upload', {
                method: 'POST',
                body: formData
            });
            const d = await res.json();
            if (d.code === 0) {
                showToast('更新包发布成功！客户端可直接检测更新。');
                closeModal('publishUpdateModal');
                loadUpdates();
            } else {
                alert('发布失败: ' + d.message);
            }
        } catch (err) {
            alert('上传出错: ' + err.message);
        } finally {
            btn.disabled = false;
            btn.innerText = '确认发布';
        }
    }

    async function toggleReleaseStatus(id) {
        try {
            const res = await fetch(`/admin/api/releases/${id}/toggle`, { method: 'POST' });
            const d = await res.json();
            if (d.code === 0) {
                showToast(d.message);
                loadUpdates();
            } else {
                alert('操作失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    async function deleteRelease(id, version) {
        if (!confirm(`确定要删除版本【${version}】吗？删除后客户端将无法下载该版本。`)) return;
        try {
            const res = await fetch(`/admin/api/releases/${id}/delete`, { method: 'POST' });
            const d = await res.json();
            if (d.code === 0) {
                showToast('版本已删除');
                loadUpdates();
            } else {
                alert('删除失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    function openEditUserModal(userId, username, role, isActive) {
        document.getElementById('edit_user_id').value = userId;
        document.getElementById('editUserTitle').innerText = `修改用户【${username}】`;
        document.getElementById('edit_user_password').value = '';
        document.getElementById('edit_user_role').value = role;
        document.getElementById('edit_user_status').value = isActive ? '1' : '0';
        openModal('editUserModal');
    }

    async function submitEditUser(e) {
        e.preventDefault();
        const userId = document.getElementById('edit_user_id').value;
        const payload = {
            password: document.getElementById('edit_user_password').value,
            role: document.getElementById('edit_user_role').value,
            is_active: document.getElementById('edit_user_status').value === '1'
        };

        try {
            const res = await fetch(`/admin/api/users/${userId}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await res.json();
            if (d.code === 0) {
                showToast('用户账号信息已更新！');
                closeModal('editUserModal');
                loadUsers();
            } else {
                alert('更新失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    async function deleteUser(userId, username) {
        if (!confirm(`确定要彻底删除用户【${username}】吗？`)) return;
        try {
            const res = await fetch(`/admin/api/users/${userId}/delete`, { method: 'POST' });
            const d = await res.json();
            if (d.code === 0) {
                showToast('用户已删除');
                loadUsers();
                loadOverview();
            } else {
                alert('删除失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    // 4. Logs API
    async function loadLogs() {
        const level = document.getElementById('log_level_filter').value;
        try {
            const res = await fetch(`/admin/api/logs?level=${encodeURIComponent(level)}`);
            const d = await res.json();
            if (d.code === 0) {
                logsData = d.data.items || [];
                renderLogsTable();
            }
        } catch (e) {
            console.error(e);
        }
    }

    function renderLogsTable() {
        const tbody = document.getElementById('logs_table_body');
        const q = (document.getElementById('log_search').value || '').trim().toLowerCase();

        let filtered = logsData;
        if (q) {
            filtered = filtered.filter(l => (l.message && l.message.toLowerCase().includes(q)) || (l.username && l.username.toLowerCase().includes(q)) || (l.client_info && l.client_info.toLowerCase().includes(q)));
        }

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 24px;">暂无日志数据</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(l => {
            let badge = `<span class="tag tag-gray">${l.level}</span>`;
            if (l.level === 'ERROR') badge = `<span class="tag tag-danger">🚨 ERROR</span>`;
            else if (l.level === 'WARN') badge = `<span class="tag tag-orange">⚠️ WARN</span>`;
            else if (l.level === 'INFO') badge = `<span class="tag tag-blue">ℹ️ INFO</span>`;

            return `
                <tr>
                    <td>#${l.id}</td>
                    <td style="color: #64748b; font-size: 12px; white-space: nowrap;">${l.created_at || '-'}</td>
                    <td>${badge}</td>
                    <td><strong>${l.username || '匿名/未登录'}</strong></td>
                    <td style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #94a3b8;" title="${l.client_info || ''}">${l.client_info || 'Win7 Desktop'}</td>
                    <td style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #334155;">${l.message}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="showLogDetail(${l.id})">详情</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function showLogDetail(logId) {
        const log = logsData.find(x => x.id === logId);
        if (!log) return;

        document.getElementById('log_dt_time').innerText = log.created_at || '-';
        document.getElementById('log_dt_level').innerText = log.level;
        document.getElementById('log_dt_user').innerText = log.username || '匿名/未登录';
        document.getElementById('log_dt_client').innerText = log.client_info || '无';
        document.getElementById('log_dt_message').innerText = log.message;

        openModal('logDetailModal');
    }

    async function clearLogs() {
        if (!confirm('确定要清空全部客户端上报的日志吗？')) return;
        try {
            const res = await fetch('/admin/api/logs/clear', { method: 'POST' });
            const d = await res.json();
            if (d.code === 0) {
                showToast('客户端日志已成功清空！');
                loadLogs();
                loadOverview();
            } else {
                alert('清空失败: ' + d.message);
            }
        } catch (e) {
            alert('请求出错: ' + e.message);
        }
    }

    // Init
    document.addEventListener('DOMContentLoaded', () => {
        loadOverview();
    });
</script>
</body>
</html>
"""

class SecureAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return session.get('is_admin', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin.login', next=request.url))

    def _handle_view(self, name, **kwargs):
        # 允许直接访问登录与登出接口，防止未登录时陷入死循环重定向
        if name in ('login', 'logout'):
            return None
        if not self.is_accessible():
            return self.inaccessible_callback(name, **kwargs)

    @expose('/')
    def index(self):
        server_ip = get_server_ip()
        return render_template_string(CONSOLE_HTML, server_ip=server_ip)

    @expose('/login', methods=['GET', 'POST'])
    def login(self):
        if session.get('is_admin', False):
            return redirect(url_for('admin.index'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if user.role == 'admin' and user.is_active:
                    session['is_admin'] = True
                    session['admin_user_id'] = user.id
                    session['admin_username'] = user.username
                    next_url = request.args.get('next') or request.form.get('next')
                    if not next_url or '/admin/login' in next_url:
                        next_url = url_for('admin.index')
                    return redirect(next_url)
                else:
                    flash('该账号没有管理员权限或已被禁用', 'error')
            else:
                flash('用户名或密码错误', 'error')
        return render_template_string(LOGIN_HTML)

    @expose('/logout')
    def logout(self):
        session.pop('is_admin', None)
        session.pop('admin_user_id', None)
        session.pop('admin_username', None)
        return redirect(url_for('admin.login'))


# --- Admin API Blueprint for Web Console ---
admin_api_bp = Blueprint('admin_web_api', __name__, url_prefix='/admin/api')

def admin_api_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin', False):
            return jsonify({'code': 401, 'message': '未登录或非管理员'}), 401
        return f(*args, **kwargs)
    return decorated

@admin_api_bp.route('/overview', methods=['GET'])
@admin_api_auth
def get_overview():
    user_count = User.query.count()
    admin_count = User.query.filter_by(role='admin').count()
    normal_count = user_count - admin_count
    
    market_total = MarketFile.query.count()
    m_assistant = MarketFile.query.filter_by(category='assistant').count()
    m_plugin = MarketFile.query.filter_by(category='plugin').count()
    m_mcp = MarketFile.query.filter_by(category='mcp').count()
    m_skill = MarketFile.query.filter_by(category='skill').count()

    log_count = ClientLog.query.count()
    error_log_count = ClientLog.query.filter_by(level='ERROR').count()

    recent_market = MarketFile.query.order_by(MarketFile.created_at.desc()).limit(5).all()
    recent_errors = ClientLog.query.filter_by(level='ERROR').order_by(ClientLog.created_at.desc()).limit(5).all()

    return jsonify({
        'code': 0,
        'data': {
            'user_count': user_count,
            'admin_user_count': admin_count,
            'normal_user_count': normal_count,
            'market_total': market_total,
            'market_by_category': {
                'assistant': m_assistant,
                'plugin': m_plugin,
                'mcp': m_mcp,
                'skill': m_skill,
            },
            'log_count': log_count,
            'error_log_count': error_log_count,
            'recent_market': [m.to_dict() for m in recent_market],
            'recent_errors': [e.to_dict() for e in recent_errors],
        }
    })

@admin_api_bp.route('/users', methods=['GET'])
@admin_api_auth
def list_users():
    users = User.query.order_by(User.id.asc()).all()
    result = []
    for u in users:
        cfg = u.config
        cfg_dict = cfg.to_dict(decrypt=True) if cfg else {
            'base_url': '',
            'model_name': '',
            'has_api_key': False,
            'platform': 'deepseek',
            'provider_name': '自托管模型服务',
            'models': [],
            'model_protocol': 'openai',
            'image_input': 'auto',
            'openai_api_mode': 'auto',
            'thought_level': 'auto',
            'context_limit': 0,
        }
        result.append({
            'id': u.id,
            'username': u.username,
            'role': u.role,
            'is_active': u.is_active,
            'created_at': u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else None,
            'config': cfg_dict,
        })
    return jsonify({'code': 0, 'data': result})

@admin_api_bp.route('/users', methods=['POST'])
@admin_api_auth
def create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or '123456'
    role = data.get('role') or 'user'

    if not username:
        return jsonify({'code': 400, 'message': '用户名不能为空'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'code': 400, 'message': '用户名已存在'}), 400

    user = User(username=username, role=role, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    # Create empty user config
    config = UserConfig(user_id=user.id, base_url='', model_name='', extra_config='{}')
    db.session.add(config)
    db.session.commit()

    return jsonify({'code': 0, 'message': '创建成功', 'data': user.to_dict()})

@admin_api_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@admin_api_auth
def edit_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404

    data = request.get_json(silent=True) or {}
    if 'password' in data and data['password']:
        user.set_password(data['password'].strip())
    if 'role' in data and data['role'] in ('admin', 'user'):
        user.role = data['role']
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])

    db.session.commit()
    return jsonify({'code': 0, 'message': '修改成功'})

@admin_api_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_api_auth
def delete_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    if user.username == 'admin' or user.id == session.get('admin_user_id'):
        return jsonify({'code': 400, 'message': '禁止删除当前登录的系统管理员'}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({'code': 0, 'message': '用户已删除'})

@admin_api_bp.route('/users/<int:user_id>/config', methods=['POST'])
@admin_api_auth
def update_user_config(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404

    config = user.config
    if not config:
        config = UserConfig(user_id=user.id)
        db.session.add(config)

    data = request.get_json(silent=True) or {}
    if 'base_url' in data:
        config.base_url = (data['base_url'] or '').strip()
    if 'model_name' in data:
        config.model_name = (data['model_name'] or '').strip()
    if 'api_key' in data and data['api_key']:
        config.set_api_key(data['api_key'].strip())

    extra = {}
    if config.extra_config:
        try:
            extra = json.loads(config.extra_config)
        except Exception:
            extra = {}

    for key in ('platform', 'provider_name', 'models', 'model_protocol', 'image_input', 'openai_api_mode', 'thought_level', 'context_limit'):
        if key in data:
            extra[key] = data[key]

    config.extra_config = json.dumps(extra, ensure_ascii=False)

    # Save as custom template if requested
    if data.get('save_as_template') and data.get('template_name'):
        tmpl_name = str(data.get('template_name')).strip()
        if tmpl_name:
            models_val = data.get('models') or []
            models_json = json.dumps(models_val, ensure_ascii=False) if isinstance(models_val, list) else str(models_val)
            tmpl = ModelTemplate(
                name=tmpl_name,
                platform=data.get('platform') or 'openai',
                base_url=config.base_url,
                api_key=data.get('api_key') or '',
                model_name=config.model_name,
                models=models_json,
                model_protocol=data.get('model_protocol') or 'openai',
                image_input=data.get('image_input') or 'auto',
                openai_api_mode=data.get('openai_api_mode') or 'auto',
                thought_level=data.get('thought_level') or 'auto',
                context_limit=int(data.get('context_limit') or 0),
                description=f'由用户【{user.username}】配置一键另存为模板',
            )
            db.session.add(tmpl)

    db.session.commit()
    return jsonify({'code': 0, 'message': '配置已更新'})

# Default preset templates for initial database setup or explicit reset
DEFAULT_MODEL_TEMPLATES = [
    {
        'name': 'DeepSeek 官方 API',
        'platform': 'deepseek',
        'base_url': 'https://api.deepseek.com/v1',
        'model_name': 'deepseek-chat',
        'models': json.dumps(['deepseek-chat', 'deepseek-reasoner']),
        'model_protocol': 'openai',
        'image_input': 'auto',
        'openai_api_mode': 'chat_completions',
        'thought_level': 'auto',
        'context_limit': 128000,
        'description': 'DeepSeek 官方开放平台模型服务 (DeepSeek-V3 与 R1 深度思考)',
    },
    {
        'name': 'OpenAI 官方 API',
        'platform': 'openai',
        'base_url': 'https://api.openai.com/v1',
        'model_name': 'gpt-4o',
        'models': json.dumps(['gpt-4o', 'gpt-4o-mini', 'o1-preview', 'o3-mini']),
        'model_protocol': 'openai',
        'image_input': 'supported',
        'openai_api_mode': 'chat_completions',
        'thought_level': 'auto',
        'context_limit': 128000,
        'description': 'OpenAI 官方通用大语言模型',
    },
    {
        'name': '硅基流动 SiliconFlow',
        'platform': 'siliconflow',
        'base_url': 'https://api.siliconflow.cn/v1',
        'model_name': 'deepseek-ai/DeepSeek-V3',
        'models': json.dumps(['deepseek-ai/DeepSeek-V3', 'deepseek-ai/DeepSeek-R1', 'Qwen/Qwen2.5-72B-Instruct']),
        'model_protocol': 'openai',
        'image_input': 'auto',
        'openai_api_mode': 'chat_completions',
        'thought_level': 'auto',
        'context_limit': 64000,
        'description': '硅基流动云端加速大模型',
    },
    {
        'name': '本地 Ollama 实例',
        'platform': 'ollama',
        'base_url': 'http://127.0.0.1:11434/v1',
        'model_name': 'qwen2.5:latest',
        'models': json.dumps(['qwen2.5:latest', 'llama3.1:latest', 'deepseek-r1:latest']),
        'model_protocol': 'openai',
        'image_input': 'auto',
        'openai_api_mode': 'chat_completions',
        'thought_level': 'auto',
        'context_limit': 32768,
        'description': '本地离线运行的 Ollama 服务',
    },
    {
        'name': 'OneAPI / NewAPI 中转接口',
        'platform': 'new-api',
        'base_url': 'http://127.0.0.1:3000/v1',
        'model_name': 'gpt-4o',
        'models': json.dumps(['gpt-4o', 'claude-3-5-sonnet-20241022', 'deepseek-chat']),
        'model_protocol': 'openai',
        'image_input': 'auto',
        'openai_api_mode': 'chat_completions',
        'thought_level': 'auto',
        'context_limit': 128000,
        'description': 'OneAPI / NewAPI 统一中转网关',
    },
]

# --- Model Templates API ---
@admin_api_bp.route('/templates', methods=['GET'])
@admin_api_auth
def list_templates():
    templates = ModelTemplate.query.order_by(ModelTemplate.id.asc()).all()
    return jsonify({
        'code': 0,
        'data': {
            'items': [t.to_dict() for t in templates]
        }
    })

@admin_api_bp.route('/templates/reset-defaults', methods=['POST'])
@admin_api_auth
def reset_default_templates():
    for d in DEFAULT_MODEL_TEMPLATES:
        db.session.add(ModelTemplate(**d))
    db.session.commit()
    templates = ModelTemplate.query.order_by(ModelTemplate.id.asc()).all()
    return jsonify({
        'code': 0,
        'message': '默认模板已恢复',
        'data': {
            'items': [t.to_dict() for t in templates]
        }
    })

@admin_api_bp.route('/templates', methods=['POST'])
@admin_api_auth
def save_template():
    data = request.get_json(silent=True) or {}
    tmpl_id = data.get('id')
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'code': 400, 'message': '模板名称不能为空'}), 400

    models = data.get('models') or []
    models_json = json.dumps(models, ensure_ascii=False) if isinstance(models, list) else str(models)

    if tmpl_id:
        tmpl = ModelTemplate.query.get(tmpl_id)
        if not tmpl:
            return jsonify({'code': 404, 'message': '模板不存在'}), 404
    else:
        tmpl = ModelTemplate(name=name)
        db.session.add(tmpl)

    tmpl.name = name
    tmpl.platform = data.get('platform') or 'openai'
    tmpl.base_url = (data.get('base_url') or '').strip()
    tmpl.model_name = (data.get('model_name') or '').strip()
    tmpl.models = models_json
    tmpl.api_key = (data.get('api_key') or '').strip()
    tmpl.model_protocol = data.get('model_protocol') or 'openai'
    tmpl.image_input = data.get('image_input') or 'auto'
    tmpl.openai_api_mode = data.get('openai_api_mode') or 'auto'
    tmpl.thought_level = data.get('thought_level') or 'auto'
    tmpl.context_limit = int(data.get('context_limit') or 0)
    tmpl.description = (data.get('description') or '').strip()

    db.session.commit()
    return jsonify({'code': 0, 'message': '模板保存成功', 'data': tmpl.to_dict()})

@admin_api_bp.route('/templates/<int:template_id>/delete', methods=['POST'])
@admin_api_auth
def delete_template(template_id: int):
    tmpl = ModelTemplate.query.get(template_id)
    if not tmpl:
        return jsonify({'code': 404, 'message': '模板不存在'}), 404

    db.session.delete(tmpl)
    db.session.commit()
    return jsonify({'code': 0, 'message': '模板已删除'})

# --- App Releases API ---
@admin_api_bp.route('/releases', methods=['GET'])
@admin_api_auth
def list_releases():
    releases = AppRelease.query.order_by(AppRelease.created_at.desc()).all()
    return jsonify({
        'code': 0,
        'data': {
            'items': [r.to_dict() for r in releases]
        }
    })

@admin_api_bp.route('/releases/upload', methods=['POST'])
@admin_api_auth
def upload_release():
    if 'file' not in request.files:
        return jsonify({'code': 400, 'message': '未选择安装包文件'}), 400

    file = request.files['file']
    version = (request.form.get('version') or '').strip().lstrip('v')
    title = (request.form.get('title') or '').strip()
    changelog = (request.form.get('changelog') or '').strip()

    if not version:
        return jsonify({'code': 400, 'message': '版本号不能为空'}), 400

    if not file or not file.filename:
        return jsonify({'code': 400, 'message': '未选择文件'}), 400

    raw_filename = os.path.basename(file.filename.strip())
    ext = raw_filename.rsplit('.', 1)[1].lower() if '.' in raw_filename else ''
    if ext not in ALLOWED_RELEASE_EXTENSIONS:
        return jsonify({'code': 400, 'message': f'不支持的安装包格式，仅支持: {", ".join(sorted(ALLOWED_RELEASE_EXTENSIONS))}'}), 400

    release_dir = os.path.join(Config.UPLOAD_FOLDER, 'releases')
    os.makedirs(release_dir, exist_ok=True)

    original_filename = raw_filename.replace('/', '').replace('\\', '').strip() or f'aionui-{version}.exe'
    stored_name = f"release-{version}-{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(release_dir, stored_name)

    file.save(file_path)
    file_size = os.path.getsize(file_path)

    release = AppRelease(
        version=version,
        title=title or f'AionUi v{version}',
        changelog=changelog,
        filename=original_filename,
        stored_name=stored_name,
        file_size=file_size,
        is_active=True,
    )
    db.session.add(release)
    db.session.commit()

    return jsonify({'code': 0, 'message': '版本发布成功', 'data': release.to_dict()})

@admin_api_bp.route('/releases/<int:release_id>/toggle', methods=['POST'])
@admin_api_auth
def toggle_release(release_id: int):
    rel = AppRelease.query.get(release_id)
    if not rel:
        return jsonify({'code': 404, 'message': '版本不存在'}), 404

    rel.is_active = not rel.is_active
    db.session.commit()
    msg = '版本已启用，客户端可检测到此更新' if rel.is_active else '版本已停用，客户端将跳过此版本'
    return jsonify({'code': 0, 'message': msg, 'is_active': rel.is_active})

@admin_api_bp.route('/releases/<int:release_id>/delete', methods=['POST'])
@admin_api_auth
def delete_release(release_id: int):
    rel = AppRelease.query.get(release_id)
    if not rel:
        return jsonify({'code': 404, 'message': '版本不存在'}), 404

    file_path = os.path.join(Config.UPLOAD_FOLDER, 'releases', rel.stored_name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    db.session.delete(rel)
    db.session.commit()
    return jsonify({'code': 0, 'message': '版本已删除'})

@admin_api_bp.route('/market', methods=['GET'])
@admin_api_auth
def list_market_files():
    files = MarketFile.query.order_by(MarketFile.created_at.desc()).all()
    result = []
    for f in files:
        item = f.to_dict()
        item['category_label'] = ALLOWED_CATEGORIES.get(f.category, f.category)
        item['uploader_username'] = f.uploader.username if f.uploader else 'admin'
        result.append(item)
    return jsonify({'code': 0, 'data': result})

@admin_api_bp.route('/market/upload', methods=['POST'])
@admin_api_auth
def upload_market_file():
    if 'file' not in request.files:
        return jsonify({'code': 400, 'message': '未选择文件'}), 400

    file = request.files['file']
    category = request.form.get('category', 'assistant').strip().lower()
    description = request.form.get('description', '').strip()

    if not file or not file.filename:
        return jsonify({'code': 400, 'message': '未选择文件'}), 400

    raw_filename = os.path.basename(file.filename.strip())
    ext = raw_filename.rsplit('.', 1)[1].lower() if '.' in raw_filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'code': 400, 'message': f'不支持的文件格式，仅支持: {", ".join(sorted(ALLOWED_EXTENSIONS))}'}), 400

    if category not in ALLOWED_CATEGORIES:
        return jsonify({'code': 400, 'message': '无效的应用分类'}), 400

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    original_filename = raw_filename.replace('/', '').replace('\\', '').strip() or f'package-{uuid.uuid4().hex[:8]}.zip'
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, stored_name)

    file.save(file_path)
    file_size = os.path.getsize(file_path)

    admin_user_id = session.get('admin_user_id')
    market_file = MarketFile(
        filename=original_filename,
        stored_name=stored_name,
        category=category,
        description=description,
        file_size=file_size,
        uploader_id=admin_user_id,
    )
    db.session.add(market_file)
    db.session.commit()

    return jsonify({'code': 0, 'message': '上传成功', 'data': market_file.to_dict()})

@admin_api_bp.route('/market/<int:file_id>/delete', methods=['POST'])
@admin_api_auth
def delete_market_file(file_id: int):
    market_file = MarketFile.query.get(file_id)
    if not market_file:
        return jsonify({'code': 404, 'message': '文件不存在'}), 404

    file_path = os.path.join(Config.UPLOAD_FOLDER, market_file.stored_name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    db.session.delete(market_file)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})

@admin_api_bp.route('/logs', methods=['GET'])
@admin_api_auth
def get_logs():
    level = request.args.get('level', '').strip().upper()
    query = ClientLog.query
    if level:
        query = query.filter_by(level=level)

    logs = query.order_by(ClientLog.created_at.desc()).limit(200).all()
    return jsonify({'code': 0, 'data': {'items': [l.to_dict() for l in logs]}})

@admin_api_bp.route('/logs/clear', methods=['POST'])
@admin_api_auth
def clear_all_logs():
    ClientLog.query.delete()
    db.session.commit()
    return jsonify({'code': 0, 'message': '日志已清空'})


# --- Flask-Admin Model Views with WTForms tuple fix ---
from wtforms import PasswordField

class SecureModelView(ModelView):
    def is_accessible(self):
        return session.get('is_admin', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin.login', next=request.url))

class UserView(SecureModelView):
    column_list = ['id', 'username', 'role', 'is_active', 'created_at']
    column_searchable_list = ['username']
    column_filters = ['role', 'is_active']
    form_columns = ['username', 'password', 'role', 'is_active']
    form_extra_fields = {
        'password': PasswordField('密码 (留空则使用默认或不修改)')
    }
    column_labels = {
        'id': 'ID',
        'username': '用户名',
        'role': '角色',
        'is_active': '启用状态',
        'created_at': '创建时间',
    }

    def on_model_change(self, form, model, is_created):
        if form.password.data:
            model.password_hash = generate_password_hash(form.password.data)
        elif is_created and not form.password.data:
            model.password_hash = generate_password_hash('123456')

class UserConfigView(SecureModelView):
    column_list = ['id', 'user_id', 'user', 'base_url', 'model_name', 'updated_at']
    column_searchable_list = ['base_url', 'model_name']
    column_labels = {
        'id': 'ID',
        'user_id': '用户ID',
        'user': '关联用户',
        'base_url': 'Base URL',
        'model_name': '默认模型',
        'updated_at': '更新时间',
    }

class MarketFileView(SecureModelView):
    column_list = ['id', 'filename', 'category', 'file_size', 'download_count', 'created_at']
    column_searchable_list = ['filename', 'description']
    column_filters = ['category']
    column_labels = {
        'id': 'ID',
        'filename': '文件名',
        'category': '分类',
        'file_size': '文件大小(字节)',
        'download_count': '下载次数',
        'created_at': '上传时间',
    }

class ClientLogView(SecureModelView):
    can_create = False
    can_edit = False
    column_list = ['id', 'level', 'user', 'client_info', 'message', 'created_at']
    column_searchable_list = ['message', 'client_info']
    column_filters = ['level', 'created_at']
    column_default_sort = ('created_at', True)
    column_labels = {
        'id': 'ID',
        'level': '级别',
        'user': '上报用户',
        'client_info': '客户端信息',
        'message': '日志内容',
        'created_at': '时间',
    }

class ModelTemplateView(SecureModelView):
    column_list = ['id', 'name', 'platform', 'base_url', 'model_name', 'image_input', 'thought_level', 'created_at']
    column_searchable_list = ['name', 'platform', 'model_name']
    column_filters = ['platform']
    column_labels = {
        'id': 'ID',
        'name': '模板名称',
        'platform': '供应商平台',
        'base_url': 'Base URL',
        'model_name': '默认模型',
        'image_input': '视觉支持',
        'thought_level': '思考推理',
        'created_at': '创建时间',
    }

class AppReleaseView(SecureModelView):
    column_list = ['id', 'version', 'title', 'filename', 'file_size', 'download_count', 'is_active', 'created_at']
    column_searchable_list = ['version', 'title', 'filename']
    column_filters = ['is_active']
    column_labels = {
        'id': 'ID',
        'version': '版本号',
        'title': '更新标题',
        'filename': '文件名',
        'file_size': '文件大小(字节)',
        'download_count': '下载次数',
        'is_active': '是否启用',
        'created_at': '发布时间',
    }


def init_admin(app):
    admin = Admin(
        app,
        name='AionUi 管理控制台',
        index_view=SecureAdminIndexView(name='概览', url='/admin'),
        template_mode='bootstrap3'
    )
    admin.add_view(UserView(User, db.session, name='用户数据表', category='原生数据表'))
    admin.add_view(UserConfigView(UserConfig, db.session, name='配置数据表', category='原生数据表'))
    admin.add_view(ModelTemplateView(ModelTemplate, db.session, name='模型模板数据表', category='原生数据表'))
    admin.add_view(AppReleaseView(AppRelease, db.session, name='更新发布数据表', category='原生数据表'))
    admin.add_view(MarketFileView(MarketFile, db.session, name='市场数据表', category='原生数据表'))
    admin.add_view(ClientLogView(ClientLog, db.session, name='日志数据表', category='原生数据表'))

    # Register Web Console API blueprint
    app.register_blueprint(admin_api_bp)

    return admin
