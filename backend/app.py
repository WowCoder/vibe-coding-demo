# -*- coding: utf-8 -*-
"""
Talk2Code - Flask 主应用
重构版本：使用模块化架构
"""

import os
import sys
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import JWT_SECRET_KEY, JWT_ACCESS_TOKEN_EXPIRES
from models import init_db
from services.sse_manager import sse_manager
from services.task_queue import task_queue
from services.requirement_service import process_requirement_async
from utils.logger import setup_logger, get_logger
from utils.rate_limiter import get_user_identity, rate_limit_handler, RATE_LIMITS

# ==================== 日志配置 ====================

logger = get_logger(__name__)
setup_logger('sqlalchemy.engine', level=30)  # WARNING 级别

# ==================== 应用初始化 ====================

app = Flask(__name__, static_folder='../frontend', static_url_path='')

# CORS 配置
CORS(app)

# JWT 配置
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = JWT_ACCESS_TOKEN_EXPIRES
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'json']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'

jwt = JWTManager(app)

# 限流配置
limiter = Limiter(
    key_func=get_user_identity,
    app=app,
    default_limits=[RATE_LIMITS['default']],
    storage_uri="memory://",
    headers_enabled=True
)

# 限流触发处理
@app.errorhandler(429)
def handle_rate_limit_exceeded(e):
    return rate_limit_handler(e)

# 初始化数据库
init_db()

logger.info("Talk2Code 应用启动")


# ==================== 应用关闭处理 ====================

import atexit

def cleanup():
    """清理资源"""
    logger.info("清理资源...")
    sse_manager.shutdown()
    task_queue.shutdown(wait=False)

atexit.register(cleanup)


# ==================== 前端页面路由 ====================

@app.route('/')
def index():
    """首页 - 重定向到登录页"""
    return send_from_directory(app.static_folder, 'login.html')


@app.route('/login.html')
def login_page():
    """登录/注册页面"""
    return send_from_directory(app.static_folder, 'login.html')


