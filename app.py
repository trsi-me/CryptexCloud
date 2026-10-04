import os
import sqlite3
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from config import Config
from utils.security import hash_password, verify_password, generate_unique_filename, validate_user_input, get_client_ip, log_security_event
from utils.storage import get_storage_manager

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
Config.init_app(app)

# تهيئة مدير التخزين
storage_manager = get_storage_manager()

def get_db_connection():
    """الحصول على اتصال قاعدة البيانات"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    conn = get_db_connection()
    
    # جدول المستخدمين
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول الملفات
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            size INTEGER NOT NULL,
            mime_type TEXT,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # جدول السجلات
    conn.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            file_id INTEGER,
            ip TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            message TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # جدول إعدادات المستخدم
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            pbkdf2_iterations INTEGER DEFAULT 200000,
            algorithm TEXT DEFAULT 'AES-256-GCM',
            max_file_size INTEGER DEFAULT 100,
            auto_delete TEXT DEFAULT 'never',
            session_timeout INTEGER DEFAULT 120,
            two_factor BOOLEAN DEFAULT 0,
            storage_backend TEXT DEFAULT 'local',
            s3_bucket TEXT DEFAULT '',
            email_notifications BOOLEAN DEFAULT 0,
            notify_upload BOOLEAN DEFAULT 1,
            notify_download BOOLEAN DEFAULT 1,
            notify_delete BOOLEAN DEFAULT 0,
            notify_login BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("تم تهيئة قاعدة البيانات بنجاح")

def log_action(user_id, action, file_id=None, status='success', message=''):
    """تسجيل عمل في السجلات"""
    try:
        conn = get_db_connection()
        ip = get_client_ip(request)
        
        conn.execute('''
            INSERT INTO logs (user_id, action, file_id, ip, status, message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, action, file_id, ip, status, message))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"فشل في تسجيل العمل: {e}")

def require_auth(f):
    """مُزخرف للتحقق من تسجيل الدخول"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'يجب تسجيل الدخول أولاً'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Routes للواجهات
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    """صفحة تسجيل الدخول"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/profile')
def profile():
    """صفحة الملف الشخصي"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')

@app.route('/settings')
def settings():
    """صفحة الإعدادات"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/logs')
def logs():
    """صفحة السجل"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('logs.html')

@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    if 'user_id' in session:
        log_action(session['user_id'], 'logout', status='success')
        session.clear()
    return redirect(url_for('login'))

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    """تسجيل مستخدم جديد"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # التحقق من صحة البيانات
        errors = validate_user_input(username, email, password)
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        conn = get_db_connection()
        
        # التحقق من عدم وجود المستخدم
        existing_user = conn.execute(
            'SELECT id FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if existing_user:
            conn.close()
            return jsonify({'error': 'اسم المستخدم موجود مسبقاً'}), 400
        
        # إنشاء المستخدم الجديد
        password_hash = hash_password(password)
        cursor = conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_action(user_id, 'register', status='success')
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'message': 'تم إنشاء الحساب بنجاح'
        })
        
    except Exception as e:
        logger.error(f"خطأ في التسجيل: {e}")
        return jsonify({'error': 'حدث خطأ في التسجيل'}), 500

@app.route('/api/login', methods=['POST'])
def login_api():
    """تسجيل الدخول"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'اسم المستخدم وكلمة المرور مطلوبان'}), 400
        
        conn = get_db_connection()
        
        # البحث عن المستخدم
        user = conn.execute(
            'SELECT id, username, password_hash FROM users WHERE username = ? OR email = ?',
            (username, username)
        ).fetchone()
        
        conn.close()
        
        if not user or not verify_password(user['password_hash'], password):
            return jsonify({'error': 'بيانات الدخول غير صحيحة'}), 401
        
        # بدء الجلسة
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        log_action(user['id'], 'login', status='success')
        
        return jsonify({
            'success': True,
            'message': 'تم تسجيل الدخول بنجاح'
        })
        
    except Exception as e:
        logger.error(f"خطأ في تسجيل الدخول: {e}")
        return jsonify({'error': 'حدث خطأ في تسجيل الدخول'}), 500

