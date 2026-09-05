# Sinkronisasi Jadwal StreamXHD -> GitHub -> Blogger

Paket ini membuat alur:

StreamXHD `https://streamxhd.com/eventos.json`
-> GitHub Actions
-> `eventos.json` di repository GitHub
-> Blogger
-> link pertandingan -> player hosting.

## Cara memasang

1. Buka repository GitHub:
   `omezing75-byte/data-sport-nexa`
2. Upload folder `.github` beserta isinya.
3. Upload folder `scripts` beserta `sync-eventos.mjs`.
4. Pastikan file `eventos.json` tetap berada di folder utama repository.
   Workflow akan memperbaruinya otomatis.
5. Masuk ke tab **Actions** di GitHub.
6. Pilih workflow **Sinkronisasi eventos.json dari StreamXHD**.
7. Jalankan **Run workflow** sekali untuk tes.
8. Jika berhasil, workflow berikutnya akan berjalan otomatis kira-kira setiap 5 menit.

## Blogger

Kode Blogger yang ada di `blogger/KODE-BLOGGER.html` sudah menggunakan:

`https://raw.githubusercontent.com/omezing75-byte/data-sport-nexa/refs/heads/main/eventos.json`

Jadi **tidak perlu mengganti URL sumber di Blogger**.

Blogger tetap membaca GitHub. Yang berubah adalah siapa yang mengisi `eventos.json`:
sekarang GitHub Actions mengambil data terbaru dari StreamXHD.

## Keamanan sinkronisasi

Workflow memeriksa bahwa respons adalah JSON, memiliki `sports`, dan mempunyai event.
Jika sumber kosong, rusak, atau tidak sesuai format, file `eventos.json` lama tidak ditimpa.

## Catatan

Jadwal GitHub Actions bersifat terjadwal dan dapat mengalami sedikit keterlambatan karena antrean GitHub. `Run workflow` dapat digunakan untuk sinkronisasi manual.


## Sumber jadwal

Sumber utama sekarang adalah `https://futbollibretv.org.pe/diaries.json`.

Jika alamat sumber berubah, cukup edit:

`scripts/config-source.json`

dan ubah nilai `source_url`. Tidak perlu mengubah `KODE-BLOGGER.html`.

`eventos.json` **tidak disertakan sebagai file awal di ZIP**, sama seperti ZIP asli. File tersebut dibuat/diupdate otomatis oleh GitHub Actions setelah workflow sinkronisasi berhasil.
