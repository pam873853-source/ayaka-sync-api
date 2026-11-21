# Ayaka Sync API

Platform manajemen REST API Key full-stack: buat, kelola, batasi, dan pantau API key dari satu dashboard. Backend FastAPI + PostgreSQL (Neon), frontend HTML/CSS/JavaScript murni, siap deploy ke Vercel.

> Status pengujian: seluruh backend diuji dengan `pytest` terhadap PostgreSQL lokal, dan alur UI (registrasi → buat key → panggil API → analytics → activity export → settings → logout) diuji di browser headless pada server lokal. Deployment ke Vercel + Neon belum diverifikasi oleh pembuat repo ini — ikuti bagian [Deploy ke Vercel](#12-deploy-ke-vercel) dan cek `/status` setelah deploy.

---

## Daftar isi

1. [Tentang project](#1-tentang-project)
2. [Fitur utama](#2-fitur-utama)
3. [Struktur folder](#3-struktur-folder)
4. [Kebutuhan sistem](#4-kebutuhan-sistem)
5. [Instalasi project](#5-instalasi-project)
6. [Setup Python environment](#6-setup-python-environment)
7. [Setup database Neon](#7-setup-database-neon)
8. [Konfigurasi environment variable](#8-konfigurasi-environment-variable)
9. [Menjalankan development server](#9-menjalankan-development-server)
10. [Migrasi database](#10-migrasi-database)
11. [Menjalankan test](#11-menjalankan-test)
12. [Deploy ke Vercel](#12-deploy-ke-vercel)
13. [Menghubungkan custom domain](#13-menghubungkan-custom-domain)
14. [Cara membuat API key](#14-cara-membuat-api-key)
15. [Cara menggunakan API key](#15-cara-menggunakan-api-key)
16. [Endpoint reference](#16-endpoint-reference)
17. [Panduan keamanan](#17-panduan-keamanan)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. Tentang project

Ayaka Sync API adalah platform untuk developer yang perlu menerbitkan API key bagi aplikasinya, mengatur izin dan rate limit per key, serta melihat traffic nyata yang dilayani. Semua statistik dihitung dari tabel `api_usage_logs` yang diisi middleware pada setiap request ber-API-key — tidak ada data palsu. Jika belum ada traffic, UI menampilkan empty state.

Arsitektur:

```
Browser ──► Vercel CDN ──► public/*.html, public/assets/*      (halaman statis)
        └─► Vercel Function (app.py → FastAPI) ──► /api/v1/*    (REST API)
                                   └──► Neon PostgreSQL (pooled, SSL)
```

## 2. Fitur utama

- **Autentikasi**: register/login (email atau username), password Argon2id, JWT access token 30 menit di cookie HttpOnly + refresh token yang dirotasi, "remember me" 30 hari, proteksi CSRF (header `X-CSRF-Token` + cek Origin), lockout brute-force (10 percobaan/akun, 30/IP per 15 menit), logout mencabut sesi di database, "sign out all sessions".
- **API key**: prefix `ayk_live_` (production) / `ayk_test_` (development), 256-bit entropy dari `secrets`, disimpan hanya sebagai HMAC-SHA256 (dengan `API_KEY_PEPPER`), full key ditampilkan sekali. Rename, deskripsi, permissions, allowed endpoints, rate limit per key, expiration, enable/disable, regenerate, revoke, delete, search/filter/sort/pagination.
- **Permissions** di backend: `read`, `write`, `delete`, `analytics`, `profile`, `admin` (tidak default; memberi `admin` butuh password).
- **Rate limiting** per key (default 60/menit) disimpan di PostgreSQL sehingga konsisten di semua instance serverless; header `X-RateLimit-Limit/Remaining/Reset` dan `Retry-After` + HTTP 429.
- **Usage tracking**: request ID, endpoint, method, status, response time, key, IP, user agent. Tidak pernah mencatat Authorization header, full key, password, atau body.
- **Dashboard**: stat cards, quick actions, grafik real-time (polling 15–30 detik, berhenti saat tab disembunyikan), tabel Recent API Activity.
- **Analytics**: total/today/week/month, success & error rate, avg/p95 response time, peak traffic; 5 grafik; range 24h/7d/30d/90d/custom; filter per key.
- **Activity logs** append-only (UPDATE diblokir trigger database, aplikasi tidak menyediakan operasi hapus): search, filter, rentang tanggal, pagination, detail, export CSV.
- **Settings**: General (username, email, timezone, format tanggal), Appearance (tema Dark/Light/System dan switch animasi scroll, disimpan di browser), Security (ganti password, sesi aktif), API Preferences (default environment/rate limit/expiration), Notifications, Danger Zone (hapus akun). Semua tersimpan di database dan diterapkan.
- **Dokumentasi** di `/docs` (cURL/Python/JavaScript, Copy Code, Try Endpoint) + OpenAPI interaktif di `/api/docs`.
- **Status page** `/status` dari health check nyata, termasuk peringatan jika environment variable wajib belum di-set.
- **Mode gelap & mode terang**: tombol matahari/bulan di navbar, halaman login/register, dan topbar dashboard; pilihan Dark / Light / System di **Settings → Appearance**. Pilihan disimpan di browser (`localStorage` key `ayaka.theme`, hanya preferensi UI — bukan data sensitif), diterapkan sebelum halaman dirender (tanpa kedipan), sinkron antar tab, dan grafik Chart.js ikut berganti warna. Semua warna diatur lewat CSS variable di `public/assets/css/global.css` (`:root` untuk gelap, `:root[data-theme="light"]` untuk terang).
- **Animasi scroll**: section, kartu, dan konten muncul halus setiap kali masuk layar — dari bawah saat scroll ke bawah, dari atas saat scroll ke atas — dan diputar ulang setiap kali elemen keluar lalu masuk lagi. Memakai `IntersectionObserver` (`public/assets/js/reveal.js`), hanya `opacity`/`translate` sehingga ringan, dan otomatis dimatikan jika pengguna mengaktifkan *reduce motion* di sistem operasi. Bisa dimatikan/dinyalakan lewat switch **Settings → Appearance → Scroll animations** (berlaku langsung di semua halaman dan tab, disimpan di browser dengan key `ayaka.motion`).

## 3. Struktur folder

```
ayaka-sync-api/
├── app.py                    # Entrypoint Vercel: mengekspor `app` FastAPI
├── backend/
│   ├── config.py             # Settings dari environment variable
│   ├── database.py           # Engine SQLAlchemy (NullPool di serverless)
│   ├── migrate.py            # Runner migrasi SQL (python -m backend.migrate)
│   ├── models.py  schemas.py  security.py  responses.py
│   ├── dependencies.py       # Auth session/API key, permission, rate limit
│   ├── middleware.py         # Request ID, security headers, usage tracking, error handler
│   ├── main.py               # Factory FastAPI + router
│   ├── routes/               # auth, api_keys, dashboard, analytics, activity, profile, settings, health, public_api
│   └── services/             # key_service, rate_limiter, usage_service, analytics_service, audit_service, settings_service
├── migrations/0001_initial_schema.sql
├── public/                   # Frontend statis (disajikan CDN Vercel)
│   ├── index.html login.html register.html docs.html status.html privacy.html terms.html 404.html
│   ├── dashboard.html keys.html analytics.html activity.html settings.html profile.html
│   └── assets/{css,js,icons}
├── tests/                    # pytest (butuh PostgreSQL)
├── pyproject.toml  requirements.txt  requirements-dev.txt  .python-version
├── vercel.json  .env.example  .gitignore
└── README.md
```

## 4. Kebutuhan sistem

- Python **3.12+** (diuji juga di 3.14)
- PostgreSQL 14+ — production: [Neon](https://neon.tech); lokal: PostgreSQL biasa atau branch Neon
- Node.js **tidak** diperlukan (frontend tanpa build step)
- Akun Vercel + Vercel CLI (opsional, untuk deploy dari terminal)

## 5. Instalasi project

```bash
git clone <url-repo-anda> ayaka-sync-api
cd ayaka-sync-api
cp .env.example .env      # lalu isi nilainya (lihat bagian 8)
```

## 6. Setup Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

`requirements.txt` hanya berisi dependency runtime (yang diinstal Vercel). `requirements-dev.txt` menambahkan `uvicorn`, `pytest`, dan `httpx`.

## 7. Setup database Neon

1. Buat project di [console.neon.tech](https://console.neon.tech).
2. Buka **Connect** → pilih database → aktifkan **Connection pooling**.
3. Salin connection string. Host-nya harus mengandung `-pooler`, contoh:
   ```
   postgresql://neondb_owner:xxxx@ep-cool-name-123456-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Pastikan `sslmode=require` tetap ada. Prefix `postgresql://` otomatis dipakai dengan driver psycopg 3.
5. (Disarankan) Buat branch Neon terpisah untuk development/preview.

Mengapa pooled URL? Vercel Functions membuka koneksi baru per invocation; PgBouncer di endpoint `-pooler` mencegah limit koneksi habis. Backend memakai `NullPool` saat berjalan di Vercel sehingga tidak menahan koneksi.

## 8. Konfigurasi environment variable

| Variable | Wajib | Contoh / default | Keterangan |
|---|---|---|---|
| `APP_NAME` | – | `Ayaka Sync API` | Nama aplikasi |
| `APP_ENV` | ✔ | `production` | `development` atau `production` (production: cookie Secure, HSTS) |
| `APP_BASE_URL` | – | `https://api.ayaka.dev` | URL publik tanpa trailing slash. **Di Vercel boleh dikosongkan**: base URL otomatis mengikuti domain yang diakses (URL deployment, alias production, atau custom domain). Isi hanya jika ingin mengunci satu domain. Nilai `localhost` diabaikan saat berjalan di Vercel. |
| `DATABASE_URL` | ✔ | `postgresql://…-pooler…/neondb?sslmode=require` | Connection string Neon pooled |
| `JWT_SECRET` | ✔ | 64+ karakter acak | Penanda tangan token sesi |
| `JWT_EXPIRES_MINUTES` | – | `30` | Umur access token |
| `API_KEY_PEPPER` | ✔ | 64+ karakter acak, beda dari JWT_SECRET | Kunci HMAC untuk hash API key. **Jangan diganti** setelah ada key — semua key lama jadi tidak valid |
| `CORS_ORIGINS` | – | `https://ayaka-sync-api.vercel.app` | Origin browser yang diizinkan (dipisah koma) |
| `RATE_LIMIT_DEFAULT` | – | `60` | Request/menit default per key |
| `LOG_LEVEL` | – | `INFO` | Level logging |

Opsional lanjutan: `REFRESH_EXPIRES_DAYS` (1), `REFRESH_REMEMBER_DAYS` (30), `LOGIN_MAX_ATTEMPTS`, `LOGIN_WINDOW_SECONDS`, `SERVE_STATIC` (lokal: true).

Membuat secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Jika variable wajib kosong, aplikasi tetap bisa diakses: `/status` dan banner di dashboard menunjukkan variable mana yang belum di-set, dan endpoint yang membutuhkan database mengembalikan `503 DATABASE_NOT_CONFIGURED`.

**Jangan pernah commit `.env`.** File ini sudah ada di `.gitignore`.

## 9. Menjalankan development server

```bash
source .venv/bin/activate
python -m backend.migrate               # sekali, atau setiap ada migrasi baru
uvicorn app:app --reload --port 8000
```

Buka <http://localhost:8000>. Di mode lokal, FastAPI juga menyajikan folder `public/` (di Vercel, CDN yang melakukannya). Set `APP_BASE_URL=http://localhost:8000` agar contoh URL di dokumentasi benar dan cookie tidak diberi flag Secure di HTTP lokal.

## 10. Migrasi database

```bash
python -m backend.migrate            # terapkan migrasi yang tertunda
python -m backend.migrate --status   # lihat migrasi applied/pending
```

- Migrasi berupa file SQL di `migrations/NNNN_nama.sql`, diterapkan berurutan dalam transaksi, dicatat beserta checksum di `schema_migrations`, dan dikunci dengan advisory lock.
- Pernyataan destruktif (`DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, `DELETE FROM`) ditolak kecuali `--allow-destructive`, dan flag itu tidak pernah diizinkan saat `APP_ENV=production`.
- Untuk Neon production: jalankan dari komputer Anda dengan `DATABASE_URL` production:
  ```bash
  DATABASE_URL="postgresql://…-pooler…/neondb?sslmode=require" python -m backend.migrate
  ```
  Migrasi **tidak** dijalankan otomatis saat cold start agar function tetap cepat dan aman.

## 11. Menjalankan test

Test membutuhkan PostgreSQL (fitur seperti `percentile_cont`, trigger append-only, dan rate limit atomik tidak bisa diuji dengan SQLite).

```bash
# contoh dengan PostgreSQL lokal
createdb ayaka_test
export TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/ayaka_test
pytest -q
```

Default `TEST_DATABASE_URL` adalah `postgresql://ayaka:ayaka@localhost:5432/ayaka_test`. Setiap test membersihkan tabelnya sendiri. Cakupan: registrasi/login/lockout/refresh/CSRF, ownership, siklus hidup API key (create/rename/disable/regenerate/revoke/delete/expiry), permission & allowed endpoints, rate limit + header, usage logging, analytics, activity log append-only + CSV, settings, health, dan penyajian halaman statis.

## 12. Deploy ke Vercel

Project ini memakai dukungan **FastAPI zero-config** Vercel saat ini ([dokumentasi](https://vercel.com/docs/frameworks/backend/fastapi)): Vercel mendeteksi `app.py` di root yang mengekspor `app`, dan file di `public/` disajikan langsung oleh CDN. Tidak memakai pola lama `api/index.py` + `builds`/`routes`.

1. Push repo ke GitHub/GitLab/Bitbucket.
2. Di Vercel: **Add New → Project** → import repo. Framework preset akan terdeteksi sebagai FastAPI; biarkan build command kosong.
3. **Settings → Environment Variables**: isi semua variable wajib dari bagian 8 (untuk Production dan, jika perlu, Preview dengan branch Neon terpisah). `APP_ENV=production`. `APP_BASE_URL` **jangan** diisi `http://localhost:8000` — kosongkan (auto-detect) atau isi domain asli Anda. Pastikan opsi *Automatically expose System Environment Variables* aktif (default).
4. Jalankan migrasi ke database Neon (bagian 10).
5. Deploy. Atau lewat CLI:
   ```bash
   npm i -g vercel
   vercel link
   vercel env add DATABASE_URL production   # ulangi untuk variable lain
   vercel --prod
   ```
6. **Verifikasi** (jangan anggap sukses hanya karena build hijau):
   ```bash
   curl https://<domain>/api/v1/health            # configuration.missing harus []
   curl https://<domain>/api/v1/health/database   # status "ok"
   ```
   Lalu buka `/status`, register akun, buat key, dan panggil `GET /api/v1/example`.

Catatan konfigurasi (`vercel.json`): `cleanUrls` (`/login` → `login.html`), security header + CSP untuk halaman statis, `excludeFiles` agar test dan `public/` tidak ikut ke bundle function, dan `maxDuration` 30 detik. Versi Python diambil dari `.python-version` / `requires-python` (3.12).

## 13. Menghubungkan custom domain

1. Vercel → Project → **Settings → Domains** → tambahkan domain, mis. `api.ayaka.dev`.
2. Tambahkan record DNS yang diminta Vercel (`A 76.76.21.21` untuk apex atau `CNAME cname.vercel-dns.com` untuk subdomain). SSL diterbitkan otomatis.
3. Jika `APP_BASE_URL` kosong, base URL otomatis berubah ke domain baru. Jika Anda mengisinya, perbarui ke `https://api.ayaka.dev` (dan `CORS_ORIGINS` bila memanggil API dari origin lain), lalu **redeploy**.
4. Cek `https://api.ayaka.dev/status`.

## 14. Cara membuat API key

1. Register / sign in, buka **API Keys** → **Create API key**.
2. Isi nama, pilih environment (Development → `ayk_test_`, Production → `ayk_live_`), centang permission seminimal mungkin, atur rate limit, expiration, dan (opsional) allowed endpoints seperti `/api/v1/records/*`.
3. Salin key yang ditampilkan — **hanya muncul sekali**. Simpan di secrets manager / environment variable.
4. Kehilangan key? Gunakan **Regenerate** (key lama langsung tidak berlaku) atau buat key baru.

## 15. Cara menggunakan API key

```bash
export AYAKA_API_KEY="ayk_test_..."
curl https://<domain>/api/v1/example -H "Authorization: Bearer $AYAKA_API_KEY"
```

```python
import os, requests
r = requests.get("https://<domain>/api/v1/example",
                 headers={"Authorization": f"Bearer {os.environ['AYAKA_API_KEY']}"}, timeout=10)
print(r.status_code, r.headers.get("X-RateLimit-Remaining"), r.json())
```

```javascript
const res = await fetch("https://<domain>/api/v1/example", {
  headers: { Authorization: `Bearer ${process.env.AYAKA_API_KEY}` },
});
console.log(res.status, await res.json());
```

Header `X-API-Key: <key>` juga diterima. Key tidak pernah diterima lewat query string.

Format respons:

```json
{ "success": true, "message": "Request successful", "data": {}, "meta": { "timestamp": "…" } }
{ "success": false, "message": "…", "error": { "code": "PERMISSION_DENIED", "details": [] }, "meta": { "timestamp": "…", "request_id": "req_…" } }
```

## 16. Endpoint reference

Base URL: `https://<domain>/api/v1`. Referensi lengkap & interaktif: `/api/docs` (OpenAPI JSON: `/api/openapi.json`).

**Developer API (API key)**

| Method | Path | Permission | Keterangan |
|---|---|---|---|
| GET | `/example` | read | Verifikasi key |
| GET / POST | `/records` | read / write | List / buat record JSON |
| GET / PATCH / DELETE | `/records/{id}` | read / write / delete | Ambil / ubah / hapus record |
| GET | `/analytics/overview` `/requests` `/endpoints` `/keys` `/response-times` `/realtime` | analytics (atau sesi) | Statistik penggunaan |
| GET | `/profile` | profile (atau sesi) | Profil akun |
| GET | `/keys`, `/keys/{id}` | admin (atau sesi) | Daftar / detail key (tanpa secret) |
| POST | `/keys/{id}/revoke` | admin (atau sesi) | Revoke key |
| GET | `/health`, `/health/database`, `/meta` | publik | Health & konfigurasi |

**Dashboard API (cookie sesi + `X-CSRF-Token` untuk method yang mengubah data)**

| Method | Path | Keterangan |
|---|---|---|
| POST | `/auth/register` `/auth/login` `/auth/logout` `/auth/logout-all` `/auth/refresh` | Siklus sesi |
| GET | `/auth/me` `/auth/sessions` `/auth/availability` | Sesi & cek ketersediaan |
| POST | `/auth/sessions/{id}/revoke` | Cabut sesi tertentu |
| POST | `/keys` | Buat key (secret dikembalikan sekali) |
| PATCH / DELETE | `/keys/{id}` | Ubah / hapus key |
| POST | `/keys/{id}/regenerate` | Terbitkan secret baru |
| GET | `/dashboard/overview` `/dashboard/recent-activity` `/dashboard/notifications` | Data dashboard |
| GET | `/activity` `/activity/{id}` `/activity/export` | Activity log & CSV |
| GET / PATCH | `/settings`, `/profile` | Preferensi & profil |
| POST | `/profile/change-password` `/profile/delete-account` | Keamanan akun |

**Kode error**: `AUTHENTICATION_REQUIRED`, `INVALID_CREDENTIALS`, `INVALID_API_KEY`, `API_KEY_EXPIRED`, `API_KEY_REVOKED`, `API_KEY_DISABLED`, `TOKEN_EXPIRED`, `SESSION_EXPIRED`, `CSRF_FAILED`, `PERMISSION_DENIED`, `RESOURCE_NOT_FOUND`, `VALIDATION_ERROR`, `EMAIL_TAKEN`, `USERNAME_TAKEN`, `RATE_LIMIT_EXCEEDED`, `DATABASE_UNAVAILABLE`, `DATABASE_NOT_CONFIGURED`, `INTERNAL_SERVER_ERROR`.

## 17. Panduan keamanan

- Simpan `JWT_SECRET` dan `API_KEY_PEPPER` hanya di environment Vercel; gunakan nilai berbeda per environment. Mengganti `JWT_SECRET` mengeluarkan semua sesi; mengganti `API_KEY_PEPPER` membatalkan semua API key.
- Token sesi hanya ada di cookie `HttpOnly`, `Secure` (production), `SameSite`; tidak ada token di `localStorage`. Cookie `ayaka_signed_in=1` hanyalah penanda UI tanpa nilai kredensial.
- Request yang mengubah data dari dashboard wajib membawa `X-CSRF-Token`; header `Origin` (jika ada) harus sama dengan host aplikasi atau terdaftar di `CORS_ORIGINS`.
- API key disimpan sebagai HMAC-SHA256; perbandingan constant-time; key yang dicabut/kedaluwarsa/dinonaktifkan ditolak dengan kode error spesifik.
- Terapkan least privilege: beri key hanya permission yang dibutuhkan, batasi dengan allowed endpoints, set expiration, dan pisahkan key development/production.
- Jangan menaruh key production di kode frontend/mobile atau repository. Jika bocor: **Revoke** atau **Regenerate** segera, lalu periksa Activity Logs & analytics key tersebut.
- Semua query memakai SQLAlchemy (parameterized), semua output UI di-escape, CSP tanpa inline script.
- Activity log tidak bisa di-UPDATE (trigger database) dan tidak ada endpoint untuk menghapusnya; entri hanya ikut terhapus saat pemilik menghapus akunnya.

## 18. Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| Base URL di Docs/Status masih `localhost` | Deployment lama (sebelum perbaikan auto-detect) atau `APP_BASE_URL` berisi domain lain. Kosongkan `APP_BASE_URL` atau isi domain Vercel/custom domain Anda, lalu **redeploy**. Cek `GET /api/v1/meta` → `base_url`. |
| `/status` menunjukkan "Configuration incomplete" | Variable wajib belum di-set di Vercel. Tambahkan lalu **redeploy** (env baru tidak berlaku untuk deployment lama). |
| `503 DATABASE_UNAVAILABLE` | `DATABASE_URL` salah, tanpa `sslmode=require`, atau compute Neon sedang bangun dari suspend (coba ulang beberapa detik). Cek `GET /api/v1/health/database`. |
| `relation "users" does not exist` | Migrasi belum dijalankan ke database tersebut: `python -m backend.migrate`. |
| Login berhasil tapi langsung kembali ke halaman login | Situs dibuka via `http://` padahal `APP_ENV=production` atau `APP_BASE_URL` berawalan `https://` (cookie Secure tidak dikirim browser lewat HTTP). |
| `403 CSRF_FAILED` | Token CSRF hilang (muat ulang halaman) atau request datang dari origin lain — tambahkan origin tersebut ke `CORS_ORIGINS`. |
| `401 INVALID_API_KEY` untuk key yang benar | `API_KEY_PEPPER` berubah sejak key dibuat, atau key dikirim dengan spasi/baris baru. Regenerate key. |
| `429 RATE_LIMIT_EXCEEDED` | Tunggu sesuai `Retry-After` atau naikkan rate limit key di dashboard. |
| Grafik kosong | Belum ada request ber-API-key pada rentang waktu itu — panggil `GET /api/v1/example` lalu tunggu refresh otomatis. |
| `pytest` gagal koneksi | Set `TEST_DATABASE_URL` ke PostgreSQL yang berjalan dan database-nya sudah dibuat. |
| Function timeout di Vercel | Pastikan memakai pooled URL Neon dan region function dekat dengan region Neon (Project → Settings → Functions → Region). |

---

© Ayaka Sync API