@app.route('/api/upload', methods=['POST'])
@require_auth
def upload_file():
    """رفع ملف مشفّر"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400
        
        # الحصول على البيانات الوصفية
        original_filename = request.form.get('original_filename', '')
        size = int(request.form.get('size', 0))
        mime_type = request.form.get('mime_type', 'application/octet-stream')
        encrypted_data_key = request.form.get('encrypted_data_key', '')
        key_iv = request.form.get('key_iv', '')
        file_iv = request.form.get('file_iv', '')
        salt = request.form.get('salt', '')
        pbkdf2_iterations = int(request.form.get('pbkdf2_iterations', 200000))
        algorithm = request.form.get('algorithm', 'AES-256-GCM')
        
        # التحقق من وجود جميع البيانات المطلوبة
        required_fields = [original_filename, encrypted_data_key, key_iv, file_iv, salt]
        if not all(required_fields):
            return jsonify({'error': 'بيانات التشفير ناقصة'}), 400
        
        # إنشاء اسم ملف فريد
        stored_filename = generate_unique_filename()
        
        # حفظ الملف
        storage_manager.save_file(file, stored_filename)
        
        # إعداد البيانات الوصفية
        metadata = {
            'encrypted_data_key': encrypted_data_key,
            'key_iv': key_iv,
            'file_iv': file_iv,
            'salt': salt,
            'pbkdf2_iterations': pbkdf2_iterations,
            'algorithm': algorithm
        }
        
        # حفظ في قاعدة البيانات
        conn = get_db_connection()
        cursor = conn.execute('''
            INSERT INTO files (user_id, original_filename, stored_filename, size, mime_type, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], original_filename, stored_filename, size, mime_type, json.dumps(metadata)))
        
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'upload', file_id, 'success', f'تم رفع الملف: {original_filename}')
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'message': 'تم رفع الملف بنجاح'
        })
        
    except Exception as e:
        logger.error(f"خطأ في رفع الملف: {e}")
        log_action(session.get('user_id'), 'upload', status='error', message=str(e))
        return jsonify({'error': 'حدث خطأ في رفع الملف'}), 500

@app.route('/api/files', methods=['GET'])
@require_auth
def get_files():
    """الحصول على قائمة ملفات المستخدم"""
    try:
        conn = get_db_connection()
        files = conn.execute('''
            SELECT id, original_filename, size, mime_type, uploaded_at
            FROM files WHERE user_id = ?
            ORDER BY uploaded_at DESC
        ''', (session['user_id'],)).fetchall()
        
        conn.close()
        
        files_list = []
        for file in files:
            files_list.append({
                'id': file['id'],
                'original_filename': file['original_filename'],
                'size': file['size'],
                'mime_type': file['mime_type'],
                'uploaded_at': file['uploaded_at']
            })
        
        return jsonify({
            'success': True,
            'files': files_list
        })
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على الملفات: {e}")
        return jsonify({'error': 'حدث خطأ في الحصول على الملفات'}), 500

@app.route('/api/download/<int:file_id>', methods=['GET'])
@require_auth
def download_file(file_id):
    """تحميل ملف مشفّر"""
    try:
        conn = get_db_connection()
        file_record = conn.execute('''
            SELECT * FROM files WHERE id = ? AND user_id = ?
        ''', (file_id, session['user_id'])).fetchone()
        
        if not file_record:
            conn.close()
            return jsonify({'error': 'الملف غير موجود'}), 404
        
        # الحصول على الملف من التخزين
        file_stream = storage_manager.get_file(file_record['stored_filename'])
        
        # إعداد الاستجابة
        response = send_file(
            file_stream,
            as_attachment=True,
            download_name=file_record['original_filename'] + '.encrypted',
            mimetype='application/octet-stream'
        )
        
        # إضافة البيانات الوصفية في الرؤوس
        metadata = json.loads(file_record['metadata'])
        response.headers['X-Metadata'] = json.dumps(metadata)
        response.headers['X-Original-Filename'] = file_record['original_filename']
        response.headers['X-File-Size'] = str(file_record['size'])
        response.headers['X-Mime-Type'] = file_record['mime_type'] or 'application/octet-stream'
        
        conn.close()
        
        log_action(session['user_id'], 'download', file_id, 'success', f'تم تحميل الملف: {file_record["original_filename"]}')
        
        return response
        
    except FileNotFoundError:
        return jsonify({'error': 'الملف غير موجود في التخزين'}), 404
    except Exception as e:
        logger.error(f"خطأ في تحميل الملف: {e}")
        log_action(session.get('user_id'), 'download', file_id, 'error', str(e))
        return jsonify({'error': 'حدث خطأ في تحميل الملف'}), 500

@app.route('/api/file/<int:file_id>', methods=['DELETE'])
@require_auth
def delete_file(file_id):
    """حذف ملف"""
    try:
        conn = get_db_connection()
        file_record = conn.execute('''
            SELECT * FROM files WHERE id = ? AND user_id = ?
        ''', (file_id, session['user_id'])).fetchone()
        
        if not file_record:
            conn.close()
            return jsonify({'error': 'الملف غير موجود'}), 404
        
        # حذف الملف من التخزين
        try:
            storage_manager.delete_file(file_record['stored_filename'])
        except Exception as e:
            logger.warning(f"فشل في حذف الملف من التخزين: {e}")
        
        # حذف السجل من قاعدة البيانات
        conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'delete', file_id, 'success', f'تم حذف الملف: {file_record["original_filename"]}')
        
        return jsonify({
            'success': True,
            'message': 'تم حذف الملف بنجاح'
        })
        
    except Exception as e:
        logger.error(f"خطأ في حذف الملف: {e}")
        log_action(session.get('user_id'), 'delete', file_id, 'error', str(e))
        return jsonify({'error': 'حدث خطأ في حذف الملف'}), 500

@app.route('/api/logs', methods=['GET'])
@require_auth
def get_logs():
    """الحصول على سجلات المستخدم"""
    try:
        # الحصول على معاملات الفلترة
        page = int(request.args.get('page', 1))
        action_filter = request.args.get('action', '')
        status_filter = request.args.get('status', '')
        date_filter = request.args.get('date', '')
        
        conn = get_db_connection()
        
        # بناء الاستعلام مع الفلاتر
        where_conditions = ['user_id = ?']
        params = [session['user_id']]
        
        if action_filter:
            where_conditions.append('action = ?')
            params.append(action_filter)
        
        if status_filter:
            where_conditions.append('status = ?')
            params.append(status_filter)
        
        if date_filter:
            if date_filter == 'today':
                where_conditions.append('DATE(timestamp) = DATE("now")')
            elif date_filter == 'week':
                where_conditions.append('timestamp >= datetime("now", "-7 days")')
            elif date_filter == 'month':
                where_conditions.append('timestamp >= datetime("now", "-30 days")')
            elif date_filter == 'year':
                where_conditions.append('timestamp >= datetime("now", "-365 days")')
        
        where_clause = ' AND '.join(where_conditions)
        
        # الحصول على إجمالي السجلات
        total_logs = conn.execute(f'''
            SELECT COUNT(*) as total FROM logs WHERE {where_clause}
        ''', params).fetchone()['total']
        
        # الحصول على السجلات مع الترقيم
        limit = 20
        offset = (page - 1) * limit
        logs = conn.execute(f'''
            SELECT action, timestamp, status, message, file_id, ip
            FROM logs WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        ''', params + [limit, offset]).fetchall()
        
        # حساب الإحصائيات
        stats = conn.execute('''
            SELECT 
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error,
                SUM(CASE WHEN action = 'upload' THEN 1 ELSE 0 END) as upload,
                SUM(CASE WHEN action = 'download' THEN 1 ELSE 0 END) as download
            FROM logs WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        conn.close()
        
        logs_list = []
        for log in logs:
            logs_list.append({
                'action': log['action'],
                'timestamp': log['timestamp'],
                'status': log['status'],
                'message': log['message'],
                'file_id': log['file_id'],
                'ip': log['ip']
            })
        
        return jsonify({
            'success': True,
            'logs': logs_list,
            'pagination': {
                'current_page': page,
                'total_pages': (total_logs + limit - 1) // limit,
                'total_logs': total_logs
            },
            'stats': {
                'success': stats['success'] or 0,
                'error': stats['error'] or 0,
                'upload': stats['upload'] or 0,
                'download': stats['download'] or 0
            }
        })
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على السجلات: {e}")
        return jsonify({'error': 'حدث خطأ في الحصول على السجلات'}), 500

@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    """الحصول على إعدادات المستخدم"""
    try:
        conn = get_db_connection()
        settings = conn.execute('''
            SELECT * FROM user_settings WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        conn.close()
        
        if settings:
            return jsonify({
                'success': True,
                'settings': {
                    'pbkdf2_iterations': settings['pbkdf2_iterations'],
                    'algorithm': settings['algorithm'],
                    'max_file_size': settings['max_file_size'],
                    'auto_delete': settings['auto_delete'],
                    'session_timeout': settings['session_timeout'],
                    'two_factor': settings['two_factor'],
                    'storage_backend': settings['storage_backend'],
                    's3_bucket': settings['s3_bucket'],
                    'email_notifications': settings['email_notifications'],
                    'notify_upload': settings['notify_upload'],
                    'notify_download': settings['notify_download'],
                    'notify_delete': settings['notify_delete'],
                    'notify_login': settings['notify_login']
                }
            })
        else:
            # إعدادات افتراضية
            return jsonify({
                'success': True,
                'settings': {
                    'pbkdf2_iterations': 200000,
                    'algorithm': 'AES-256-GCM',
                    'max_file_size': 100,
                    'auto_delete': 'never',
                    'session_timeout': 120,
                    'two_factor': False,
                    'storage_backend': 'local',
                    's3_bucket': '',
                    'email_notifications': False,
                    'notify_upload': True,
                    'notify_download': True,
                    'notify_delete': False,
                    'notify_login': False
                }
            })
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على الإعدادات: {e}")
        return jsonify({'error': 'حدث خطأ في الحصول على الإعدادات'}), 500

@app.route('/api/settings', methods=['POST'])
@require_auth
def save_settings():
    """حفظ إعدادات المستخدم"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        
        # التحقق من وجود الإعدادات
        existing = conn.execute('''
            SELECT id FROM user_settings WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if existing:
            # تحديث الإعدادات الموجودة
            conn.execute('''
                UPDATE user_settings SET
                    pbkdf2_iterations = ?,
                    algorithm = ?,
                    max_file_size = ?,
                    auto_delete = ?,
                    session_timeout = ?,
                    two_factor = ?,
                    storage_backend = ?,
                    s3_bucket = ?,
                    email_notifications = ?,
                    notify_upload = ?,
                    notify_download = ?,
                    notify_delete = ?,
                    notify_login = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (
                data.get('pbkdf2_iterations', 200000),
                data.get('algorithm', 'AES-256-GCM'),
                data.get('max_file_size', 100),
                data.get('auto_delete', 'never'),
                data.get('session_timeout', 120),
                data.get('two_factor', False),
                data.get('storage_backend', 'local'),
                data.get('s3_bucket', ''),
                data.get('email_notifications', False),
                data.get('notify_upload', True),
                data.get('notify_download', True),
                data.get('notify_delete', False),
                data.get('notify_login', False),
                session['user_id']
            ))
        else:
            # إنشاء إعدادات جديدة
            conn.execute('''
                INSERT INTO user_settings (
                    user_id, pbkdf2_iterations, algorithm, max_file_size,
                    auto_delete, session_timeout, two_factor, storage_backend,
                    s3_bucket, email_notifications, notify_upload, notify_download,
                    notify_delete, notify_login
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['user_id'],
                data.get('pbkdf2_iterations', 200000),
                data.get('algorithm', 'AES-256-GCM'),
                data.get('max_file_size', 100),
                data.get('auto_delete', 'never'),
                data.get('session_timeout', 120),
                data.get('two_factor', False),
                data.get('storage_backend', 'local'),
                data.get('s3_bucket', ''),
                data.get('email_notifications', False),
                data.get('notify_upload', True),
                data.get('notify_download', True),
                data.get('notify_delete', False),
                data.get('notify_login', False)
            ))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'settings_update', status='success', message='تم تحديث الإعدادات')
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ الإعدادات بنجاح'
        })
        
    except Exception as e:
        logger.error(f"خطأ في حفظ الإعدادات: {e}")
        return jsonify({'error': 'حدث خطأ في حفظ الإعدادات'}), 500

@app.route('/api/profile', methods=['GET'])
@require_auth
def get_profile():
    """الحصول على بيانات الملف الشخصي"""
    try:
        conn = get_db_connection()
        
        # الحصول على بيانات المستخدم
        user = conn.execute('''
            SELECT username, email, created_at FROM users WHERE id = ?
        ''', (session['user_id'],)).fetchone()
        
        # الحصول على إحصائيات الملفات
        stats = conn.execute('''
            SELECT 
                COUNT(*) as total_files,
                SUM(size) as total_size
            FROM files WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'username': user['username'],
                'email': user['email'],
                'created_at': user['created_at']
            },
            'stats': {
                'total_files': stats['total_files'] or 0,
                'total_size': stats['total_size'] or 0
            }
        })
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على الملف الشخصي: {e}")
        return jsonify({'error': 'حدث خطأ في الحصول على الملف الشخصي'}), 500

# معالج الأخطاء
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'الصفحة غير موجودة'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'حدث خطأ داخلي في الخادم'}), 500

if __name__ == '__main__':
    # تهيئة قاعدة البيانات
    init_db()
    
    # تشغيل التطبيق
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=app.config['FLASK_DEBUG']
    )
