// CryptexCloud - JavaScript Client-Side Encryption
// يستخدم Web Crypto API حصرياً للتشفير

class CryptexCloud {
    constructor() {
        this.algorithm = 'AES-GCM';
        this.keyLength = 256;
        this.ivLength = 12; // 96 bits for GCM
        this.saltLength = 16;
        this.pbkdf2Iterations = 200000;
        this.masterPassword = '';
        this.rememberPassword = false;
    }

    // توليد مفتاح عشوائي
    async generateRandomKey(length = 32) {
        return window.crypto.getRandomValues(new Uint8Array(length));
    }

    // توليد IV عشوائي
    async generateIV() {
        return window.crypto.getRandomValues(new Uint8Array(this.ivLength));
    }

    // توليد salt عشوائي
    async generateSalt() {
        return window.crypto.getRandomValues(new Uint8Array(this.saltLength));
    }

    // تحويل ArrayBuffer إلى Base64
    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }

    // تحويل Base64 إلى ArrayBuffer
    base64ToArrayBuffer(base64) {
        const binary = window.atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    // اشتقاق مفتاح من كلمة المرور باستخدام PBKDF2
    async deriveKey(password, salt, iterations = this.pbkdf2Iterations) {
        const encoder = new TextEncoder();
        const passwordBuffer = encoder.encode(password);
        const saltBuffer = new Uint8Array(salt);

        // استيراد كلمة المرور كمفتاح
        const keyMaterial = await window.crypto.subtle.importKey(
            'raw',
            passwordBuffer,
            'PBKDF2',
            false,
            ['deriveKey']
        );

        // اشتقاق المفتاح باستخدام PBKDF2
        const derivedKey = await window.crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: saltBuffer,
                iterations: iterations,
                hash: 'SHA-256'
            },
            keyMaterial,
            {
                name: this.algorithm,
                length: this.keyLength
            },
            false,
            ['encrypt', 'decrypt']
        );

        return derivedKey;
    }

    // تشفير مفتاح البيانات
    async encryptDataKey(dataKey, kek, iv) {
        const encrypted = await window.crypto.subtle.encrypt(
            {
                name: this.algorithm,
                iv: new Uint8Array(iv)
            },
            kek,
            dataKey
        );

        return encrypted;
    }

    // فك تشفير مفتاح البيانات
    async decryptDataKey(encryptedDataKey, kek, iv) {
        try {
            // التحقق من صحة IV
            if (!iv || iv.byteLength !== this.ivLength) {
                throw new Error(`IV غير صحيح. الطول المتوقع: ${this.ivLength} بايت، الطول الفعلي: ${iv.byteLength || 0} بايت`);
            }

            // التحقق من صحة البيانات المشفّرة
            if (!encryptedDataKey || encryptedDataKey.byteLength === 0) {
                throw new Error('مفتاح البيانات المشفّر فارغ أو غير صحيح');
            }

            const ivArray = new Uint8Array(iv);
            const decrypted = await window.crypto.subtle.decrypt(
                {
                    name: this.algorithm,
                    iv: ivArray
                },
                kek,
                encryptedDataKey
            );

            return decrypted;
        } catch (error) {
            console.error('خطأ في فك تشفير مفتاح البيانات:', error);
            if (error.name === 'OperationError') {
                throw new Error('فشل في فك تشفير مفتاح البيانات. تحقق من كلمة المرور');
            }
            throw error;
        }
    }

    // تشفير الملف
    async encryptFile(file, masterPassword) {
        try {
            // قراءة الملف كـ ArrayBuffer
            const fileBuffer = await file.arrayBuffer();

            // توليد مفتاح البيانات العشوائي
            const dataKey = await this.generateRandomKey(32);

            // توليد IV للملف
            const fileIV = await this.generateIV();

            // توليد salt لاشتقاق KEK
            const salt = await this.generateSalt();

            // اشتقاق KEK من كلمة المرور
            const kek = await this.deriveKey(masterPassword, salt);

            // تشفير مفتاح البيانات
            const keyIV = await this.generateIV();
            const encryptedDataKey = await this.encryptDataKey(dataKey, kek, keyIV);

            // استيراد مفتاح البيانات
            const importedDataKey = await window.crypto.subtle.importKey(
                'raw',
                dataKey,
                this.algorithm,
                false,
                ['encrypt']
            );

            // تشفير الملف
            const encryptedFile = await window.crypto.subtle.encrypt(
                {
                    name: this.algorithm,
                    iv: fileIV
                },
                importedDataKey,
                fileBuffer
            );

            // إعداد البيانات الوصفية
            const metadata = {
                encrypted_data_key: this.arrayBufferToBase64(encryptedDataKey),
                key_iv: this.arrayBufferToBase64(keyIV),
                file_iv: this.arrayBufferToBase64(fileIV),
                salt: this.arrayBufferToBase64(salt),
                pbkdf2_iterations: this.pbkdf2Iterations,
                algorithm: 'AES-256-GCM'
            };

            return {
                encryptedData: encryptedFile,
                metadata: metadata
            };

        } catch (error) {
            console.error('خطأ في تشفير الملف:', error);
            throw new Error('فشل في تشفير الملف: ' + error.message);
        }
    }

    // فك تشفير الملف
    async decryptFile(encryptedData, metadata, masterPassword = null) {
        try {
            // استخدام كلمة المرور الممررة أو المحفوظة
            const password = masterPassword || this.masterPassword;

            if (!password) {
                throw new Error('كلمة المرور الرئيسية مطلوبة لفك التشفير');
            }

            // التحقق من صحة البيانات الوصفية
            if (!metadata || !metadata.encrypted_data_key || !metadata.key_iv || !metadata.file_iv || !metadata.salt) {
                throw new Error('البيانات الوصفية غير صحيحة أو ناقصة');
            }

            // تحويل البيانات الوصفية
            let encryptedDataKey, keyIV, fileIV, salt;
            try {
                encryptedDataKey = this.base64ToArrayBuffer(metadata.encrypted_data_key);
                keyIV = this.base64ToArrayBuffer(metadata.key_iv);
                fileIV = this.base64ToArrayBuffer(metadata.file_iv);
                salt = this.base64ToArrayBuffer(metadata.salt);
            } catch (e) {
                throw new Error('فشل في تحويل البيانات الوصفية: ' + e.message);
            }

            const iterations = metadata.pbkdf2_iterations || this.pbkdf2Iterations;

            // التحقق من صحة IVs
            if (keyIV.byteLength !== this.ivLength || fileIV.byteLength !== this.ivLength) {
                throw new Error(`طول IV غير صحيح. المتوقع: ${this.ivLength} بايت`);
            }

            // اشتقاق KEK من كلمة المرور
            const kek = await this.deriveKey(password, salt, iterations);

            // فك تشفير مفتاح البيانات
            const dataKeyBuffer = await this.decryptDataKey(encryptedDataKey, kek, keyIV);

            // استيراد مفتاح البيانات
            const dataKey = await window.crypto.subtle.importKey(
                'raw',
                dataKeyBuffer,
                this.algorithm,
                false,
                ['decrypt']
            );

            // التحقق من صحة البيانات المشفّرة
            if (!encryptedData || encryptedData.byteLength === 0) {
                throw new Error('البيانات المشفّرة فارغة أو غير صحيحة');
            }

            // في AES-GCM، يجب أن يكون طول البيانات المشفّرة على الأقل 16 بايت (حجم authentication tag)
            if (encryptedData.byteLength < 16) {
                throw new Error('البيانات المشفّرة قصيرة جداً');
            }

            // فك تشفير الملف
            const decryptedData = await window.crypto.subtle.decrypt(
                {
                    name: this.algorithm,
                    iv: new Uint8Array(fileIV)
                },
                dataKey,
                encryptedData
            );

            return decryptedData;

        } catch (error) {
            console.error('خطأ في فك تشفير الملف:', error);

            // رسائل خطأ أكثر وضوحاً
            let errorMessage = 'فشل في فك تشفير الملف';
            if (error.name === 'OperationError') {
                errorMessage = 'فشل في فك التشفير. قد تكون كلمة المرور غير صحيحة أو الملف تالف';
            } else if (error.message.includes('كلمة المرور')) {
                errorMessage = error.message;
            } else {
                errorMessage += ': ' + error.message;
            }

            throw new Error(errorMessage);
        }
    }

    // رفع ملف مشفّر
    async uploadEncryptedFile(file, metadata) {
        try {
            const formData = new FormData();

            // إضافة الملف المشفّر
            const encryptedBlob = new Blob([metadata.encryptedData], { type: 'application/octet-stream' });
            formData.append('file', encryptedBlob, file.name + '.encrypted');

            // إضافة البيانات الوصفية
            formData.append('original_filename', file.name);
            formData.append('size', file.size.toString());
            formData.append('mime_type', file.type || 'application/octet-stream');
            formData.append('encrypted_data_key', metadata.metadata.encrypted_data_key);
            formData.append('key_iv', metadata.metadata.key_iv);
            formData.append('file_iv', metadata.metadata.file_iv);
            formData.append('salt', metadata.metadata.salt);
            formData.append('pbkdf2_iterations', metadata.metadata.pbkdf2_iterations.toString());
            formData.append('algorithm', metadata.metadata.algorithm);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'فشل في رفع الملف');
            }

            return result;

        } catch (error) {
            console.error('خطأ في رفع الملف:', error);
            throw error;
        }
    }

    // تشفير ورفع ملف
    async encryptAndUploadFile(file, masterPassword) {
        try {
            // تحديث شريط التقدم - بدء التشفير
            updateProgress('encryption', 0, 'جاري التشفير...');

            // تشفير الملف
            const encryptedResult = await this.encryptFile(file, masterPassword);

            // تحديث شريط التقدم - انتهاء التشفير
            updateProgress('encryption', 100, 'تم التشفير');

            // تحديث شريط التقدم - بدء الرفع
            updateProgress('upload', 0, 'جاري الرفع...');

            // رفع الملف المشفّر
            const uploadResult = await this.uploadEncryptedFile(file, encryptedResult);

            // تحديث شريط التقدم - انتهاء الرفع
            updateProgress('upload', 100, 'تم الرفع بنجاح');

            return uploadResult;

        } catch (error) {
            updateProgress('encryption', 0, 'فشل في التشفير');
            updateProgress('upload', 0, 'فشل في الرفع');
            throw error;
        }
    }

    // تحميل وفك تشفير ملف
    async downloadAndDecryptFile(fileId) {
        try {
            const response = await fetch(`/api/download/${fileId}`);

            if (!response.ok) {
                throw new Error('فشل في تحميل الملف');
            }

            // الحصول على البيانات الوصفية من الرؤوس
            const metadata = JSON.parse(response.headers.get('X-Metadata') || '{}');
            const originalFilename = response.headers.get('X-Original-Filename') || 'file';
            const mimeType = response.headers.get('X-Mime-Type') || 'application/octet-stream';

            // تحميل الملف المشفّر
            const encryptedData = await response.arrayBuffer();

            // فك التشفير
            const decryptedData = await this.decryptFile(encryptedData, metadata);

            // إنشاء وتحميل الملف المفكوك
            const blob = new Blob([decryptedData], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = originalFilename;
            a.click();
            URL.revokeObjectURL(url);

            return true;

        } catch (error) {
            console.error('خطأ في تحميل الملف:', error);
            throw error;
        }
    }

    // تعيين كلمة المرور الرئيسية
    setMasterPassword(password, remember = false) {
        this.masterPassword = password;
        this.rememberPassword = remember;

        if (remember) {
            // حفظ في sessionStorage (يُمسح عند إغلاق المتصفح)
            sessionStorage.setItem('cryptex_master_password', password);
        } else {
            sessionStorage.removeItem('cryptex_master_password');
        }
    }

    // الحصول على كلمة المرور المحفوظة
    getStoredMasterPassword() {
        return sessionStorage.getItem('cryptex_master_password');
    }

    // مسح كلمة المرور المحفوظة
    clearStoredMasterPassword() {
        sessionStorage.removeItem('cryptex_master_password');
        this.masterPassword = '';
        this.rememberPassword = false;
    }
}

