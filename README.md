# CryptexCloud

نظام نسخ احتياطي يحفظ ملفات مشفّرة. التشفير يتم في المتصفح بواجهة Web Crypto قبل الرفع. الخادم يخزّن الناتج وبيانات وصفية مشفّرة ولا يفك المحتوى.

تحذير من التوثيق السابق وما زال صحيحاً: فقدان كلمة المرور الرئيسية أو البيانات الوصفية أو ملف التخزين يمنع استرجاع المحتوى. لا توجد نسخة مفتاح مفكوك على الخادم.

## 1 ما هو المشروع

تطبيق Flask عربي: تسجيل، دخول، رفع ملف مع metadata قادمة من المتصفح، تنزيل الملف كما خُزّن، حذفه، سجل عمليات، وإعدادات مستخدم. التخزين المحلي هو الافتراضي، مع مسار اختياري إلى Amazon S3 عبر `boto3` عندما `STORAGE_BACKEND=s3`.

## 2 لماذا وُجد

إبقاء المحتوى غير مقروء للخادم: المفتاح يُشتق في المتصفح من كلمة مرور رئيسية، ويُشفّر الملف بـ AES-256-GCM، ويُرسل ciphertext. هذا موصوف في README السابق ويطابقه اعتماد الواجهة على Web Crypto وعمود `files.metadata`.

## 3 المستخدمون

مستخدم مسجّل يملك `session['user_id']`. لا أدوار إضافية في جدول `users`. الزائر يُوجَّه من `/` إلى `/login`.

لا حسابات بذرة في `init_db`. الحساب يُنشأ من `POST /api/register`.

## 4 الميزات

- تسجيل ودخول وخروج.
- رفع حتى حد 100 ميجابايت (`MAX_CONTENT_LENGTH`).
- قائمة ملفات المستخدم.
- تنزيل وحذف لملفاته فقط.
- سجل `logs` مع عنوان IP.
- إعدادات في `user_settings`: تكرارات PBKDF2، الخوارزمية، حد الحجم، الحذف التلقائي، مهلة الجلسة، علم المصادقة الثنائية، واجهة التخزين، دلو S3، أعلام إشعارات.
- صفحات: الرئيسية، الدخول، الملف، الإعدادات، السجل.

علم `two_factor` يُحفظ في الجدول. استنتاج من الكود: مسار الدخول يتحقق من كلمة المرور فقط ولا يطلب رمزاً ثانياً.

## 5 سير العمل

```
/login -> POST /api/login -> session user_id
المتصفح: كلمة مرور رئيسية
  -> PBKDF2 + AES-GCM داخل المتصفح
  -> POST /api/upload (ملف مشفّر + metadata JSON)
  -> storage + صف files
GET /api/download/<id> -> الملف المشفر
  -> المتصفح يفكه بكلمة المرور الرئيسية
```

فك التشفير بعد التنزيل يتم في الواجهة. الخادم يعيد البايتات المخزنة.

## 6 أمثلة واقعية

مثال README السابق ما زال صالحاً كاختبار يدوي: مستخدم جديد، ملف نصي «Hello Cryptex»، كلمة مرور رئيسية يختارها، ثم تنزيل وفك ومقارنة بصمة SHA-256 بأداة النظام `certutil` على Windows. الخادم لا يحسب هذه البصمة للمحتوى الأصلي لأنه لا يراه.

## 7 رحلة المستخدم

1. يفتح `/login` وينشئ حساباً (اسم 3 أحرف على الأقل، كلمة مرور 8 أحرف على الأقل).
2. يدخل إلى `/`.
3. يختار ملفاً ويكتب كلمة المرور الرئيسية في الواجهة.
4. يرفع. يظهر الملف في القائمة بالاسم الأصلي والحجم.
5. ينزّل ويفك في المتصفح.
6. يراجع `/logs` ويرى الرفع والتنزيل.
7. يضبط `/settings` ثم يخرج من `/logout`.

## 8 الوحدات

