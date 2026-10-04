import uuid
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password):
    """
    إنشاء هش آمن لكلمة المرور باستخدام PBKDF2
    """
    return generate_password_hash(password, method='pbkdf2:sha256')

def verify_password(password_hash, password):
    """
    التحقق من صحة كلمة المرور مقابل الهش المحفوظ
    """
    return check_password_hash(password_hash, password)

def generate_unique_filename():
    """
    توليد اسم ملف فريد باستخدام UUID
    """
    return str(uuid.uuid4())

def generate_session_token():
    """
    توليد رمز جلسة فريد
    """
    return str(uuid.uuid4())

def sanitize_filename(filename):
    """
    تنظيف اسم الملف من الأحرف الخطيرة
    """
    # إزالة الأحرف الخطيرة
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # تحديد طول الاسم
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:255-len(ext)-1] + '.' + ext if ext else name[:255]
    
    return filename

def validate_user_input(username, email=None, password=None):
    """
    التحقق من صحة بيانات المستخدم
    """
    errors = []
    
    # التحقق من اسم المستخدم
    if not username or len(username.strip()) < 3:
        errors.append("اسم المستخدم يجب أن يكون 3 أحرف على الأقل")
    
    if len(username) > 50:
        errors.append("اسم المستخدم طويل جداً")
    
    # التحقق من البريد الإلكتروني (اختياري)
    if email:
        if '@' not in email or '.' not in email:
            errors.append("البريد الإلكتروني غير صحيح")
        if len(email) > 100:
            errors.append("البريد الإلكتروني طويل جداً")
    
    # التحقق من كلمة المرور
    if password:
        if len(password) < 8:
            errors.append("كلمة المرور يجب أن تكون 8 أحرف على الأقل")
        if len(password) > 128:
            errors.append("كلمة المرور طويلة جداً")
    
    return errors

def get_client_ip(request):
    """
    الحصول على عنوان IP الحقيقي للعميل
    """
    # التحقق من الـ headers المختلفة للحصول على IP الحقيقي
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def log_security_event(user_id, action, file_id=None, ip=None, status='success', message=''):
    """
    تسجيل حدث أمني (يتم استدعاؤها من app.py)
    """
    # هذه الدالة ستستخدم في app.py لتسجيل الأحداث
    return {
        'user_id': user_id,
        'action': action,
        'file_id': file_id,
        'ip': ip,
        'status': status,
        'message': message
    }
