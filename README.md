# Menfess Bot (Telegram)

Bot menfess anonim untuk Telegram. Alur: **User → Bot → Admin → Publish/Delete → Channel**.
Dibangun dengan Python 3.12, `python-telegram-bot` v22+, dan FastAPI, berjalan sebagai **Webhook** di **Vercel Serverless** — tanpa database, tanpa polling, tanpa background thread.

## Daftar Isi
- [Struktur Project](#struktur-project)
- [1. Membuat Bot via BotFather](#1-membuat-bot-via-botfather)
- [2. Mendapatkan CHANNEL_ID](#2-mendapatkan-channel_id)
- [3. Mendapatkan Telegram User ID untuk ADMIN_IDS](#3-mendapatkan-telegram-user-id-untuk-admin_ids)
- [4. Menjadikan Bot sebagai Admin Channel](#4-menjadikan-bot-sebagai-admin-channel)
- [5. Contoh .env](#5-contoh-env)
- [6. Deploy ke Vercel](#6-deploy-ke-vercel)
- [7. Mengatur Webhook](#7-mengatur-webhook)
- [Troubleshooting](#troubleshooting)
- [Catatan Desain: Tanpa Database](#catatan-desain-tanpa-database)

---

## Struktur Project

```
project/
│
├── api/
│   └── webhook.py        # Entry point FastAPI + handler webhook Vercel
│
├── app/
│   ├── config.py          # Baca & validasi environment variable
│   ├── handlers.py        # Handler /start dan pesan menfess dari user
│   ├── callbacks.py        # Handler tombol Publish / Delete
│   ├── services.py        # Logic pengiriman & penyimpanan sementara
│   └── utils.py           # Helper logging & formatting
│
├── requirements.txt
├── vercel.json
├── README.md
├── .env.example
└── .gitignore
```

---

## 1. Membuat Bot via BotFather

1. Buka [@BotFather](https://t.me/BotFather) di Telegram.
2. Kirim `/newbot`, lalu ikuti instruksinya (nama bot & username bot).
3. BotFather akan memberikan **token**, contoh: `123456789:AAH...`. Simpan ini sebagai `BOT_TOKEN`.

## 2. Mendapatkan CHANNEL_ID

1. Buat channel Telegram (bisa privat atau publik).
2. Tambahkan bot [@userinfobot](https://t.me/userinfobot) atau [@RawDataBot](https://t.me/RawDataBot) sebagai member channel sementara, atau forward salah satu pesan dari channel ke bot tersebut.
3. `CHANNEL_ID` untuk channel biasanya berupa angka negatif panjang, contoh: `-1001234567890`.
4. Alternatif: gunakan endpoint `getUpdates` Telegram API setelah mem-forward pesan dari channel ke bot Anda, lalu cari field `chat.id` pada response JSON.

## 3. Mendapatkan Telegram User ID untuk ADMIN_IDS

1. Chat dengan [@userinfobot](https://t.me/userinfobot) — bot akan membalas dengan User ID Anda.
2. Lakukan ini untuk setiap orang yang ingin dijadikan admin.
3. Isi `ADMIN_IDS` dengan angka-angka tersebut dipisahkan koma, contoh: `111111111,222222222`.

## 4. Menjadikan Bot sebagai Admin Channel

1. Buka pengaturan channel → **Administrators** → **Add Admin**.
2. Cari username bot Anda dan tambahkan sebagai admin.
3. Pastikan izin **Post Messages** aktif — tanpa ini, bot tidak bisa publish menfess ke channel.

## 5. Contoh .env

```env
BOT_TOKEN=123456789:AAH...

ADMIN_IDS=111111111,222222222

CHANNEL_ID=-1001234567890

WEBHOOK_URL=https://nama-project-kamu.vercel.app/api/webhook

WEBHOOK_SECRET=string_rahasia_acak_anda
```

`WEBHOOK_SECRET` bebas Anda tentukan sendiri (string acak) — digunakan untuk memverifikasi bahwa request webhook benar-benar berasal dari Telegram (header `X-Telegram-Bot-Api-Secret-Token`).

## 6. Deploy ke Vercel

1. Push project ini ke repository GitHub/GitLab/Bitbucket Anda.
2. Buka [vercel.com](https://vercel.com) → **New Project** → import repository tersebut.
3. Saat konfigurasi, tambahkan seluruh variabel dari `.env.example` di bagian **Environment Variables** Vercel (BOT_TOKEN, ADMIN_IDS, CHANNEL_ID, WEBHOOK_URL, WEBHOOK_SECRET).
4. Klik **Deploy**. Setelah selesai, Anda akan mendapatkan URL seperti `https://nama-project-kamu.vercel.app`.
5. Update `WEBHOOK_URL` di Environment Variables agar sesuai dengan domain final (`https://nama-project-kamu.vercel.app/api/webhook`), lalu redeploy jika perlu.

## 7. Mengatur Webhook

Setelah deploy berhasil, daftarkan webhook ke Telegram dengan memanggil endpoint berikut (ganti `<BOT_TOKEN>`, `<WEBHOOK_URL>`, `<WEBHOOK_SECRET>`):

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
        "url": "<WEBHOOK_URL>",
        "secret_token": "<WEBHOOK_SECRET>"
      }'
```

Cek status webhook:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

Response `"pending_update_count": 0` dan `"last_error_message"` kosong menandakan webhook berjalan normal.

---

## Troubleshooting

| Masalah | Penyebab Umum | Solusi |
|---|---|---|
| Bot tidak merespon `/start` | Webhook belum di-set atau `WEBHOOK_URL` salah | Jalankan ulang `setWebhook`, cek `getWebhookInfo` |
| `401 Unauthorized` di log Vercel | `WEBHOOK_SECRET` di Telegram tidak sama dengan di Environment Variables | Samakan nilai lalu `setWebhook` ulang |
| Publish gagal / bot tidak bisa post ke channel | Bot belum jadi admin channel, atau tidak ada izin **Post Messages** | Tambahkan bot sebagai admin channel dengan izin post |
| `CHANNEL_ID salah` di log | Format ID channel salah (harus diawali `-100` untuk channel) | Ambil ulang ID lewat @RawDataBot |
| File terlalu besar | Bot API standar membatasi unggah ~50MB via bot | Gunakan file lebih kecil, atau self-hosted Bot API server jika perlu limit lebih besar |
| Tombol Publish/Delete bilang "sudah diproses" padahal belum ada admin yang menekan | State in-memory hilang akibat cold start Vercel (lihat bagian di bawah) | Minta user kirim ulang menfess, atau tambahkan storage eksternal (lihat bawah) |
| Error `Callback Error` di log | `callback_data` tidak dikenali/menfess sudah kedaluwarsa dari memori | Ini expected behavior saat entry sudah tidak ada di store |

---

## Catatan Desain: Tanpa Database

Sesuai requirement, bot ini **tidak menggunakan database** — status setiap menfess (`pending` / `published` / `deleted`) disimpan di **memori proses** (in-memory dict di `app/services.py`).

Ini bekerja baik selama Vercel Serverless Function tetap **warm** antar-request (umumnya beberapa menit setelah request terakhir). Namun karena sifat serverless, instance bisa saja di-*restart* (cold start) sehingga state sebelumnya hilang — menfess yang sedang pending saat itu tidak akan ditemukan lagi ketika admin menekan tombol.

Ini adalah trade-off yang disengaja demi memenuhi requirement "tanpa database". Untuk kebutuhan produksi dengan traffic tinggi atau butuh keandalan lebih tinggi, Anda bisa mengganti `MenfessStore` di `app/services.py` dengan storage eksternal ringan seperti **Vercel KV**, **Upstash Redis**, atau sejenisnya — cukup ganti implementasi `create` / `get` / `set_status` tanpa mengubah bagian lain dari kode.