| الملف | الوظيفة |
| --- | --- |
| `app.py` | المسارات والجلسة وتهيئة الجداول |
| `config.py` | قراءة البيئة وإنشاء المجلدات |
| `utils/security.py` | تجزئة كلمة مرور الحساب، التحقق، اسم فريد، تنظيف الاسم، IP |
| `utils/storage.py` | حفظ محلي أو S3 |
| `templates/` | index, login, profile, settings, logs |
| `static/js/app.js` | تشفير المتصفح والنداءات |
| `static/css/style.css` | التنسيق |
| `static/fonts/` | خطوط |
| `data/cryptexcloud.db` | قاعدة افتراضية |
| `storage/` | ملفات مشفّرة محلياً |

## 9 الكيانات

| الجدول | أعمدة أساسية |
| --- | --- |
| users | id, username فريد, email, password_hash, created_at |
| files | id, user_id, original_filename, stored_filename, size, mime_type, uploaded_at, metadata |
| logs | id, user_id, action, file_id, ip, timestamp, status, message |
| user_settings | user_id فريد، pbkdf2_iterations افتراضي 200000، algorithm افتراضي AES-256-GCM، max_file_size افتراضي 100، auto_delete افتراضي never، session_timeout افتراضي 120، two_factor افتراضي 0، storage_backend افتراضي local، أعلام الإشعار |

README السابق وثّق users وfiles وlogs. جدول `user_settings` موجود في `init_db` ولم يكن في ذلك الملخص. هذا استكمال من الكود لا إلغاء للوصف القديم.

## 10 الصلاحيات

`require_auth` يرفض API برمز 401 إذا غابت `session['user_id']`. صفحات HTML تعيد التوجيه إلى الدخول.

استعلامات الملفات تقيّد بـ `user_id` الحالي في مسارات القائمة والتنزيل والحذف المقروءة. مستخدم لا يمرَّر له ملف مستخدم آخر عبر هذه الاستعلامات.

## 11 الأتمتة

- `init_db` عند الإقلاع.
- `Config.init_app` ينشئ `DATA_DIR` و`STORAGE_DIR`.
- `log_action` بعد العمليات.
- حقل `auto_delete` يُخزَّن. مهمة حذف دورية غير موجودة في الملفات الحالية كجدولة تعمل وحدها.
- `two_factor` مخزّن بلا إرسال رمز.

## 12 تأثير الوحدات على بعضها

- تغيير `STORAGE_BACKEND` قبل التشغيل يبدّل مكان البايتات بين القرص وS3. الصف في `files` يبقى مرجع الاسم.
- حذف ملف يحذف من التخزين ومن الجدول ويكتب سجل.
- إعدادات PBKDF2 في `user_settings` تخص التشفير في الواجهة. الخادم لا يعيد تشفير الملفات القديمة إذا تغيّر العدد.
- فقدان metadata في الصف يجعل فك الملف في المتصفح غير ممكن حتى لو بقي ciphertext.

## 13 مسرد

| المصطلح | المعنى |
| --- | --- |
| Master Password | كلمة مرور رئيسية تُكتب في المتصفح ولا تُرسل كمفتاح خام للتخزين |
| Data Key | مفتاح عشوائي 32 بايت لتشفير الملف |
| KEK | مفتاح يُشتق بـ PBKDF2 لتشفير Data Key |
| IV | متجه تهيئة 12 بايت لـ AES-GCM |
| metadata | JSON نصي فيه القيم المرمّزة Base64: encrypted_data_key, key_iv, file_iv, salt, pbkdf2_iterations, algorithm |

القيم الرقمية من README السابق مطابقة للوصف: ملح 16 بايت، 200000 تكرار افتراضي، AES-256-GCM.

## 14 أسئلة شائعة

**هل الخادم يقرأ ملفاتي؟** يخزّن ciphertext. فك المحتوى في المتصفح.

**نسيت كلمة المرور الرئيسية؟** لا استرجاع في الكود.

**هل كلمة دخول الحساب هي كلمة التشفير؟** لا. دخول الحساب يُجزَّأ بـ PBKDF2 عبر Werkzeug. كلمة التشفير تبقى في عملية Web Crypto.

**لماذا فشل S3؟** المفاتيح أو اسم الدلو ناقصة، و`StorageManager` يرفع استثناء عند فشل `head_bucket`.

## 15 مخطط المعمارية ASCII

```
المتصفح
  Web Crypto AES-GCM
  app.js
        | session cookie
        v
Flask app.py
  config.py  <- متغيرات بيئة
  utils/security.py
  utils/storage.py
        |                 |
        v                 v
SQLite data/cryptexcloud.db     storage/  أو  S3
```

