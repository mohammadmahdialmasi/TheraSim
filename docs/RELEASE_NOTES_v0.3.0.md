# TheraSim v0.3.0 — Release notes

## English

TheraSim v0.3.0 consolidates local model configuration, bilingual settings
and support, release metadata checks, and Windows portable-package
verification. The package is a Windows x64 one-folder ZIP, not an installer or
a single-file executable.

### Changes

- Configure patient-agent and evaluator-agent model IDs separately for each
  supported OpenAI-compatible provider. Either role can fall back to that
  provider's general model. Provider settings take effect for agents after
  application restart.
- Keep strict ACT report validation in the application. Provider-side
  structured output is only a generation aid; rubric coverage, schema,
  transcript message/speaker references, and exact evidence quotes are still
  checked and invalid reports are rejected.
- Offer optional, user-initiated hardware inventory. It reports limited
  system facts and estimates; it does not select or download models and does
  not establish compatibility across hardware.
- Document measured local synthetic model tests, including contract failures.
  No ACT evaluator model is recommended.
- Add bilingual provider configuration, support-diagnostics preview/export,
  current-version display, and manual stable-release metadata/checksum
  verification. Update checks never install or overwrite application files.
- Protect saved Windows provider keys with the current user's DPAPI context.
  On non-Windows platforms, persistent provider-key storage is not supported;
  use environment variables.
- Align the portable package name as
  `TheraSim-v0.3.0-Windows-x64-Portable.zip`, verify the package's SQL
  migration allowlist, and generate a SHA-256 sidecar and build manifest.
- Add bilingual installation and user guides.

### Install on Windows

Download the ZIP and matching `.sha256` sidecar from the
[v0.3.0 GitHub Release](https://github.com/mohammadmahdialmasi/TheraSim/releases)
only after the release's Windows workflow has passed. Verify the SHA-256
before extracting the ZIP to a user-writable directory, then run
`TheraSim\TheraSim.exe`. No administrator access or installer is required.
Application data stays outside the extracted application folder under
`%LOCALAPPDATA%\TheraSim`. Model weights are not included.

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
materials it identifies. It does **not** license executable source code or
the Windows binary. Unless a separate software license is provided, the
source code remains all rights reserved by its copyright holder. Third-party
dependencies and materials keep their own license terms.

## فارسی

نسخهٔ TheraSim 0.3.0 تنظیم مدل‌های محلی، تنظیمات و پشتیبانی دوزبانه، بررسی
فرادادهٔ انتشار و راستی‌آزمایی بستهٔ قابل‌حمل ویندوز را یکپارچه می‌کند. بسته،
ZIP پوشه‌ای ویندوز x64 است؛ نصب‌کننده یا فایل اجرایی تک‌فایلی نیست.

### تغییرها

- شناسهٔ مدل بیمار شبیه‌سازی‌شده و ارزیاب را برای هر ارائه‌دهندهٔ سازگار با
  OpenAI جداگانه تنظیم کنید. هر نقش می‌تواند به مدل عمومی همان ارائه‌دهنده
  برگردد. عامل‌ها پس از راه‌اندازی مجدد برنامه، تنظیمات را اعمال می‌کنند.
- اعتبارسنجی سخت‌گیرانهٔ گزارش ACT در خود برنامه حفظ شده است. خروجی ساختاریافتهٔ
  ارائه‌دهنده فقط کمکی برای تولید است؛ پوشش روبریک، ساختار، شناسه و گویندهٔ پیام
  گفتگو، و نقل‌قول دقیق شواهد همچنان بررسی می‌شوند و گزارش نامعتبر رد می‌شود.
- بررسی سخت‌افزار اختیاری و با درخواست کاربر ارائه شده است. فقط اطلاعات و
  برآوردهای محدود سیستم را گزارش می‌کند؛ مدل انتخاب یا دریافت نمی‌کند و
  سازگاری را در همهٔ سخت‌افزارها اثبات نمی‌کند.
- آزمون‌های محلی و داستانی مدل‌ها، از جمله شکست‌های قرارداد خروجی، مستند شده‌اند.
  هیچ مدل ارزیاب ACT توصیه نمی‌شود.
- پیکربندی ارائه‌دهنده، پیش‌نمایش/خروجی تشخیصی پشتیبانی، نمایش نسخهٔ نصب‌شده و
  بررسی دستی فرادادهٔ انتشار پایدار و checksum دوزبانه شده‌اند. بررسی به‌روزرسانی
  فایلی را نصب یا جایگزین نمی‌کند.
- کلیدهای ارائه‌دهنده که در ویندوز ذخیره می‌شوند با DPAPI کاربر جاری محافظت
  می‌شوند. ذخیرهٔ پایدار کلید در سیستم‌عامل‌های غیر ویندوز پشتیبانی نمی‌شود؛ از
  متغیرهای محیطی استفاده کنید.
- نام بستهٔ قابل‌حمل به
  `TheraSim-v0.3.0-Windows-x64-Portable.zip` یکسان شده و فهرست مجاز مهاجرت‌های
  SQL بررسی می‌شود؛ فایل SHA-256 و مانیفست ساخت نیز تولید می‌شوند.
- راهنماهای نصب و کاربر به فارسی و انگلیسی افزوده شده‌اند.

### نصب در ویندوز

ZIP و فایل `.sha256` متناظر را فقط از
[انتشار GitHub نسخهٔ 0.3.0](https://github.com/mohammadmahdialmasi/TheraSim/releases)
و پس از موفقیت گردش‌کار ویندوز دریافت کنید. پیش از استخراج SHA-256 را بررسی
کنید؛ سپس ZIP را در پوشه‌ای قابل‌نوشتن برای کاربر استخراج و
`TheraSim\TheraSim.exe` را اجرا کنید. نصب‌کننده یا دسترسی مدیر لازم نیست. دادهٔ
برنامه جدا از پوشهٔ استخراج‌شده و در `%LOCALAPPDATA%\TheraSim` نگهداری می‌شود.
وزن مدل همراه برنامه نیست.

### دامنه و ایمنی

فقط از داده‌های داستانی و ساختگی استفاده کنید. ACT تنها رویکرد اجرایی است.
TheraSim نمونه‌ای آزمایشی برای پژوهش و آموزش است؛ روان‌درمانی، تشخیص، توصیهٔ
بالینی، نظارت حرفه‌ای، گواهی صلاحیت یا سنجش معتبر مهارت ارائه نمی‌کند. اعتبار
ارزیاب، روبریک، تحلیل‌ها و پاسخ‌های شبیه‌سازی‌شده اثبات نشده است. موفقیت آزمون‌ها
یا ساخت بسته، اعتبار بالینی یا امنیتی را تأیید نمی‌کند. محلی‌محور بودن تضمین
نمی‌کند نصب کاملاً بدون اینترنت باشد؛ پیش از ارسال متن نشانی ارائه‌دهنده را
بررسی کنید.

### مجوز

`LICENSE.md` مجوز CC BY 4.0 را فقط برای مستندات و مواد پژوهشیِ اصیلی اعمال
می‌کند که در آن مشخص شده‌اند. این مجوز **کد اجرایی یا فایل اجرایی ویندوز را
پوشش نمی‌دهد**. تا زمانی که مجوز نرم‌افزاری جداگانه‌ای ارائه نشود، حقوق کد منبع
برای دارندهٔ حق نشر محفوظ است. وابستگی‌ها و مواد اشخاص ثالث تابع شرایط مجوز خود
هستند.