// إنشاء مثيل عام من CryptexCloud
const cryptex = new CryptexCloud();

// دوال مساعدة للواجهة
function updateProgress(type, percent, status) {
    const progressBar = document.getElementById(type + 'Progress');
    const statusText = document.getElementById(type + 'Status');

    if (progressBar && statusText) {
        progressBar.style.width = percent + '%';
        statusText.textContent = status;
    }
}

function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    if (messageDiv) {
        messageDiv.textContent = text;
        messageDiv.className = `message ${type}`;
        messageDiv.style.display = 'block';

        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 5000);
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 بايت';
    const k = 1024;
    const sizes = ['بايت', 'كيلوبايت', 'ميجابايت', 'جيجابايت'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US') + ' ' + date.toLocaleTimeString('en-US');
}

// التحقق من دعم Web Crypto API
if (!window.crypto || !window.crypto.subtle) {
    console.error('Web Crypto API غير مدعوم في هذا المتصفح');
    showMessage('هذا المتصفح لا يدعم التشفير المطلوب. يرجى استخدام متصفح حديث.', 'error');
}

// تهيئة كلمة المرور المحفوظة عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function () {
    const storedPassword = cryptex.getStoredMasterPassword();
    if (storedPassword) {
        cryptex.setMasterPassword(storedPassword, true);
        const rememberCheckbox = document.getElementById('rememberPassword');
        if (rememberCheckbox) {
            rememberCheckbox.checked = true;
        }
    }
});