## 16 التقنيات المستخدمة

- Flask 2.2.5 وWerkzeug 2.2.3
- cryptography 41.0.0 (موجودة في المتطلبات، التشفير التشغيلي للملفات في المتصفح)
- boto3 1.28.0 للتخزين S3
- python-dotenv 1.0.0
- SQLite
- Web Crypto API في الواجهة
- HTML وCSS وJavaScript

## 17 شجرة الملفات

```
CryptexCloud/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── utils/
│   ├── security.py
│   └── storage.py
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── profile.html
│   ├── settings.html
│   └── logs.html
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── fonts/
├── data/          (يُنشأ)
└── storage/       (يُنشأ)
```

ملف `.env` غير موجود داخل قائمة الملفات الحالية. `load_dotenv()` يقرأه إن أضفته أنت. لا تطبع القيم.

## 18 الواجهة الأمامية

`templates` عربية. `static/js/app.js` ينفّذ التشفير والرفع والتنزيل. الإعدادات والملف الشخصي تسحب JSON من `/api/settings` و`/api/profile`.

## 19 الواجهة الخلفية

لا FastAPI.

دوال: `get_db_connection`, `init_db`, `log_action`, `require_auth`, `index`, `login`, `profile`, `settings`, `logs`, `logout`, `register`, `login_api`, `upload_file`, `get_files`, `download_file`, `delete_file`, `get_logs`, `get_settings`, `save_settings`, `get_profile`, `not_found`, `internal_error`.

في `utils/security.py`: `hash_password`, `verify_password`, `generate_unique_filename`, `generate_session_token`, `sanitize_filename`, `validate_user_input`, `get_client_ip`, `log_security_event`.

في `utils/storage.py`: الصنف `StorageManager` ودوال الحفظ والقراءة والحذف المحلي وS3، و`get_storage_manager`.

## 20 تدفق الطلب

1. الصفحة تتحقق من الجلسة.
2. API المحمي يمر على `require_auth`.
3. الرفع يستقبل ملفاً وmetadata، يولّد اسماً فريداً، يستدعي `storage_manager.save_file`، يدرج `files`، ثم `log_action`.
4. التنزيل يتحقق من ملكية `file_id` ويرسل الملف المخزن.
5. الأخطاء 404 و500 تعيد JSON عربي.

## 21 قاعدة البيانات

المسار: `DATA_DIR/cryptexcloud.db` والافتراضي `data/cryptexcloud.db`.

`password_hash` من `generate_password_hash(..., method='pbkdf2:sha256')`.

`metadata` نص JSON وليس أعمدة منفصلة.

## 22 نقاط النهاية

| الطريقة | المسار | الغرض | المعاملات | مصادقة | الرد |
| --- | --- | --- | --- | --- | --- |
| GET | `/` | لوحة الملفات | - | جلسة وإلا توجيه | HTML |
| GET | `/login` | الدخول والتسجيل | - | عام | HTML |
| GET | `/profile` | الملف | - | جلسة | HTML |
| GET | `/settings` | الإعدادات | - | جلسة | HTML |
| GET | `/logs` | السجل | - | جلسة | HTML |
| GET | `/logout` | خروج ومسح الجلسة | - | عام | توجيه |
| POST | `/api/register` | إنشاء مستخدم | username, email, password | لا | JSON |
| POST | `/api/login` | دخول | username, password | لا | JSON + session |
| POST | `/api/upload` | حفظ ملف مشفّر | file, metadata | جلسة | JSON |
| GET | `/api/files` | قائمة المستخدم | - | جلسة | JSON |
| GET | `/api/download/<file_id>` | تنزيل ciphertext | file_id | جلسة وملكية | ملف |
| DELETE | `/api/file/<file_id>` | حذف | file_id | جلسة وملكية | JSON |
| GET | `/api/logs` | سجل المستخدم | - | جلسة | JSON |
| GET | `/api/settings` | قراءة الإعدادات | - | جلسة | JSON |
| POST | `/api/settings` | حفظ الإعدادات | حقول user_settings | جلسة | JSON |
| GET | `/api/profile` | بيانات الحساب | - | جلسة | JSON |

## 23 المصادقة

