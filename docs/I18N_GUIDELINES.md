# Internationalization and translation guidelines

## Language policy

TheraSim supports English (`en`) and Persian (`fa`) UI modes. Both languages
must communicate the same behavior, warnings, scientific limitations, and
privacy boundaries. English and Persian must not imply different capabilities.
The application is a synthetic-data-only research prototype; translations
must not suggest clinical validation, treatment effectiveness, or professional
certification.

The central navigation and shared interface strings live in
`frontend/src/i18n.ts`. Feature-specific screens may keep colocated `en`/`fa`
copy dictionaries. Every user-visible string must belong to a language-aware
catalog; avoid embedding visible English or Persian copy directly in JSX.
Backend errors exposed to users should be mapped to localized, actionable
messages where practical. Do not localize API identifiers, database fields,
code symbols, model IDs, URLs, or stored enum values.

## Writing and terminology

- Use clear, concise, professional English and idiomatic Persian written for
  the intended audience; do not translate sentence structure literally.
- Follow [the bilingual terminology glossary](TRANSLATION_GLOSSARY.md).
- Keep ACT names and process concepts scientifically distinct. Do not invent a
  Persian clinical term when its meaning is ambiguous; retain the established
  source term and document it for expert review.
- Use «مراجع» for the fictional therapy client and say explicitly that cases
  are fictional. Use «طرح درمان» for treatment plan, «رونوشت» for transcript,
  and «معیارنامهٔ ارزیابی» for rubric in Persian UI copy.
- Preserve research-prototype disclaimers, human-review requirements, missing
  evidence semantics, and synthetic-data warnings in both languages.
- Avoid colloquial second-person imperatives in Persian UI. Prefer polite
  constructions, Persian punctuation, Persian half-spaces (نیم‌فاصله), and
  consistent Persian numerals where the surrounding interface already uses
  them. Preserve proper names such as Ollama, LM Studio, llama.cpp, and ACT.

## RTL and mixed-direction text

- Set `dir="rtl"` for Persian page roots and `dir="ltr"` for English roots.
- Use `dir="auto"` for user-entered or model-generated text whose language is
  not known. Use `<bdi dir="ltr">` or an equivalent isolated span for IDs,
  hashes, URLs, version strings, and API identifiers.
- Prefer CSS logical properties (`margin-inline`, `padding-inline`,
  `text-align: start`) so layouts mirror without changing semantic order.
- Keep numeric values and URLs legible; verify longer Persian labels in
  buttons, cards, navigation, validation messages, and narrow layouts.
- Use the bundled Vazirmatn font for Persian text. Do not insert direction
  control characters into API payloads or stored identifiers.

## Translation-catalog checks

Before merging UI copy changes:

1. Keep central English and Persian keys identical; the frontend test suite
   checks key parity, duplicate keys, and unused central entries.
2. Keep feature-local language objects structurally identical and check their
   TypeScript diagnostics.
3. Run `npm test`, `npm run lint`, and `npm run build` from `frontend`.
4. Review both language modes in the browser, including RTL direction,
   mixed-direction identifiers, text wrapping, and empty/error/loading states.
5. Update the glossary when a term is added or intentionally changed.

## Internationalization and ترجمه

رابط کاربری TheraSim از دو زبان انگلیسی (`en`) و فارسی (`fa`) پشتیبانی می‌کند.
هر دو زبان باید رفتار، هشدارها، محدودیت‌های علمی و مرزهای حریم خصوصی یکسانی را
بیان کنند و نباید قابلیت متفاوتی را القا کنند. این برنامه نمونه‌ای پژوهشی با
داده‌های ساختگی است؛ ترجمه‌ها نباید اعتبار بالینی، اثربخشی درمان یا گواهی
صلاحیت حرفه‌ای را القا کنند.

رشته‌های مشترک رابط و ناوبری در `frontend/src/i18n.ts` قرار دارند. صفحه‌های
ویژگی‌محور می‌توانند فرهنگ واژگان دوزبانهٔ محلی داشته باشند. متن قابل مشاهده
را مستقیماً در JSX ننویسید؛ آن را در واژگان متناسب با زبان قرار دهید. خطاهای
بک‌اندی که به کاربر نشان داده می‌شوند، در صورت امکان باید به پیام‌های روشن و
ترجمه‌شده نگاشت شوند. شناسه‌های API، فیلدهای پایگاه داده، نمادهای کد، شناسهٔ
مدل، نشانی‌ها و مقدارهای ذخیره‌شدهٔ enum را ترجمه نکنید.

