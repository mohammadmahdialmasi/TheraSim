# Install and run TheraSim on Windows

## Download and verify

Download the Windows x64 ZIP and its `.sha256` file from the GitHub Release.
Before extracting, verify the hash in PowerShell:

```powershell
$expected = (Get-Content .\TheraSim-v0.2.1-windows-x64.zip.sha256).Split()[0]
$actual = (Get-FileHash .\TheraSim-v0.2.1-windows-x64.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 verification failed." }
```

The v0.2.0 Windows ZIP contains an unintended migration backup. Use the
corrective v0.2.1 package only after its tagged Windows workflow has passed
and its release checksum has been verified.

Extract the ZIP to a folder you can write to, such as a folder under your
profile. No administrator access or installer is required. Start
`TheraSim\TheraSim.exe`. The application binds only to `127.0.0.1`, opens the
local interface in your default browser, and initializes its databases under
`%LOCALAPPDATA%\TheraSim\data`. Closing the console window or pressing
`Ctrl+C` requests a graceful server shutdown.

On first use, create a local reviewer account with a password of at least 12
characters. It is a single local account, not a multi-user authorization
system. Keep your Windows account and device protected. Live SQLite files are
not encrypted by TheraSim.

## Data, logs, and local models

- Database files: `%LOCALAPPDATA%\TheraSim\data\therasim.db` and
  `case_vault.db`
- Rotating application log: `%LOCALAPPDATA%\TheraSim\logs\therasim.log`
- Optional local settings: `%LOCALAPPDATA%\TheraSim\config.env`

The `config.env` file accepts only the settings listed in the example below.
Use UTF-8 `KEY=value` lines; do not put shell commands in this file. Process
environment variables override file values. Restart TheraSim after editing
settings.

```dotenv
THERASIM_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=your-installed-model
# LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
# LM_STUDIO_MODEL=your-installed-model
```

Install and run Ollama or LM Studio separately if you want model-backed
patient replies or evaluator reports. No model is included. The app can start
without a model, but model-dependent workflows will not work until a compatible
local provider and model are available. Model requests are sent to the
provider address you configure; local-first does not mean that every
installation or model workflow is air-gapped.

The default local web port is 8765. If another application already uses it,
set `THERASIM_PORT` to an available port between 1024 and 65535 before
launching. The service remains bound to loopback.

## Safe use and limitations

Use synthetic, fictional data only. Do not enter real client, patient, or
identifiable information. TheraSim is a research/educational prototype, not
psychotherapy, diagnosis, clinical advice, professional supervision,
certification, or a validated measure of competence. ACT is the only runnable
modality. Evaluation, analytics, simulated responses, and rubrics are
experimental; their clinical, semantic, and psychometric validity has not been
established. Human review is required.

Before moving or deleting the local data directory, stop the application and
make a backup. Backup/restore guidance is in
[`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md). Removing the application
folder does not remove user-local data or logs.

## Troubleshooting

- **The app cannot start or the port is occupied:** close the other app using
  the configured local port, or set a different `THERASIM_PORT`. TheraSim
  never terminates another process to free a port.
- **The browser did not open:** open the displayed `http://127.0.0.1:<port>/`
  address manually while the TheraSim console remains running.
- **Model provider is unavailable:** confirm the provider is running locally,
  the base URL and model name are correct, and restart TheraSim. An unavailable
  model does not prevent the application itself from starting.
- **Startup fails:** review the console message and the rotating log file
  above. Do not post passwords, access tokens, logs containing private
  information, or real client data in a public issue.
- **The data directory is not writable:** choose a Windows profile folder
  with normal user write access. Do not run the app as administrator as a
  workaround.

See [`BUILD_WINDOWS.md`](BUILD_WINDOWS.md) to build the package yourself.

---

## نصب و اجرای TheraSim در ویندوز

### دریافت و تأیید

فایل ZIP ویندوز و فایل `.sha256` نسخهٔ v0.2.1 را از
[GitHub Releases](https://github.com/mohammadmahdialmasi/TheraSim/releases)
دریافت کنید. ZIP نسخهٔ v0.2.0 یک فایل پشتیبان مهاجرتِ ناخواسته دارد؛ از بستهٔ
اصلاح‌شدهٔ v0.2.1 فقط پس از موفقیت گردش‌کار ویندوز و تأیید checksum انتشار
استفاده کنید. پیش از استخراج، در PowerShell هش را بررسی کنید:

```powershell
$expected = (Get-Content .\TheraSim-v0.2.1-windows-x64.zip.sha256).Split()[0]
$actual = (Get-FileHash .\TheraSim-v0.2.1-windows-x64.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 verification failed." }
```

ZIP را در پوشه‌ای قابل‌نوشتن، مانند پوشه‌ای در نمایهٔ کاربری خود، استخراج کنید.
نصب‌کننده یا دسترسی مدیر لازم نیست. فایل `TheraSim\TheraSim.exe` را اجرا کنید.
برنامه فقط به `127.0.0.1` متصل می‌شود، رابط محلی را در مرورگر پیش‌فرض باز می‌کند
و پایگاه‌داده‌ها را در `%LOCALAPPDATA%\TheraSim\data` نگه می‌دارد. بستن پنجرهٔ
کنسول یا فشردن `Ctrl+C` خاموش‌شدن کنترل‌شدهٔ سرور را درخواست می‌کند.

در نخستین اجرا، حساب محلی بازبین را با گذرواژه‌ای حداقل ۱۲ نویسه‌ای بسازید.
این حساب سامانهٔ چندکاربره نیست. فایل‌های SQLite زنده با TheraSim رمزنگاری
نمی‌شوند.

### داده، گزارش‌ها و مدل‌های محلی

- پایگاه‌داده‌ها: `%LOCALAPPDATA%\TheraSim\data\therasim.db` و
  `case_vault.db`
- گزارش برنامه: `%LOCALAPPDATA%\TheraSim\logs\therasim.log`
- تنظیمات محلی اختیاری: `%LOCALAPPDATA%\TheraSim\config.env`

برای تولید پاسخ مراجع یا گزارش ارزیاب باید Ollama یا LM Studio را جداگانه نصب
و اجرا کنید؛ هیچ مدل زبانی همراه بسته نیست. نشانی ارائه‌دهنده را پیش از ارسال
متن بررسی کنید؛ محلی‌محور بودن تضمین نمی‌کند که همهٔ نصب‌ها یا جریان‌های کاری
کاملاً بدون اینترنت باشند.

### استفادهٔ ایمن و محدودیت‌ها

فقط از داده‌های داستانی و ساختگی استفاده کنید. TheraSim نمونهٔ اولیه‌ای پژوهشی
و آموزشی است و درمان، تشخیص، توصیهٔ بالینی، نظارت حرفه‌ای، گواهی صلاحیت یا
سنجش معتبر مهارت ارائه نمی‌کند. ACT تنها رویکرد اجرایی است. ارزیابی، تحلیل،
پاسخ‌های شبیه‌سازی‌شده و روبریک‌ها آزمایشی‌اند و اعتبار بالینی، معنایی یا
روان‌سنجی آن‌ها اثبات نشده است. بازبینی انسانی لازم است.

پیش از جابه‌جایی یا حذف داده‌های محلی، برنامه را متوقف و نسخهٔ پشتیبان تهیه
کنید؛ راهنمای [پشتیبان‌گیری و بازیابی](docs/BACKUP_RESTORE.md) را ببینید.
حذف پوشهٔ برنامه داده‌ها و گزارش‌های محلی کاربر را حذف نمی‌کند.
