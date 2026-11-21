# Install and run TheraSim on Windows

## Download and verify

The current Windows x64 package target is
`TheraSim-v0.3.0-Windows-x64-Portable.zip`, with a matching `.sha256` sidecar.
Download the ZIP and sidecar only from an official GitHub Release after its
Windows workflow has passed; if that asset is not listed there, do not treat a
local `dist/` copy as a release download. Before extracting a published asset,
verify its hash in PowerShell:

```powershell
$expected = (Get-Content .\TheraSim-v0.3.0-Windows-x64-Portable.zip.sha256).Split()[0]
$actual = (Get-FileHash .\TheraSim-v0.3.0-Windows-x64-Portable.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 verification failed." }
```

The published v0.2.0 Windows ZIP contains an unintended migration backup; do
not use it. A matching checksum confirms the downloaded bytes match the
sidecar, not that an unpublished local build is an official release.

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
environment variables override file values. Explicit provider environment
variables also take precedence over saved values from the **Settings** page at
startup. Restart TheraSim after editing settings.

```dotenv
THERASIM_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=your-installed-model
# LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
# LM_STUDIO_MODEL=your-installed-model
# LLAMA_CPP_BASE_URL=http://127.0.0.1:8080/v1
# CUSTOM_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
```

After signing in, use **Settings** to choose Ollama, LM Studio, a llama.cpp
server, or a custom OpenAI-compatible endpoint. Each provider has independent,
editable protocol, host, port, API base URL, model, and optional API-key
settings. Presets use `127.0.0.1`; their port numbers are editable suggestions.
Use **Test connection** to check the endpoint and list models when supported.
If model listing is not supported, type the model identifier. Settings persist
in `%LOCALAPPDATA%\TheraSim\provider-settings.json`; restart TheraSim to apply
changes to Patient Agent and Evaluator Agent workflows.

API keys are optional and should only be supplied when the selected endpoint
requires authentication. On Windows, entering a key through **Settings**
saves it protected with Windows DPAPI for the current Windows user in
`provider-settings.json` as a base64-encoded protected blob; the settings API
does not return key values. If TheraSim finds an older `api_key` plaintext
entry, Windows startup migrates it to the protected form and removes the
plaintext field. DPAPI protects against casual reading of the file, but it is
not equivalent to a separate application secret or hardware-backed security:
the current Windows account and a process with sufficient host access may be
able to read or recover the key. The protected blob is tied to the Windows
user and is not intended to remain portable across machines or accounts.
If a settings update omits `api_key`, the previous protected user-saved key is
preserved. Provider environment keys override saved keys at runtime; an
environment-only key is not newly added to the provider settings file by an
update. Non-Windows platforms do not support persistent provider-key storage;
provide provider credentials only through provider-specific environment
variables in those environments.
Model requests and connection tests go to the configured endpoint, which may
be remote. Non-loopback HTTP endpoints are rejected; use HTTPS remotely and
never send real client data.

Install and run the selected model server separately if you want model-backed
patient replies or evaluator reports. No model is included. The app can start
without a model, but model-dependent workflows will not work until a compatible
provider and model are available. Local-first does not mean every installation
or model workflow is air-gapped.

The default local web port is 8765. If another application already uses it,
set `THERASIM_PORT` to an available port between 1024 and 65535 before
launching. The service remains bound to loopback.

## Support diagnostics

After signing in, open **Settings** and find **Privacy-safe support export**.
The page displays the complete sanitized JSON report for the selected
interface language—the exact report fields used in the ZIP—along with a
summary of included and excluded categories. The ZIP's `diagnostics.json`
contains allow-listed metadata, including application version, operating-system
family/release, architecture, Python version, service and database-schema
status, active provider type, and sanitized connection-test status/time.
Provider URLs are omitted and no model identifier value is exported.

