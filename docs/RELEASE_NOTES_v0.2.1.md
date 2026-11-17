# TheraSim v0.2.1 — Release notes

## English

TheraSim v0.2.1 is a corrective patch for the public v0.2.0 Windows package.
The existing v0.2.0 release and tag remain unchanged.

### Changes

- The Windows package now includes only `.sql` files from the operational and
  restricted migration directories. Package verification compares the archive
  with that exact source allowlist and rejects backup files.
- Windows CI runs backend tests with a fresh temporary data directory and
  builds and smoke-tests the versioned package.
- Persian labels for persisted feature statuses and errors are improved.
  User/model text and identifiers use automatic or explicit text direction to
  remain readable in right-to-left layouts.
- Application and package version metadata is `0.2.1`.

### Install on Windows

Download `TheraSim-v0.2.1-windows-x64.zip` and its `.sha256` sidecar from the
[v0.2.1 GitHub Release](https://github.com/mohammadmahdialmasi/TheraSim/releases)
after publication. Verify the SHA-256 value before extracting the ZIP to a
user-writable folder, then run `TheraSim\TheraSim.exe`. No administrator
access or installer is required. The application binds to loopback and keeps
its data and logs under `%LOCALAPPDATA%\TheraSim`. Model weights are not
included; model-backed workflows require a separately installed provider.
See [`INSTALL_WINDOWS.md`](../INSTALL_WINDOWS.md) for complete instructions.

### Scope and safety

Use synthetic, fictional data only. ACT is the only runnable modality.
TheraSim is an experimental research/educational prototype, not psychotherapy,
diagnosis, clinical advice, professional supervision, certification, or a
validated measure of competence. Evaluator, rubric, analytics, and simulated
response validity has not been established. A passing build or test suite is
not clinical or security validation. Local-first operation does not guarantee
an air-gapped installation; check the configured model-provider endpoint
before sending text.

### Licensing

`LICENSE.md` applies CC BY 4.0 only to the original documentation and research
materials it identifies. It does **not** license the executable source code
or the Windows binary. Unless a separate software license is provided, the
source code remains all rights reserved by its copyright holder. Third-party
dependencies and materials keep their own license terms.

## فارسی

نسخهٔ TheraSim 0.2.1 یک نسخهٔ اصلاحی برای بستهٔ ویندوز عمومیِ 0.2.0 است.
نسخه و برچسب انتشار موجودِ 0.2.0 بدون تغییر باقی می‌مانند.

### تغییرها

- بستهٔ ویندوز اکنون فقط فایل‌های `.sql` را از پوشه‌های مهاجرت عملیاتی و
  محدودشده وارد می‌کند. بررسی بسته، آرشیو را با همین فهرست دقیقِ فایل‌های منبع
  مقایسه و فایل‌های پشتیبان را رد می‌کند.
- گردش‌کار ویندوز، آزمون‌های بک‌اند را با مسیر دادهٔ موقت و تازه اجرا می‌کند و
  بستهٔ نسخه‌بندی‌شده را می‌سازد و به‌صورت ایزوله آزمایش می‌کند.
- برچسب‌های فارسیِ وضعیت‌های ذخیره‌شده و خطاهای پنل‌ها بهبود یافته‌اند.
  جهت متن کاربر/مدل و شناسه‌ها به‌صورت خودکار یا صریح تنظیم می‌شود تا در چیدمان
  راست‌به‌چپ خوانا بمانند.
- فرادادهٔ نسخهٔ برنامه و بسته `0.2.1` است.

### نصب در ویندوز

پس از انتشار، فایل `TheraSim-v0.2.1-windows-x64.zip` و فایل `.sha256` آن را از
[انتشار GitHub نسخهٔ 0.2.1](https://github.com/mohammadmahdialmasi/TheraSim/releases)
دریافت کنید. پیش از استخراج، مقدار SHA-256 را بررسی کنید؛ سپس ZIP را در پوشه‌ای
قابل‌نوشتن برای کاربر استخراج و `TheraSim\TheraSim.exe` را اجرا کنید. نصب‌کننده
یا دسترسی مدیر لازم نیست. برنامه فقط به loopback متصل می‌شود و داده‌ها و
گزارش‌ها را در `%LOCALAPPDATA%\TheraSim` نگه می‌دارد. وزن مدل زبانی همراه بسته
نیست؛ جریان‌های کاری وابسته به مدل به ارائه‌دهنده‌ای نیاز دارند که جداگانه
نصب شده باشد. راهنمای کامل در [`INSTALL_WINDOWS.md`](../INSTALL_WINDOWS.md)
آمده است.

### دامنه و ایمنی

فقط از داده‌های داستانی و ساختگی استفاده کنید. ACT تنها رویکرد اجرایی است.
TheraSim نمونهٔ اولیه‌ای آزمایشی برای پژوهش و آموزش است؛ روان‌درمانی، تشخیص،
توصیهٔ بالینی، نظارت حرفه‌ای، گواهی صلاحیت یا سنجش معتبر مهارت ارائه نمی‌کند.
اعتبار ارزیاب، روبریک، تحلیل و پاسخ‌های شبیه‌سازی‌شده اثبات نشده است. موفقیت
آزمون‌ها یا ساخت بسته، اعتبار بالینی یا امنیتی را تأیید نمی‌کند. محلی‌محور بودن
تضمین‌کنندهٔ نصب بدون اینترنت نیست؛ پیش از ارسال متن، نشانی ارائه‌دهندهٔ مدل را
بررسی کنید.

### مجوز

`LICENSE.md` مجوز CC BY 4.0 را فقط برای مستندات و مواد پژوهشیِ اصیلی اعمال
می‌کند که در آن مشخص شده‌اند. این مجوز **کد اجرایی یا فایل اجرایی ویندوز را
پوشش نمی‌دهد**. تا زمانی که مجوز نرم‌افزاری جداگانه‌ای ارائه نشود، حقوق کد
منبع برای دارندهٔ حق نشر محفوظ است. وابستگی‌ها و مواد اشخاص ثالث تابع شرایط
مجوز خود هستند.