### نگارش و اصطلاح‌شناسی

- انگلیسی را روشن، موجز و حرفه‌ای بنویسید. فارسی باید طبیعی و متناسب با
  مخاطب باشد؛ ساختار جملهٔ انگلیسی را کلمه‌به‌کلمه منتقل نکنید.
- از [واژه‌نامهٔ دوزبانه](TRANSLATION_GLOSSARY.md) پیروی کنید.
- نام ACT و فرایندهای آن را از نظر علمی متمایز نگه دارید. اگر معنای یک اصطلاح
  بالینی روشن نیست، برای آن معادل‌سازی قطعی نسازید؛ اصطلاح اصلی را حفظ و
  ابهام را برای بازبینی متخصص ثبت کنید.
- برای مراجع داستانی از واژهٔ «مراجع» استفاده کنید و داستانی‌بودن پرونده را
  روشن بیان کنید. در UI فارسی، برای *Treatment Plan* از «طرح درمان»، برای
  *Transcript* از «رونوشت» و برای *Rubric* از «معیارنامهٔ ارزیابی» استفاده کنید.
- هشدار استفاده از دادهٔ ساختگی، الزام بازبینی انسانی و مفهوم دادهٔ غایب را
  در هر دو زبان حفظ کنید. در متن رابط از خطاب محاوره‌ای پرهیز کنید؛ نیم‌فاصله،
  نشانه‌گذاری فارسی و شیوهٔ نمایش عددها را یکدست نگه دارید.
- نام‌های خاص مانند Ollama،‏ LM Studio،‏ llama.cpp و ACT را به همان شکل حفظ
  کنید.

### راست‌به‌چپ و متن‌های دوجهته

- برای ریشهٔ صفحهٔ فارسی از `dir="rtl"` و برای انگلیسی از `dir="ltr"` استفاده
  کنید.
- برای متن کاربر یا مدل که زبان آن معلوم نیست از `dir="auto"` استفاده کنید.
  شناسه‌ها، هش‌ها، نشانی‌ها و نسخه‌ها را با `<bdi dir="ltr">` یا سازوکاری
  معادل جدا کنید.
- برای چیدمان از ویژگی‌های منطقی CSS مانند `margin-inline` و
  `text-align: start` استفاده کنید تا صفحه بدون جابه‌جایی معنایی آینه‌ای شود.
- خوانایی نشانی‌ها و عددها و شکست متن فارسی را در دکمه‌ها، کارت‌ها،
  پیام‌های اعتبارسنجی، صفحه‌های باریک و حالت‌های خالی/خطا/بارگذاری بررسی کنید.
- برای متن فارسی از قلم Vazirmatn استفاده کنید. نویسه‌های کنترلی جهت را وارد
  درخواست‌های API یا شناسه‌های ذخیره‌شده نکنید.

### بررسی واژگان ترجمه

پیش از ادغام تغییرات رابط:

1. کلیدهای انگلیسی و فارسی در واژه‌نامهٔ مرکزی را یکسان نگه دارید؛ آزمون
   فرانت‌اند همسانی کلیدها، کلیدهای تکراری و ورودی‌های بلااستفاده را بررسی
   می‌کند.
2. ساختار واژگان انگلیسی و فارسی هر ویژگی را یکسان نگه دارید و تشخیص‌های
   TypeScript را بررسی کنید.
3. از پوشهٔ `frontend`، دستورهای `npm test`،‏ `npm run lint` و `npm run build`
   را اجرا کنید.
4. هر دو زبان را در مرورگر بررسی کنید؛ به راست‌چین‌بودن، شناسه‌های دوجهته،
   شکستن متن و حالت‌های خالی، خطا و بارگذاری توجه کنید.
5. با افزودن اصطلاح تازه یا تغییر عمدی یک معادل، واژه‌نامه را نیز به‌روز کنید.
