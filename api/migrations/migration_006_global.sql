-- ============================================================
-- Flow Ops TMS — Migration 006: Global Operations Reference Data
-- Languages, Currencies, UOMs, Tax Jurisdictions, Date Formats, Time Zones
-- Run: PGPASSWORD=oms_dev_password psql -h localhost -p 5433 -U oms_user -d flow_ops_tms -f migration_006_global.sql
-- ============================================================

BEGIN;
SET search_path = tms;

-- ============================================================
-- CURRENCIES
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.currencies (
    currency_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    currency_code   text NOT NULL UNIQUE,   -- ISO 4217 e.g. USD
    currency_name   text NOT NULL,
    currency_symbol text,
    decimal_places  integer NOT NULL DEFAULT 2,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- LANGUAGES
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.languages (
    language_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    language_code   text NOT NULL UNIQUE,   -- ISO 639-1 e.g. en
    language_name   text NOT NULL,
    native_name     text,
    locale_code     text,                   -- e.g. en-US
    is_active       boolean NOT NULL DEFAULT true,
    is_default      boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- DATE FORMATS
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.date_formats (
    date_format_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    format_code     text NOT NULL UNIQUE,
    format_pattern  text NOT NULL,          -- e.g. MM/DD/YYYY
    display_example text,                   -- e.g. 06/25/2026
    region          text,
    is_active       boolean NOT NULL DEFAULT true,
    is_default      boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- TIME ZONES
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.time_zones (
    time_zone_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tz_code         text NOT NULL UNIQUE,   -- IANA e.g. America/New_York
    tz_name         text NOT NULL,
    utc_offset      text NOT NULL,          -- e.g. UTC-05:00
    utc_offset_minutes integer NOT NULL DEFAULT 0,
    region          text,
    is_active       boolean NOT NULL DEFAULT true,
    is_default      boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- TAX JURISDICTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.tax_jurisdictions (
    jurisdiction_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_code   text NOT NULL UNIQUE,
    jurisdiction_name   text NOT NULL,
    country_code        text NOT NULL,
    state_province      text,
    tax_type            text NOT NULL DEFAULT 'VAT',  -- VAT | GST | SALES | CUSTOMS | EXCISE
    standard_rate       numeric(7,4),                 -- e.g. 20.0000 for 20%
    reduced_rate        numeric(7,4),
    zero_rate           numeric(7,4) NOT NULL DEFAULT 0,
    currency_code       text DEFAULT 'USD',
    effective_from      date,
    effective_to        date,
    is_active           boolean NOT NULL DEFAULT true,
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- ADD MISSING COLUMNS TO unit_of_measures
-- ============================================================
ALTER TABLE tms.unit_of_measures
    ADD COLUMN IF NOT EXISTS base_uom_code   text,
    ADD COLUMN IF NOT EXISTS conversion_factor numeric(20,10),
    ADD COLUMN IF NOT EXISTS is_active       boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS uom_type        text;  -- WEIGHT | VOLUME | LENGTH | QTY | TIME

-- Indexes
CREATE INDEX IF NOT EXISTS idx_currencies_code    ON tms.currencies(currency_code);
CREATE INDEX IF NOT EXISTS idx_languages_code     ON tms.languages(language_code);
CREATE INDEX IF NOT EXISTS idx_time_zones_code    ON tms.time_zones(tz_code);
CREATE INDEX IF NOT EXISTS idx_tax_jurisdictions_country ON tms.tax_jurisdictions(country_code, is_active);

-- ============================================================
-- SEED: CURRENCIES (major ISO 4217)
-- ============================================================
INSERT INTO tms.currencies (currency_id, currency_code, currency_name, currency_symbol, decimal_places) VALUES
  (gen_random_uuid(), 'USD', 'US Dollar',            '$',   2),
  (gen_random_uuid(), 'EUR', 'Euro',                 '€',   2),
  (gen_random_uuid(), 'GBP', 'British Pound',        '£',   2),
  (gen_random_uuid(), 'CAD', 'Canadian Dollar',      'CA$', 2),
  (gen_random_uuid(), 'MXN', 'Mexican Peso',         '$',   2),
  (gen_random_uuid(), 'BRL', 'Brazilian Real',       'R$',  2),
  (gen_random_uuid(), 'AUD', 'Australian Dollar',    'A$',  2),
  (gen_random_uuid(), 'CNY', 'Chinese Yuan',         '¥',   2),
  (gen_random_uuid(), 'JPY', 'Japanese Yen',         '¥',   0),
  (gen_random_uuid(), 'INR', 'Indian Rupee',         '₹',   2),
  (gen_random_uuid(), 'SGD', 'Singapore Dollar',     'S$',  2),
  (gen_random_uuid(), 'HKD', 'Hong Kong Dollar',     'HK$', 2),
  (gen_random_uuid(), 'CHF', 'Swiss Franc',          'CHF', 2),
  (gen_random_uuid(), 'SEK', 'Swedish Krona',        'kr',  2),
  (gen_random_uuid(), 'NOK', 'Norwegian Krone',      'kr',  2),
  (gen_random_uuid(), 'DKK', 'Danish Krone',         'kr',  2),
  (gen_random_uuid(), 'AED', 'UAE Dirham',           'د.إ', 2),
  (gen_random_uuid(), 'SAR', 'Saudi Riyal',          'ر.س', 2),
  (gen_random_uuid(), 'KRW', 'South Korean Won',     '₩',   0),
  (gen_random_uuid(), 'ZAR', 'South African Rand',   'R',   2),
  (gen_random_uuid(), 'NZD', 'New Zealand Dollar',   'NZ$', 2),
  (gen_random_uuid(), 'THB', 'Thai Baht',            '฿',   2),
  (gen_random_uuid(), 'MYR', 'Malaysian Ringgit',    'RM',  2),
  (gen_random_uuid(), 'IDR', 'Indonesian Rupiah',    'Rp',  0),
  (gen_random_uuid(), 'PHP', 'Philippine Peso',      '₱',   2)
ON CONFLICT (currency_code) DO NOTHING;

-- ============================================================
-- SEED: LANGUAGES
-- ============================================================
INSERT INTO tms.languages (language_id, language_code, language_name, native_name, locale_code, is_default) VALUES
  (gen_random_uuid(), 'en',    'English',              'English',              'en-US', true),
  (gen_random_uuid(), 'en-GB', 'English (UK)',         'English (UK)',         'en-GB', false),
  (gen_random_uuid(), 'es',    'Spanish',              'Español',              'es-ES', false),
  (gen_random_uuid(), 'es-MX', 'Spanish (Mexico)',     'Español (México)',     'es-MX', false),
  (gen_random_uuid(), 'fr',    'French',               'Français',             'fr-FR', false),
  (gen_random_uuid(), 'de',    'German',               'Deutsch',              'de-DE', false),
  (gen_random_uuid(), 'pt',    'Portuguese',           'Português',            'pt-PT', false),
  (gen_random_uuid(), 'pt-BR', 'Portuguese (Brazil)',  'Português (Brasil)',   'pt-BR', false),
  (gen_random_uuid(), 'zh',    'Chinese (Simplified)', '中文(简体)',            'zh-CN', false),
  (gen_random_uuid(), 'zh-TW', 'Chinese (Traditional)','中文(繁體)',            'zh-TW', false),
  (gen_random_uuid(), 'ja',    'Japanese',             '日本語',               'ja-JP', false),
  (gen_random_uuid(), 'ko',    'Korean',               '한국어',               'ko-KR', false),
  (gen_random_uuid(), 'ar',    'Arabic',               'العربية',              'ar-SA', false),
  (gen_random_uuid(), 'hi',    'Hindi',                'हिन्दी',                 'hi-IN', false),
  (gen_random_uuid(), 'nl',    'Dutch',                'Nederlands',           'nl-NL', false),
  (gen_random_uuid(), 'it',    'Italian',              'Italiano',             'it-IT', false),
  (gen_random_uuid(), 'pl',    'Polish',               'Polski',               'pl-PL', false),
  (gen_random_uuid(), 'ru',    'Russian',              'Русский',              'ru-RU', false),
  (gen_random_uuid(), 'tr',    'Turkish',              'Türkçe',               'tr-TR', false),
  (gen_random_uuid(), 'sv',    'Swedish',              'Svenska',              'sv-SE', false)
ON CONFLICT (language_code) DO NOTHING;

-- ============================================================
-- SEED: DATE FORMATS
-- ============================================================
INSERT INTO tms.date_formats (format_code, format_pattern, display_example, region, is_default) VALUES
  ('MDY_SLASH',  'MM/DD/YYYY',   '06/25/2026', 'United States',        true),
  ('DMY_SLASH',  'DD/MM/YYYY',   '25/06/2026', 'Europe / Latin America',false),
  ('YMD_DASH',   'YYYY-MM-DD',   '2026-06-25', 'ISO 8601 / Asia',      false),
  ('DMY_DOT',    'DD.MM.YYYY',   '25.06.2026', 'Germany / Russia',     false),
  ('MDY_DASH',   'MM-DD-YYYY',   '06-25-2026', 'North America Alt',    false),
  ('DMY_DASH',   'DD-MM-YYYY',   '25-06-2026', 'Europe Alt',           false),
  ('YMD_SLASH',  'YYYY/MM/DD',   '2026/06/25', 'Japan / China',        false),
  ('MDY_LONG',   'MMM DD, YYYY', 'Jun 25, 2026','US Long Format',      false),
  ('DMY_LONG',   'DD MMM YYYY',  '25 Jun 2026','UK Long Format',       false),
  ('FULL_LONG',  'MMMM D, YYYY', 'June 25, 2026','Full Written',       false)
ON CONFLICT (format_code) DO NOTHING;

-- ============================================================
-- SEED: TIME ZONES (major IANA zones)
-- ============================================================
INSERT INTO tms.time_zones (tz_code, tz_name, utc_offset, utc_offset_minutes, region, is_default) VALUES
  ('America/New_York',      'Eastern Time',              'UTC-05:00', -300, 'North America', true),
  ('America/Chicago',       'Central Time',              'UTC-06:00', -360, 'North America', false),
  ('America/Denver',        'Mountain Time',             'UTC-07:00', -420, 'North America', false),
  ('America/Los_Angeles',   'Pacific Time',              'UTC-08:00', -480, 'North America', false),
  ('America/Anchorage',     'Alaska Time',               'UTC-09:00', -540, 'North America', false),
  ('Pacific/Honolulu',      'Hawaii Time',               'UTC-10:00', -600, 'North America', false),
  ('America/Toronto',       'Eastern Time (Canada)',     'UTC-05:00', -300, 'North America', false),
  ('America/Vancouver',     'Pacific Time (Canada)',     'UTC-08:00', -480, 'North America', false),
  ('America/Mexico_City',   'Central Time (Mexico)',     'UTC-06:00', -360, 'Latin America', false),
  ('America/Sao_Paulo',     'Brasilia Time',             'UTC-03:00', -180, 'Latin America', false),
  ('America/Buenos_Aires',  'Argentina Time',            'UTC-03:00', -180, 'Latin America', false),
  ('America/Bogota',        'Colombia Time',             'UTC-05:00', -300, 'Latin America', false),
  ('Europe/London',         'Greenwich Mean Time',       'UTC+00:00',    0, 'Europe',        false),
  ('Europe/Paris',          'Central European Time',     'UTC+01:00',   60, 'Europe',        false),
  ('Europe/Berlin',         'Central European Time (DE)','UTC+01:00',   60, 'Europe',        false),
  ('Europe/Amsterdam',      'Central European Time (NL)','UTC+01:00',   60, 'Europe',        false),
  ('Europe/Madrid',         'Central European Time (ES)','UTC+01:00',   60, 'Europe',        false),
  ('Europe/Rome',           'Central European Time (IT)','UTC+01:00',   60, 'Europe',        false),
  ('Europe/Moscow',         'Moscow Time',               'UTC+03:00',  180, 'Europe',        false),
  ('Africa/Johannesburg',   'South Africa Standard Time','UTC+02:00',  120, 'Africa',        false),
  ('Africa/Lagos',          'West Africa Time',          'UTC+01:00',   60, 'Africa',        false),
  ('Africa/Nairobi',        'East Africa Time',          'UTC+03:00',  180, 'Africa',        false),
  ('Asia/Dubai',            'Gulf Standard Time',        'UTC+04:00',  240, 'Middle East',   false),
  ('Asia/Riyadh',           'Arabia Standard Time',      'UTC+03:00',  180, 'Middle East',   false),
  ('Asia/Kolkata',          'India Standard Time',       'UTC+05:30',  330, 'Asia',          false),
  ('Asia/Dhaka',            'Bangladesh Standard Time',  'UTC+06:00',  360, 'Asia',          false),
  ('Asia/Bangkok',          'Indochina Time',            'UTC+07:00',  420, 'Asia',          false),
  ('Asia/Singapore',        'Singapore Time',            'UTC+08:00',  480, 'Asia',          false),
  ('Asia/Shanghai',         'China Standard Time',       'UTC+08:00',  480, 'Asia',          false),
  ('Asia/Hong_Kong',        'Hong Kong Time',            'UTC+08:00',  480, 'Asia',          false),
  ('Asia/Tokyo',            'Japan Standard Time',       'UTC+09:00',  540, 'Asia',          false),
  ('Asia/Seoul',            'Korea Standard Time',       'UTC+09:00',  540, 'Asia',          false),
  ('Australia/Sydney',      'Australian Eastern Time',   'UTC+10:00',  600, 'Pacific',       false),
  ('Australia/Melbourne',   'Australian Eastern Time (VIC)','UTC+10:00',600,'Pacific',       false),
  ('Australia/Perth',       'Australian Western Time',   'UTC+08:00',  480, 'Pacific',       false),
  ('Pacific/Auckland',      'New Zealand Standard Time', 'UTC+12:00',  720, 'Pacific',       false),
  ('UTC',                   'Coordinated Universal Time','UTC+00:00',    0, 'Universal',     false)
ON CONFLICT (tz_code) DO NOTHING;

-- ============================================================
-- SEED: TAX JURISDICTIONS
-- ============================================================
INSERT INTO tms.tax_jurisdictions
    (jurisdiction_code, jurisdiction_name, country_code, state_province, tax_type, standard_rate, reduced_rate, currency_code, effective_from) VALUES
  -- United States (no federal VAT; state sales tax)
  ('US-CA', 'California Sales Tax',      'US', 'CA', 'SALES',   7.2500, NULL,   'USD', '2020-01-01'),
  ('US-TX', 'Texas Sales Tax',           'US', 'TX', 'SALES',   6.2500, NULL,   'USD', '2020-01-01'),
  ('US-NY', 'New York Sales Tax',        'US', 'NY', 'SALES',   4.0000, NULL,   'USD', '2020-01-01'),
  ('US-FL', 'Florida Sales Tax',         'US', 'FL', 'SALES',   6.0000, NULL,   'USD', '2020-01-01'),
  ('US-IL', 'Illinois Sales Tax',        'US', 'IL', 'SALES',   6.2500, NULL,   'USD', '2020-01-01'),
  -- European VAT
  ('EU-DE', 'Germany VAT',               'DE', NULL, 'VAT',    19.0000, 7.0000, 'EUR', '2007-01-01'),
  ('EU-FR', 'France VAT',                'FR', NULL, 'VAT',    20.0000, 5.5000, 'EUR', '2014-01-01'),
  ('EU-GB', 'United Kingdom VAT',        'GB', NULL, 'VAT',    20.0000, 5.0000, 'GBP', '2011-01-04'),
  ('EU-ES', 'Spain VAT (IVA)',           'ES', NULL, 'VAT',    21.0000, 10.000, 'EUR', '2012-09-01'),
  ('EU-IT', 'Italy VAT (IVA)',           'IT', NULL, 'VAT',    22.0000, 10.000, 'EUR', '2013-10-01'),
  ('EU-NL', 'Netherlands VAT (BTW)',     'NL', NULL, 'VAT',    21.0000, 9.0000, 'EUR', '2012-10-01'),
  ('EU-SE', 'Sweden VAT (MOMS)',         'SE', NULL, 'VAT',    25.0000, 12.000, 'SEK', '1995-01-01'),
  -- Americas
  ('MX',    'Mexico IVA',                'MX', NULL, 'VAT',    16.0000, 0.0000, 'MXN', '2010-01-01'),
  ('BR',    'Brazil ICMS (avg)',         'BR', NULL, 'VAT',    17.0000, NULL,   'BRL', '2020-01-01'),
  ('CA-HST','Canada HST',               'CA', NULL, 'GST',    13.0000, 0.0000, 'CAD', '2010-07-01'),
  -- Asia Pacific
  ('AU-GST','Australia GST',            'AU', NULL, 'GST',    10.0000, 0.0000, 'AUD', '2000-07-01'),
  ('NZ-GST','New Zealand GST',          'NZ', NULL, 'GST',    15.0000, 0.0000, 'NZD', '2010-10-01'),
  ('SG-GST','Singapore GST',            'SG', NULL, 'GST',     9.0000, 0.0000, 'SGD', '2024-01-01'),
  ('IN-GST','India GST (standard)',     'IN', NULL, 'GST',    18.0000, 5.0000, 'INR', '2017-07-01'),
  ('JP-CT', 'Japan Consumption Tax',    'JP', NULL, 'VAT',    10.0000, 8.0000, 'JPY', '2019-10-01'),
  -- Middle East
  ('AE-VAT','UAE VAT',                  'AE', NULL, 'VAT',     5.0000, 0.0000, 'AED', '2018-01-01'),
  ('SA-VAT','Saudi Arabia VAT',         'SA', NULL, 'VAT',    15.0000, 0.0000, 'SAR', '2020-07-01'),
  -- Zero rate / exempt placeholder
  ('EXEMPT', 'Tax Exempt',              'US', NULL, 'SALES',   0.0000, 0.0000, 'USD', '2020-01-01')
ON CONFLICT (jurisdiction_code) DO NOTHING;

-- ============================================================
-- SEED: UNIT OF MEASURES (update existing + add missing)
-- ============================================================
UPDATE tms.unit_of_measures SET uom_type = 'QTY'    WHERE uom_code IN ('EA','CS','PAL');
UPDATE tms.unit_of_measures SET uom_type = 'WEIGHT'  WHERE uom_code IN ('KG','LB','MT');
UPDATE tms.unit_of_measures SET uom_type = 'VOLUME'  WHERE uom_code IN ('M3','CF');
UPDATE tms.unit_of_measures SET uom_type = 'LENGTH'  WHERE uom_code IN ('M','FT');

-- Add additional UOMs
INSERT INTO tms.unit_of_measures (uom_id, uom_code, uom_name, uom_type, base_uom_code, conversion_factor) VALUES
  (gen_random_uuid(), 'G',    'Gram',             'WEIGHT', 'KG',  0.001),
  (gen_random_uuid(), 'OZ',   'Ounce',            'WEIGHT', 'KG',  0.0283495),
  (gen_random_uuid(), 'TON',  'Short Ton (US)',   'WEIGHT', 'KG',  907.185),
  (gen_random_uuid(), 'L',    'Litre',            'VOLUME', 'M3',  0.001),
  (gen_random_uuid(), 'GAL',  'US Gallon',        'VOLUME', 'M3',  0.003785),
  (gen_random_uuid(), 'CM',   'Centimetre',       'LENGTH', 'M',   0.01),
  (gen_random_uuid(), 'IN',   'Inch',             'LENGTH', 'M',   0.0254),
  (gen_random_uuid(), 'YD',   'Yard',             'LENGTH', 'M',   0.9144),
  (gen_random_uuid(), 'MI',   'Mile',             'LENGTH', 'M',   1609.344),
  (gen_random_uuid(), 'KM',   'Kilometre',        'LENGTH', 'M',   1000),
  (gen_random_uuid(), 'HR',   'Hour',             'TIME',   NULL,  NULL),
  (gen_random_uuid(), 'MIN',  'Minute',           'TIME',   NULL,  NULL),
  (gen_random_uuid(), 'DAY',  'Day',              'TIME',   NULL,  NULL),
  (gen_random_uuid(), 'BX',   'Box',              'QTY',    NULL,  NULL),
  (gen_random_uuid(), 'RL',   'Roll',             'QTY',    NULL,  NULL),
  (gen_random_uuid(), 'DR',   'Drum',             'QTY',    NULL,  NULL),
  (gen_random_uuid(), 'BAG',  'Bag',              'QTY',    NULL,  NULL),
  (gen_random_uuid(), 'CTN',  'Carton',           'QTY',    NULL,  NULL),
  (gen_random_uuid(), 'PKG',  'Package',          'QTY',    NULL,  NULL),
  (gen_random_uuid(), 'SET',  'Set',              'QTY',    NULL,  NULL)
ON CONFLICT (uom_code) DO NOTHING;

COMMIT;
