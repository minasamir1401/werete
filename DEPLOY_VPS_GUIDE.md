# 🚀 دليل نشر الباك إند على سيرفر Linux (VPS)

هذا المشروع جاهز تماماً للعمل على سيرفرات Linux (مثل Ubuntu 22.04 أو أحدث) التي تستخدمها DigitalOcean أو AWS أو غيرها.

## 🛠 المتطلبات الأساسية
- سيرفر VPS نظيف بنظام Ubuntu.
- الوصول عبر SSH.

## 📥 خطوات التثبيت السريع

1. **انقل المشروع إلى السيرفر**
   يمكنك فعل ذلك باستخدام Git أو SCP.
   ```bash
   git clone https://github.com/minasamir1401/golomi.git
   cd golomi/Back-End
   ```

2. **تشغيل سكربت الإعداد التلقائي**
   قمنا بإنشاء ملف `setup_linux.sh` ليقوم بكل شيء بدلاً منك.
   ```bash
   chmod +x setup_linux.sh
   ./setup_linux.sh
   ```

3. **تشغيل السيرفر**
   لديك خياران:
   
   **الخيار الأول: التشغيل المباشر (للتجربة)**
   ```bash
   chmod +x run_linux.sh
   ./run_linux.sh
   ```

   **الخيار الثاني: التشغيل المستمر (للإنتاج - Production)**
   نستخدم `systemd` لضمان عمل السيرفر 24 ساعة حتى لو أعدت تشغيل الجهاز.
   
   أنشئ ملف خدمة جديد:
   ```bash
   sudo nano /etc/systemd/system/gold-backend.service
   ```
   
   ضع فيه المحتوى التالي (مع تغيير المسارات حسب مكان مشروعك):
   ```ini
   [Unit]
   Description=Gold Backend Service
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/path/to/golomi/Back-End
   ExecStart=/path/to/golomi/Back-End/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   
   ثم قم بتفعيل الخدمة:
   ```bash
   sudo systemctl enable gold-backend
   sudo systemctl start gold-backend
   ```

## 🌐 ملاحظات مهمة
- الباك إند سيعمل على المنفذ `8000`. تأكد من فتح هذا المنفذ في جدار الحماية (Firewall) إذا لزم الأمر:
  ```bash
  sudo ufw allow 8000
  ```
- قاعدة البيانات `gold_prices.db` (SQLite) ستعمل تلقائياً ولن تحتاج لتثبيت MySQL أو PostgreSQL.