// دوال الانيميشن
function createCodeRain() {
    const codeRain = document.createElement('div');
    codeRain.className = 'code-rain';
    document.body.appendChild(codeRain);

    const codeChars = ['0', '1', 'A', 'B', 'C', 'D', 'E', 'F', 'تشفير', 'أمان', 'حماية', 'مفتاح', 'قفل', 'درع'];

    for (let i = 0; i < 50; i++) {
        const char = document.createElement('div');
        char.className = 'code-char';
        char.textContent = codeChars[Math.floor(Math.random() * codeChars.length)];
        char.style.left = Math.random() * 100 + '%';
        char.style.animationDelay = Math.random() * 3 + 's';
        char.style.animationDuration = (Math.random() * 2 + 2) + 's';
        codeRain.appendChild(char);
    }

    return codeRain;
}

function removeCodeRain() {
    const codeRain = document.querySelector('.code-rain');
    if (codeRain) {
        codeRain.remove();
    }
}

function animateProgress(progressBar, targetPercent, duration = 1000) {
    let start = 0;
    const increment = targetPercent / (duration / 16);

    const timer = setInterval(() => {
        start += increment;
        progressBar.style.width = Math.min(start, targetPercent) + '%';

        if (start >= targetPercent) {
            clearInterval(timer);
        }
    }, 16);
}