جلسة Flask. كلمة مرور الحساب تُجزَّأ بـ PBKDF2-SHA256 عبر Werkzeug وتُتحقق بـ `check_password_hash`.

ملفات تعريف الارتباط في `Config.init_app`: `SESSION_COOKIE_HTTPONLY = True`، `SESSION_COOKIE_SAMESITE = Lax`، و`SESSION_COOKIE_SECURE` عندما لا يكون التصحيح مفعلاً.

`session_timeout` في الإعدادات قيمة مخزنة. استنتاج من الكود: `PERMANENT_SESSION_LIFETIME` غير مربوط بهذا الحقل في `config.py`.

## 24 الأمان الموجود فعلياً في الكود

- تجزئة كلمة مرور الحساب.
- تحقق طول كلمة المرور 8 على الأقل عند التسجيل عبر `validate_user_input`.
- استعلامات بمعاملات.
- عزل الملفات بـ user_id.
- حد 100 ميجابايت.
- تنظيف أحرف خطرة في اسم الملف داخل `sanitize_filename`.
- السجل يخزن action وIP ورسالة حالة، لا كلمة المرور الرئيسية.
- `SECRET_KEY` من البيئة مع قيمة افتراضية تطويرية داخل `config.py` (القيمة غير مذكورة).
- `get_client_ip` يثق بأول عنوان في `X-Forwarded-For`.
- CORS غير مذكور في `app.py`.
- لا CSRF token ظاهر على نماذج API المعتمدة على الجلسة.
- المصادقة الثنائية علم قاعدة فقط.

## 25 مفاتيح الإعداد بدون قيم

`config.py` يقرأ عبر `os.getenv`. الأسماء فقط:

| المفتاح | الافتراضي في الكود إن غاب |
| --- | --- |
| FLASK_ENV | development |
| FLASK_DEBUG | يُعد مفعلاً إذا كانت القيمة 1 |
| FLASK_APP | app.py |
| SECRET_KEY | قيمة تطويرية ثابتة في الملف |
| STORAGE_BACKEND | local |
| DATA_DIR | data |
| STORAGE_DIR | storage |
| PBKDF2_ITERATIONS | 200000 |
| AWS_ACCESS_KEY_ID | فارغ |
| AWS_SECRET_ACCESS_KEY | فارغ |
| S3_BUCKET_NAME | فارغ |
| S3_REGION | us-east-1 |
| SMTP_HOST | فارغ |
| SMTP_PORT | 587 |
| SMTP_USER | فارغ |
| SMTP_PASS | فارغ |

SMTP مُعرَّف في الإعدادات. إرسال بريد فعلي غير موجود في `app.py`. أعلام الإشعار تُحفظ فقط.

## 26 التكاملات

- Amazon S3 عند `STORAGE_BACKEND=s3` وحسابات AWS.
- Web Crypto في المتصفح.
- SMTP غير موصول بالإرسال في المسارات الحالية.

## 27 المهام المجدولة

غير موجود في الملفات الحالية. لا Procfile. الحذف التلقائي إعداد مخزّن بلا عامل.

## 28 تخزين الملفات

محلي: `STORAGE_DIR` وأسماء UUID. سحابي: `upload_fileobj` إلى الدلو. القاعدة تحت `DATA_DIR`.

## 29 التسجيل

`logging` بمستوى INFO. `log_action` يكتب جدول `logs`. `logger.error` عند فشل السجل أو S3. لا تُسجَّل كلمات المرور.

## 30 التثبيت من requirements

```
pip install -r requirements.txt
python app.py
```

للتخزين السحابي ضع المفاتيح في بيئة التشغيل بالأسماء أعلاه دون كتابتها في الكود، ثم اضبط `STORAGE_BACKEND`.

متطلب README السابق: Python 3.10.6 ومتصفح يدعم Web Crypto. لا قيد إصدار داخل ملف Python.

## 31 دليل التطوير

- التشفير الحقيقي للملف في `static/js/app.js`. لا تنقل المفتاح إلى الخادم.
- اختبر الرفع والتنزيل ثم طابق البصمة محلياً.
- إن غيّرت شكل metadata حدّث الواجهة وعمود الحفظ معاً.
- أبقِ `.env` خارج أي مستودع.

## 32 النشر

