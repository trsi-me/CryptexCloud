import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

class Config:
    """إعدادات التطبيق الأساسية"""
    
    # إعدادات Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'
    FLASK_APP = os.getenv('FLASK_APP', 'app.py')
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    
    # إعدادات التخزين
    STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'local')
    DATA_DIR = os.getenv('DATA_DIR', 'data')
    STORAGE_DIR = os.getenv('STORAGE_DIR', 'storage')
    
    # إعدادات التشفير
    PBKDF2_ITERATIONS = int(os.getenv('PBKDF2_ITERATIONS', '200000'))
    
    # إعدادات AWS S3
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', '')
    S3_REGION = os.getenv('S3_REGION', 'us-east-1')
    
    # إعدادات SMTP
    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASS = os.getenv('SMTP_PASS', '')
    
    @classmethod
    def init_app(cls, app):
        """تهيئة التطبيق مع الإعدادات"""
        app.config.from_object(cls)
        
        # إنشاء المجلدات المطلوبة إذا لم تكن موجودة
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.STORAGE_DIR, exist_ok=True)
        
        # تعيين مسار قاعدة البيانات
        app.config['DATABASE'] = os.path.join(cls.DATA_DIR, 'cryptexcloud.db')
        
        # إعدادات الجلسة
        app.config['SESSION_COOKIE_SECURE'] = not cls.FLASK_DEBUG
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        
        # إعدادات رفع الملفات
        app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
        app.config['UPLOAD_FOLDER'] = cls.STORAGE_DIR