function showAnimatedMessage(text, type) {
    const messageDiv = document.getElementById('message');
    if (messageDiv) {
        messageDiv.textContent = text;
        messageDiv.className = `message ${type} message-enhanced fade-in-up`;
        messageDiv.style.display = 'block';

        // إضافة أيقونة حسب النوع
        const icon = type === 'success' ? '<span class="icon-success"></span>' : type === 'error' ? '<span class="icon-error"></span>' : type === 'info' ? '<span class="icon-info"></span>' : '<span class="icon-warning"></span>';
        messageDiv.innerHTML = `${icon} ${text}`;

        setTimeout(() => {
            messageDiv.style.display = 'none';
            messageDiv.classList.remove('message-enhanced', 'fade-in-up');
        }, 5000);
    }
}

function animateFileUpload(fileName) {
    // إضافة ملف إلى القائمة مع انيميشن
    const tbody = document.getElementById('filesTableBody');
    if (tbody) {
        const row = document.createElement('tr');
        row.className = 'file-item uploading fade-in-up';
        row.innerHTML = `
            <td class="filename">${fileName} <span class="encrypt-icon icon-encrypt"></span></td>
            <td>جاري الرفع...</td>
            <td>الآن</td>
            <td class="actions">
                <button class="btn btn-sm btn-secondary" disabled>جاري الرفع</button>
            </td>
        `;
        tbody.insertBefore(row, tbody.firstChild);
        return row;
    }
    return null;
}

function updateFileStatus(row, status, message) {
    if (row) {
        row.classList.remove('uploading');
        row.classList.add(status);

        const statusCell = row.querySelector('td:nth-child(2)');
        const actionCell = row.querySelector('.actions');

        if (statusCell && actionCell) {
            statusCell.textContent = message;

            if (status === 'success') {
                actionCell.innerHTML = `
                    <button class="btn btn-sm btn-primary" onclick="downloadFile(${row.dataset.fileId || ''})"><span class="icon-download"></span> تحميل</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteFile(${row.dataset.fileId || ''}, '${row.dataset.fileName || ''}')"><span class="icon-delete"></span> حذف</button>
                `;
                row.classList.add('success-animation');
            } else if (status === 'error') {
                actionCell.innerHTML = `
                    <button class="btn btn-sm btn-secondary" disabled><span class="icon-error"></span> فشل</button>
                `;
                row.classList.add('error-animation');
            }
        }
    }
}

// تصدير للاستخدام العام
window.CryptexCloud = CryptexCloud;
window.cryptex = cryptex;
window.createCodeRain = createCodeRain;
window.removeCodeRain = removeCodeRain;
window.animateProgress = animateProgress;
window.showAnimatedMessage = showAnimatedMessage;
window.animateFileUpload = animateFileUpload;
window.updateFileStatus = updateFileStatus;