غير موجود في الملفات الحالية: Procfile أو دليل Heroku. التشغيل الموصوف: `python app.py`.

## 33 النسخ الاحتياطي

انسخ مجلد `data/` (القاعدة) ومجلد `storage/` إن كان التخزين محلياً. على S3 انسخ الكائنات في الدلو مع صفوف `files` لأن metadata جزء من الاسترجاع. كلمة المرور الرئيسية تبقى مع المستخدم خارج هذه الملفات.

## 34 استكشاف الأخطاء

| العرض | ما تفحصه |
| --- | --- |
| الخط لا يظهر | `static/fonts/` |
| خطأ قاعدة | مجلد `data` قابل للكتابة |
| خطأ تخزين | مجلد `storage` أو صلاحيات S3 |
| فشل فك التشفير | كلمة مرور رئيسية مختلفة أو metadata ناقصة أو متصفح بلا Web Crypto |
| 401 | الجلسة انتهت أو الطلب بلا كوكي |

## 35 الاعتماديات مع الإصدارات من requirements.txt

| الحزمة | الإصدار |
| --- | --- |
| Flask | 2.2.5 |
| boto3 | 1.28.0 |
| cryptography | 41.0.0 |
| python-dotenv | 1.0.0 |
| Werkzeug | 2.2.3 |

## 36 القيود

- لا استعادة بلا كلمة المرور الرئيسية والبيانات الوصفية.
- المصادقة الثنائية غير مفعّلة سلوكياً.
- مهلة الجلسة المخزنة غير مربوطة بوقت الجلسة.
- SMTP غير مرسل.
- الحذف التلقائي غير مجدول.
- الاعتماد على `X-Forwarded-For` بلا طبقة موثوقة يزيّف IP في السجل.
- قيمة SECRET_KEY الافتراضية للتطوير تبقى إن لم تُضبط البيئة.

## 37 الحالة الحالية

تطبيق محلي كامل للتسجيل والرفع المشفر من المتصفح والسجل والإعدادات. S3 جاهز في الكود عند ضبط البيئة. الإشعارات البريدية والمصادقة الثنائية حقول فقط.

## 38 قرارات المعمارية

- تشفير من طرف العميل حتى لا يملك الخادم Data Key مفكوكاً.
- metadata في عمود JSON واحد.
- تخزين قابل للتبديل بين قرص وS3 خلف `StorageManager`.
- كلمة مرور الحساب منفصلة عن كلمة التشفير.
- سجل عمليات بلا محتوى الملف.

## 39 سجل التغييرات

غير موثق. لا رقم إصدار تطبيق في `config.py` ولا في `requirements.txt`.

## System Overview

المتصفح يشفّر الملف بكلمة مرور رئيسية ويرفع ciphertext. Flask يحفظه مع metadata ويسجّل العملية. التنزيل يعيد ciphertext ليفكّه المتصفح. الخادم لا يحتفظ بمفتاح فك.

## Quick Reference

| البند | القيمة |
| --- | --- |
| تشغيل | `python app.py` |
| قاعدة | `data/cryptexcloud.db` |
| ملفات | `storage/` أو S3 |
| حد الرفع | 100 ميجابايت |
| تجزئة الحساب | pbkdf2:sha256 |
| تشفير الملف | AES-256-GCM في المتصفح |
| تكرارات افتراضية | 200000 |

## Quick Start

```
pip install -r requirements.txt
python app.py
```

أنشئ مستخدماً من صفحة الدخول، ارفع ملفاً صغيراً، نزّله، وتأكد أن المحتوى عاد كما كان.

## For Non-Technical Users

كلمة دخول الموقع تفتح حسابك. كلمة المرور الرئيسية تفتح ملفاتك. احفظ الثانية في مكان آمن خارج البرنامج. إذا ضاعت لا يستطيع صاحب الخادم إرجاع الملفات. راجع صفحة السجل لمعرفة عمليات الرفع والتنزيل على حسابك.

## For Developers

اقرأ `config.py` لأسماء البيئة، و`utils/storage.py` لمسار الحفظ، و`app.js` لتفاصيل Web Crypto. لا تسجّل metadata المفكوك. لا تضع مفاتيح AWS في الكود. علم `two_factor` وحقل SMTP بحاجة إلى تنفيذ لاحق إن رغبت بسلوك حقيقي.