@app.route('/index.html')
def home_page():
    """首页 - 需求输入页"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/detail.html')
def detail_page():
    """需求详情页"""
    return send_from_directory(app.static_folder, 'detail.html')


@app.route('/<path:filename>')
def static_files(filename):
    """静态文件服务"""
    return send_from_directory(app.static_folder, filename)


# ==================== 用户认证 API ====================

@app.route('/api/register', methods=['POST'])
@limiter.limit(RATE_LIMITS['auth'])
def register():
    """用户注册接口"""
    from models import User, SessionLocal
    from utils import hash_password

    data = request.get_json()
    if not data:
        return jsonify({'error': '请求数据为空'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    if len(username) < 3:
        return jsonify({'error': '用户名至少 3 个字符'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少 6 个字符'}), 400

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return jsonify({'error': '用户名已存在'}), 409

        password_hash = hash_password(password)
        new_user = User(username=username, password_hash=password_hash)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"用户注册成功：{username}")
        return jsonify({
            'message': '注册成功',
            'user': {'id': new_user.id, 'username': new_user.username}
        }), 201
    finally:
        db.close()


@app.route('/api/login', methods=['POST'])
@limiter.limit(RATE_LIMITS['auth'])
def login():
    """用户登录接口"""
    from models import User, SessionLocal
    from utils import verify_password

    data = request.get_json()
    if not data:
        return jsonify({'error': '请求数据为空'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            return jsonify({'error': '用户名或密码错误'}), 401

        access_token = create_access_token(identity=str(user.id), expires_delta=JWT_ACCESS_TOKEN_EXPIRES)
        logger.info(f"用户登录成功：{username}")

        return jsonify({
            'message': '登录成功',
            'token': access_token,
            'user': {'id': user.id, 'username': user.username}
        }), 200
    finally:
        db.close()


@app.route('/api/user/info', methods=['GET'])
@jwt_required()
def get_user_info():
    """获取当前用户信息"""
    from models import User, SessionLocal

    current_user_id = get_jwt_identity()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user_id).first()
        if not user:
            return jsonify({'error': '用户不存在'}), 404

        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'create_time': user.create_time.isoformat() if user.create_time else None
            }
        }), 200
    finally:
        db.close()


# ==================== 需求管理 API ====================

@app.route('/api/requirements', methods=['POST'])
@limiter.limit(RATE_LIMITS['requirement_create'])
@jwt_required()
def create_requirement():
    """创建需求接口"""
    from models import Requirement, SessionLocal

    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data or not data.get('content'):
        return jsonify({'error': '需求内容不能为空'}), 400

    content = data.get('content', '').strip()
    title = content[:100]

    db = SessionLocal()
    try:
        requirement = Requirement(
            user_id=current_user_id,
            title=title,
            content=content,
            status='pending',
            dialogue_history=[{
                'role': 'user',
                'name': '用户',
                'content': content,
                'timestamp': get_current_timestamp()
            }],
            code_files=[]
        )
        db.add(requirement)
        db.commit()
        db.refresh(requirement)

        logger.info(f"创建需求 {requirement.id}，准备提交到任务队列")

        # 提交到任务队列
        task_id = task_queue.submit(
            requirement.id,
            process_requirement_async,
            requirement.id
        )

        if task_id is None:
            # 任务已存在，直接启动线程处理
            import threading
            thread = threading.Thread(
                target=process_requirement_async,
                args=(requirement.id,),
                daemon=False
            )
            thread.start()
            logger.info(f"任务已存在，启动独立线程处理：{requirement.id}")

        return jsonify({
            'message': '需求已提交，正在处理',
            'requirement': {
                'id': requirement.id,
                'title': requirement.title,
                'status': requirement.status
            }
        }), 201
    finally:
        db.close()


@app.route('/api/requirements', methods=['GET'])
@jwt_required()
def list_requirements():
    """获取需求列表"""
    from models import Requirement, SessionLocal

    current_user_id = get_jwt_identity()
    db = SessionLocal()
    try:
        requirements = db.query(Requirement).filter(
            Requirement.user_id == current_user_id
        ).order_by(Requirement.create_time.desc()).all()

        return jsonify({
            'requirements': [
                {
                    'id': r.id,
                    'title': r.title,
                    'status': r.status,
                    'create_time': r.create_time.isoformat() if r.create_time else None
                }
                for r in requirements
            ]
        }), 200
    finally:
        db.close()


@app.route('/api/requirements/<int:req_id>', methods=['GET'])
@jwt_required()
def get_requirement(req_id):
    """获取需求详情"""
    from models import Requirement, SessionLocal

    current_user_id = get_jwt_identity()
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(
            Requirement.id == req_id,
            Requirement.user_id == current_user_id
        ).first()

        if not requirement:
            return jsonify({'error': '需求不存在'}), 404

        return jsonify({
            'requirement': {
                'id': requirement.id,
                'title': requirement.title,
                'content': requirement.content,
                'status': requirement.status,
                'dialogue_history': requirement.dialogue_history or [],
                'code_files': requirement.code_files or [],
                'create_time': requirement.create_time.isoformat() if requirement.create_time else None,
                'update_time': requirement.update_time.isoformat() if requirement.update_time else None
            }
        }), 200
    finally:
        db.close()


@app.route('/api/requirements/<int:req_id>/chat', methods=['POST'])
@limiter.limit(RATE_LIMITS['chat'])
@jwt_required()
def chat_with_requirement(req_id):
    """与需求对话（支持 diff 代码修改）"""
    from models import Requirement, SessionLocal
    from llm.client import get_client
    from prompts import CODE_EDIT_SYSTEM_PROMPT, CODE_EDIT_USER_PROMPT
    from diff_utils import parse_diff, apply_diff

    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data or not data.get('message'):
        return jsonify({'error': '消息内容不能为空'}), 400

    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(
            Requirement.id == req_id,
            Requirement.user_id == current_user_id
        ).first()

        if not requirement:
            return jsonify({'error': '需求不存在'}), 404

        user_message = data.get('message', '').strip()
        dialogue_history = requirement.dialogue_history or []

        # 构建对话上下文
        recent_dialogues = dialogue_history[-6:] if len(dialogue_history) > 6 else dialogue_history
        context_parts = []
        for msg in recent_dialogues:
            if msg.get('role') == 'user':
                context_parts.append(f"用户：{msg.get('content', '')}")
            elif msg.get('role') == 'agent':
                context_parts.append(f"AI: {msg.get('content', '')}")
        context = '\n'.join(context_parts)

        # 获取当前代码
        current_code = ""
        code_files = requirement.code_files or []
        for file in code_files:
            current_code += f"\n\n// === {file.get('filename', 'unknown')} ===\n{file.get('content', '')}"

        # 保存用户消息
        dialogue_history.append({
            'role': 'user',
            'name': '用户',
            'content': user_message,
            'timestamp': get_current_timestamp()
        })

        # 调用 LLM 生成 diff
        user_prompt = CODE_EDIT_USER_PROMPT.format(
            requirement=requirement.content,
            current_code=current_code if current_code else '暂无代码',
            user_message=user_message
        )

        client = get_client()
        response = client.chat(user_prompt, CODE_EDIT_SYSTEM_PROMPT, use_memory=False, max_tokens=3000, timeout=45)
        ai_response = response.content

        # 解析并应用 diff
        code_updated = False
        updated_files = []

        for diff_file in parse_diff(ai_response):
            original_file = None
            for f in code_files:
                if f.get('filename') == diff_file.filename:
                    original_file = f
                    break

            if original_file:
                try:
                    new_content = apply_diff(original_file.get('content', ''), diff_file)
                    if new_content != original_file.get('content', ''):
                        original_file['content'] = new_content
                        original_file['status'] = 'modified'
                        code_updated = True
                        updated_files.append(diff_file.filename)
                        logger.info(f"文件 {diff_file.filename} 已通过 diff 更新")
                except Exception as e:
                    logger.warning(f"应用 diff 失败：{e}")

        # 保存 AI 回复
        if code_updated:
            dialogue_history.append({
                'role': 'system',
                'name': '系统',
                'content': f'已更新文件：{", ".join(updated_files)}',
                'timestamp': get_current_timestamp(),
                'type': 'code_updated'
            })
        else:
            dialogue_history.append({
                'role': 'agent',
                'name': 'AI 助手',
                'content': ai_response,
                'timestamp': get_current_timestamp()
            })

        requirement.dialogue_history = dialogue_history
        requirement.code_files = code_files
        db.commit()

        return jsonify({
            'message': 'success',
            'dialogue_history': dialogue_history,
            'code_files': requirement.code_files,
            'ai_response': ai_response,
            'updated_files': updated_files if code_updated else []
        }), 200

    except Exception as e:
        logger.error(f"处理对话失败：{e}", exc_info=True)
        db.rollback()
        return jsonify({'error': f'处理失败：{str(e)}'}), 500
    finally:
        db.close()


@app.route('/api/requirements/<int:req_id>/code', methods=['POST'])
@jwt_required()
def save_code(req_id):
    """保存用户修改的代码"""
    from models import Requirement, SessionLocal

    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data or not data.get('filename'):
        return jsonify({'error': '文件名不能为空'}), 400

    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(
            Requirement.id == req_id,
            Requirement.user_id == current_user_id
        ).first()

        if not requirement:
            return jsonify({'error': '需求不存在'}), 404

        filename = data.get('filename', '').strip()
        content = data.get('content', '')

        code_files = requirement.code_files or []
        file_found = False
        for i, file in enumerate(code_files):
            if file.get('filename') == filename:
                code_files[i]['content'] = content
                code_files[i]['status'] = 'modified'
                file_found = True
                break

        if not file_found:
            code_files.append({
                'filename': filename,
                'content': content,
                'status': 'modified'
            })

        requirement.code_files = code_files

        dialogue_history = requirement.dialogue_history or []
        dialogue_history.append({
            'role': 'user',
            'name': '用户',
            'content': f'修改了文件 {filename}',
            'timestamp': get_current_timestamp(),
            'type': 'code_edit'
        })
        requirement.dialogue_history = dialogue_history

        db.commit()

        return jsonify({
            'message': '代码已保存',
            'filename': filename,
            'code_files': code_files
        }), 200

    except Exception as e:
        logger.error(f"保存代码失败：{e}")
        db.rollback()
        return jsonify({'error': f'保存失败：{str(e)}'}), 500
    finally:
        db.close()


@app.route('/api/requirements/<int:req_id>/code/all', methods=['PUT'])
@jwt_required()
def save_all_code(req_id):
    """批量保存所有代码文件"""
    from models import Requirement, SessionLocal

    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data or not data.get('code_files'):
        return jsonify({'error': '代码文件列表不能为空'}), 400

    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(
            Requirement.id == req_id,
            Requirement.user_id == current_user_id
        ).first()

        if not requirement:
            return jsonify({'error': '需求不存在'}), 404

        new_code_files = []
        for file in data.get('code_files', []):
            if 'filename' in file and 'content' in file:
                new_code_files.append({
                    'filename': file['filename'],
                    'content': file['content'],
                    'status': 'modified'
                })

        requirement.code_files = new_code_files
        db.commit()

        return jsonify({
            'message': '所有代码已保存',
            'code_files': new_code_files
        }), 200

    except Exception as e:
        logger.error(f"批量保存代码失败：{e}")
        db.rollback()
        return jsonify({'error': f'保存失败：{str(e)}'}), 500
    finally:
        db.close()


# ==================== SSE 实时推送 ====================

@app.route('/api/sse/<int:req_id>')
def sse_stream(req_id):
    """SSE 实时推送连接"""
    import queue

    client_queue = queue.Queue()
    client_id = str(req_id)

    # 添加到 SSE 管理器
    sse_manager.add_client(client_id, client_queue)
    logger.debug(f"SSE 客户端已连接：client_id={client_id}")

    def generate():
        try:
            # 发送初始连接消息
            yield SSEMessage.format_event('connected', {'requirement_id': req_id})

            # 持续监听队列中的消息
            while True:
                try:
                    message = client_queue.get(timeout=30)
                    if message is None:
                        break
                    yield message
                except queue.Empty:
                    yield ': heartbeat\n\n'
        except GeneratorExit:
            logger.debug(f"SSE 客户端断开：client_id={client_id}")
        finally:
            sse_manager.remove_client(client_id, client_queue)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# ==================== 辅助函数 ====================

def get_current_timestamp() -> str:
    """获取当前时间戳"""
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


from utils import SSEMessage


# ==================== 主程序入口 ====================

if __name__ == '__main__':
    logger.info("启动 Flask 应用，端口 5001")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
