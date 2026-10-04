import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class StorageManager:
    """مدير التخزين يدعم التخزين المحلي وS3"""
    
    def __init__(self, backend='local', config=None):
        self.backend = backend
        self.config = config or {}
        self.s3_client = None
        
        if backend == 's3':
            self._init_s3_client()
    
    def _init_s3_client(self):
        """تهيئة عميل S3"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.config.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=self.config.get('AWS_SECRET_ACCESS_KEY'),
                region_name=self.config.get('S3_REGION', 'us-east-1')
            )
            # اختبار الاتصال
            self.s3_client.head_bucket(Bucket=self.config.get('S3_BUCKET_NAME'))
            logger.info("تم الاتصال بنجاح بـ S3")
        except (NoCredentialsError, ClientError) as e:
            logger.error(f"فشل في الاتصال بـ S3: {e}")
            raise Exception("فشل في تهيئة S3 - تحقق من بيانات الاعتماد")
    
    def save_file(self, file_stream, dest_path):
        """
        حفظ الملف في التخزين المحدد
        """
        try:
            if self.backend == 'local':
                return self._save_local(file_stream, dest_path)
            elif self.backend == 's3':
                return self._save_s3(file_stream, dest_path)
            else:
                raise ValueError(f"نوع التخزين غير مدعوم: {self.backend}")
        except Exception as e:
            logger.error(f"فشل في حفظ الملف {dest_path}: {e}")
            raise
    
    def _save_local(self, file_stream, dest_path):
        """حفظ الملف محلياً"""
        full_path = os.path.join(self.config.get('STORAGE_DIR', ''), dest_path)
        
        # إنشاء المجلد إذا لم يكن موجوداً
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # حفظ الملف
        with open(full_path, 'wb') as f:
            file_stream.seek(0)
            f.write(file_stream.read())
        
        return full_path
    
    def _save_s3(self, file_stream, dest_path):
        """حفظ الملف في S3"""
        bucket_name = self.config.get('S3_BUCKET_NAME')
        
        try:
            file_stream.seek(0)
            self.s3_client.upload_fileobj(
                file_stream,
                bucket_name,
                dest_path
            )
            return f"s3://{bucket_name}/{dest_path}"
        except ClientError as e:
            logger.error(f"فشل في رفع الملف إلى S3: {e}")
            raise Exception("فشل في رفع الملف إلى S3")
    
    def get_file(self, file_path):
        """
        الحصول على ملف من التخزين
        """
        try:
            if self.backend == 'local':
                return self._get_local(file_path)
            elif self.backend == 's3':
                return self._get_s3(file_path)
            else:
                raise ValueError(f"نوع التخزين غير مدعوم: {self.backend}")
        except Exception as e:
            logger.error(f"فشل في الحصول على الملف {file_path}: {e}")
            raise
    
    def _get_local(self, file_path):
        """الحصول على ملف محلي"""
        full_path = os.path.join(self.config.get('STORAGE_DIR', ''), file_path)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"الملف غير موجود: {file_path}")
        
        return open(full_path, 'rb')
    
    def _get_s3(self, file_path):
        """الحصول على ملف من S3"""
        bucket_name = self.config.get('S3_BUCKET_NAME')
        
        try:
            # إنشاء ملف مؤقت
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            
            self.s3_client.download_fileobj(
                bucket_name,
                file_path,
                temp_file
            )
            
            temp_file.seek(0)
            return temp_file
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"الملف غير موجود في S3: {file_path}")
            else:
                logger.error(f"فشل في تحميل الملف من S3: {e}")
                raise Exception("فشل في تحميل الملف من S3")
    
    def delete_file(self, file_path):
        """
        حذف ملف من التخزين
        """
        try:
            if self.backend == 'local':
                return self._delete_local(file_path)
            elif self.backend == 's3':
                return self._delete_s3(file_path)
            else:
                raise ValueError(f"نوع التخزين غير مدعوم: {self.backend}")
        except Exception as e:
            logger.error(f"فشل في حذف الملف {file_path}: {e}")
            raise
    
    def _delete_local(self, file_path):
        """حذف ملف محلي"""
        full_path = os.path.join(self.config.get('STORAGE_DIR', ''), file_path)
        
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        else:
            logger.warning(f"الملف غير موجود للحذف: {file_path}")
            return False
    
    def _delete_s3(self, file_path):
        """حذف ملف من S3"""
        bucket_name = self.config.get('S3_BUCKET_NAME')
        
        try:
            self.s3_client.delete_object(
                Bucket=bucket_name,
                Key=file_path
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"الملف غير موجود في S3 للحذف: {file_path}")
                return False
            else:
                logger.error(f"فشل في حذف الملف من S3: {e}")
                raise Exception("فشل في حذف الملف من S3")
    
    def file_exists(self, file_path):
        """
        التحقق من وجود ملف
        """
        try:
            if self.backend == 'local':
                full_path = os.path.join(self.config.get('STORAGE_DIR', ''), file_path)
                return os.path.exists(full_path)
            elif self.backend == 's3':
                bucket_name = self.config.get('S3_BUCKET_NAME')
                try:
                    self.s3_client.head_object(Bucket=bucket_name, Key=file_path)
                    return True
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        return False
                    else:
                        raise
            else:
                raise ValueError(f"نوع التخزين غير مدعوم: {self.backend}")
        except Exception as e:
            logger.error(f"فشل في التحقق من وجود الملف {file_path}: {e}")
            return False

# دالة مساعدة لإنشاء مدير التخزين
def get_storage_manager():
    """الحصول على مدير التخزين الحالي"""
    from config import Config
    
    config = {
        'STORAGE_DIR': Config.STORAGE_DIR,
        'AWS_ACCESS_KEY_ID': Config.AWS_ACCESS_KEY_ID,
        'AWS_SECRET_ACCESS_KEY': Config.AWS_SECRET_ACCESS_KEY,
        'S3_BUCKET_NAME': Config.S3_BUCKET_NAME,
        'S3_REGION': Config.S3_REGION
    }
    
    return StorageManager(backend=Config.STORAGE_BACKEND, config=config)