Review the preview, then select its confirmation checkbox and choose **Create
support ZIP**. The English filename is
`TheraSim-support-diagnostics.zip`; the Persian filename is
`TheraSim-support-diagnostics-fa.zip`. Each archive contains only
`diagnostics.json` and a language-matched `README.txt`. It excludes user
records, transcripts, case content, application logs, database files,
credentials, API keys, cookies, and personal information. TheraSim does not
upload or email the archive. Open and review it yourself, and attach it
manually to a support message only if you choose to share it.

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
- **The support preview has no current version or export fails:** confirm the
  app is still running, reload the page, and try again. Do not substitute raw
  logs or database files for the support ZIP. Only share a downloaded archive
  after reviewing its contents; the email action opens a draft but does not
  send or attach anything.

See [`BUILD_WINDOWS.md`](BUILD_WINDOWS.md) to build the package yourself.

---

## نصب و اجرای TheraSim در ویندوز

### دریافت و تأیید

هدف فعلی بستهٔ ویندوز x64، فایل
`TheraSim-v0.3.0-Windows-x64-Portable.zip` و فایل `.sha256` متناظر آن است. ZIP و
فایل checksum را فقط پس از موفقیت گردش‌کار ویندوز از
[صفحهٔ GitHub Releases](https://github.com/mohammadmahdialmasi/TheraSim/releases)
دریافت کنید؛ اگر فایل در آن صفحه فهرست نشده، نسخهٔ محلی پوشهٔ `dist/` را بستهٔ
منتشرشده تلقی نکنید. پیش از استخراج نسخهٔ منتشرشده، در PowerShell هش را
بررسی کنید:

```powershell
$expected = (Get-Content .\TheraSim-v0.3.0-Windows-x64-Portable.zip.sha256).Split()[0]
$actual = (Get-FileHash .\TheraSim-v0.3.0-Windows-x64-Portable.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 verification failed." }
```

بستهٔ ویندوز v0.2.0 منتشرشده شامل نسخهٔ پشتیبان مهاجرتِ ناخواسته است؛ از آن
استفاده نکنید. تطبیق checksum فقط یکسان‌بودن بایت‌های دریافت‌شده با فایل
checksum را تأیید می‌کند، نه رسمی‌بودن ساخت محلیِ منتشرنشده را.

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

فایل `config.env` فقط تنظیمات فهرست‌شده در نمونهٔ زیر را می‌پذیرد. از خطوط
UTF-8 با قالب `KEY=value` استفاده کنید و دستورهای shell را در آن قرار ندهید.
متغیرهای محیطی فرایند بر مقدارهای فایل مقدم‌اند و متغیرهای صریح ارائه‌دهنده
هنگام راه‌اندازی بر مقدارهای ذخیره‌شده در صفحهٔ **تنظیمات** اولویت دارند.
پس از ویرایش، TheraSim را دوباره راه‌اندازی کنید.

```dotenv
THERASIM_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=your-installed-model
# LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
# LM_STUDIO_MODEL=your-installed-model
# LLAMA_CPP_BASE_URL=http://127.0.0.1:8080/v1
# CUSTOM_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
```

پس از ورود، از بخش **تنظیمات**، Ollama،‏ LM Studio، سرور llama.cpp یا نشانی
سفارشی سازگار با API اوپن‌ای‌آی را انتخاب کنید. پروتکل، میزبان، درگاه، نشانی
پایهٔ API، نام مدل و کلید احتمالی هر ارائه‌دهنده جداگانه قابل تنظیم‌اند.
مقدارهای پیش‌فرض به `127.0.0.1` اشاره می‌کنند و درگاه‌های پیشنهادی قابل ویرایش
هستند. با **آزمایش اتصال** می‌توانید ارتباط را بررسی و در صورت پشتیبانی سرور،
فهرست مدل‌ها را دریافت کنید؛ در غیر این صورت نام مدل را دستی وارد کنید.
تنظیمات در `%LOCALAPPDATA%\TheraSim\provider-settings.json` ذخیره می‌شوند؛
برای اعمال آن‌ها در جریان‌های کاری عامل مراجع و ارزیاب، برنامه را دوباره
راه‌اندازی کنید.
متغیرهای محیطیِ صریح برای هر ارائه‌دهنده، هنگام راه‌اندازی بر مقدارهای ذخیره‌شده
در صفحهٔ تنظیمات اولویت دارند.

کلید API اختیاری است و فقط در صورت نیاز سرویس باید وارد شود. وارد کردن کلید از
طریق صفحهٔ **تنظیمات** در ویندوز آن را با Windows DPAPI برای حساب فعلی ویندوز
به‌صورت محافظت‌شده و در قالب base64 در فایل ذخیره می‌کند؛ API مقدار کلید را
بازنمی‌گرداند.
در صورت یافتن ورودی قدیمیِ متن سادهٔ `api_key`، راه‌اندازی در ویندوز آن را به
فرمت محافظت‌شده منتقل و فیلد متن ساده را حذف می‌کند. DPAPI در مقابل خواندن
غیرمستقیم فایل محافظت می‌کند، اما جایگزین راز جداگانهٔ برنامه یا امنیت سخت‌افزاری
نیست؛ حساب فعلی ویندوز یا فرایندی با دسترسی کافی میزبان ممکن است بتواند کلید را
بخواند یا بازیابی کند. محتوای محافظت‌شده به کاربر ویندوزی وابسته است و برای
انتقال بین رایانه‌ها یا حساب‌ها طراحی نشده است. در سیستم‌عامل‌های غیرویندوز،
ذخیره‌سازی دائمی کلید ارائه‌دهنده پشتیبانی نمی‌شود؛ کلیدها فقط از طریق متغیرهای
محیطی ارائه‌دهنده تنظیم شوند. اگر به‌روزرسانی تنظیمات `api_key` را حذف کند،
کلید محافظت‌شدهٔ قبلیِ ذخیره‌شده توسط کاربر در ویندوز حفظ می‌شود. کلیدهای محیطی
ارائه‌دهنده فقط هنگام اجرا بر کلیدهای ذخیره‌شده اولویت دارند؛ اگر کلید فقط از
محیط آمده باشد، به‌روزرسانی آن را به فایل تنظیمات اضافه نمی‌کند.
آزمایش اتصال و درخواست‌های مدل به نشانی تنظیم‌شده فرستاده می‌شوند که ممکن است
دوردست باشد. نشانی HTTP غیرمحلی پذیرفته نمی‌شود؛ برای سرویس دوردست HTTPS
تنظیم کنید و هیچ‌گاه دادهٔ واقعی مراجعان را ارسال نکنید.

برای تولید پاسخ مراجع یا گزارش ارزیاب، سرویس مدل انتخابی را جداگانه نصب و اجرا
کنید؛ هیچ مدل زبانی همراه بسته نیست. برنامه بدون مدل اجرا می‌شود، اما جریان‌های
کاری وابسته به مدل تا زمان پیکربندی ارائه‌دهنده و مدل کار نخواهند کرد.
محلی‌محور بودن تضمین نمی‌کند که همهٔ نصب‌ها یا جریان‌های کاری کاملاً بدون
اینترنت باشند.

درگاه پیش‌فرض وب محلی 8765 است. اگر برنامهٔ دیگری از آن استفاده می‌کند، پیش از
اجرا مقدار `THERASIM_PORT` را روی درگاه آزاد بین 1024 و 65535 تنظیم کنید.
سرویس همچنان فقط به loopback متصل می‌شود.

### اطلاعات عیب‌یابی برای پشتیبانی

پس از ورود، در **تنظیمات** بخش **خروجی پشتیبانی با رعایت حریم خصوصی** را باز
کنید. صفحه گزارش کامل JSON پالوده‌شده را به زبان رابط انتخاب‌شده نمایش می‌دهد؛
این همان گزارش و همان فیلدهایی است که در ZIP قرار می‌گیرند. همچنین خلاصهٔ
دسته‌های شامل و حذف‌شده را نشان می‌دهد. فایل `diagnostics.json` در ZIP
فرادادهٔ مجاز را دارد: از جمله نسخهٔ
برنامه، خانواده و نسخهٔ سیستم‌عامل، معماری، نسخهٔ Python، وضعیت سرویس و طرح
پایگاه‌داده، نوع ارائه‌دهندهٔ فعال و وضعیت/زمانِ پالوده‌شدهٔ آزمایش اتصال.
نشانی ارائه‌دهنده در خروجی نیست و مقدار شناسهٔ مدل نیز صادر نمی‌شود.

پیش‌نمایش را بررسی کنید، کادر تأیید را انتخاب کنید و **ایجاد بستهٔ پشتیبانی**
را بزنید. نام فایل انگلیسی
`TheraSim-support-diagnostics.zip` و نام فایل فارسی
`TheraSim-support-diagnostics-fa.zip` است. هر بسته فقط `diagnostics.json` و
`README.txt` هم‌زبان را دارد. رکوردهای کاربر، رونوشت، محتوای پرونده، گزارش
برنامه، فایل پایگاه‌داده، اطلاعات ورود، کلید API، کوکی و اطلاعات شخصی در آن
نیست. TheraSim بسته را بارگذاری یا ایمیل نمی‌کند. خودتان فایل را بازبینی کنید
و فقط در صورت تمایل، دستی به پیام پشتیبانی پیوست کنید.

### استفادهٔ ایمن و محدودیت‌ها

فقط از داده‌های داستانی و ساختگی استفاده کنید. TheraSim نمونهٔ اولیه‌ای پژوهشی
و آموزشی است و درمان، تشخیص، توصیهٔ بالینی، نظارت حرفه‌ای، گواهی صلاحیت یا
سنجش معتبر مهارت ارائه نمی‌کند. ACT تنها رویکرد اجرایی است. ارزیابی، تحلیل،
پاسخ‌های شبیه‌سازی‌شده و معیارنامه‌های ارزیابی آزمایشی‌اند و اعتبار بالینی، معنایی یا
روان‌سنجی آن‌ها اثبات نشده است. بازبینی انسانی لازم است.

پیش از جابه‌جایی یا حذف داده‌های محلی، برنامه را متوقف و نسخهٔ پشتیبان تهیه
کنید؛ راهنمای [پشتیبان‌گیری و بازیابی](docs/BACKUP_RESTORE.md) را ببینید.
حذف پوشهٔ برنامه داده‌ها و گزارش‌های محلی کاربر را حذف نمی‌کند.

### عیب‌یابی

- **برنامه اجرا نمی‌شود یا درگاه اشغال است:** برنامهٔ دیگرِ استفاده‌کننده از
  درگاه محلی را ببندید یا مقدار دیگری برای `THERASIM_PORT` تنظیم کنید.
  TheraSim برای آزادکردن درگاه، فرایند دیگری را متوقف نمی‌کند.
- **مرورگر باز نشد:** تا وقتی کنسول TheraSim باز است، نشانی نمایش‌داده‌شدهٔ
  `http://127.0.0.1:<port>/` را دستی در مرورگر وارد کنید.
- **ارائه‌دهندهٔ مدل در دسترس نیست:** مطمئن شوید سرویس محلی اجراست، نشانی پایه
  و نام مدل درست‌اند و TheraSim را دوباره راه‌اندازی کنید. نبود مدل مانع
  اجرای خود برنامه نمی‌شود.
- **برنامه هنگام شروع خطا می‌دهد:** پیام کنسول و فایل گزارش چرخشی بالا را
  بررسی کنید. گذرواژه، توکن دسترسی، گزارش دارای اطلاعات خصوصی یا دادهٔ واقعی
  مراجع را در گزارش عمومی ارسال نکنید.
- **پوشهٔ داده قابل نوشتن نیست:** پوشه‌ای در نمایهٔ ویندوز انتخاب کنید که
  دسترسی نوشتن معمولی دارد؛ برای رفع مشکل برنامه را با دسترسی مدیر اجرا نکنید.
- **نسخه در پیش‌نمایش پشتیبانی دیده نمی‌شود یا خروجی خطا می‌دهد:** مطمئن شوید
  برنامه هنوز اجراست، صفحه را دوباره بارگذاری و دوباره امتحان کنید. گزارش خام
  یا فایل پایگاه‌داده را جایگزین ZIP پشتیبانی نکنید. فقط پس از بازبینی، فایل
  دانلودشده را به اشتراک بگذارید؛ گزینهٔ ایمیل فقط پیش‌نویس باز می‌کند و چیزی
  نمی‌فرستد یا پیوست نمی‌کند.
