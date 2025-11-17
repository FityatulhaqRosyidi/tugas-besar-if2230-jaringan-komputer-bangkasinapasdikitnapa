<h1 align="center">Tugas Besar IF2230 - Jaringan Komputer</h1>
<h3 align="center">ChatTCP</h3>

## Daftar Isi

- [Deskripsi](#deskripsi)
- [Kebutuhan Sistem](#kebutuhan-sistem)
- [Struktur](#struktur)
- [Cara Menjalankan](#cara-menjalankan)
- [Pengembang](#pengembang)

## Deskripsi

Program ini merupakan implementasi pemrograman socket dalam Python yang mencakup dua bagian utama:
(1) Pembuatan protokol TCP over UDP dengan fitur three-way handshake, flow control (sliding window), dan error detection (checksum)
(2) Aplikasi chat room sederhana berbasis client-server.

Server pada program ini bertugas mengelola koneksi client melalui three-way handshake, menyimpan dan menyebarkan pesan ke semua client yang terhubung (max 20 pesan), serta menyediakan fitur khusus seperti perintah !disconnect untuk memutus koneksi, !change untuk mengganti nama pengguna, dan !kill dengan password untuk mematikan server secara aman. Adapun client dapat terhubung ke server, mengirim/menerima pesan, mengirim heartbeat dengan timeout 30 detik, dan menggunakan berbagai perintah yang tersedia dengan protokol komunikasi yang dibangun di atas UDP untuk menjamin keandalan transfer data.

## Kebutuhan Sistem

* Python

## Struktur
```ssh
├── .github/
│   └── .keep
├── .vscode/
│   └── launch.json
├── src/
│   ├── classes/
│   │   ├─ tcp_base.py
│   │   ├─ tcp_client.py
│   │   ├─ tcp_segment.py
│   │   └─ tcp_server.py
│   ├── helper/
│   │   ├─ constants.py
│   │   └─ utils.py
│   ├── client.py
│   ├── client_ip.txt
│   ├── rand_ip.py
│   └── server.py
├── .gitignore
├── .python-version
├── LICENSE
├── README.md
├── pyproject.toml
└── uv.lock
```

## Cara Menjalankan

1. Clone repository ini:

```bash
git clone https://github.com/labsister22/tugas-besar-if2230-jaringan-komputer-bangkasinapasdikitnapa.git
```

2. Navigasi ke direktori repositori dan masuk ke folder src:

```bash
cd src
```

3. Jalankan command berikut untuk menjalankan server:

```bash
uv run python server.py
```

4. Jalankan command berikut untuk menjalankan client di host/terminal yang berbeda dengan server:

```bash
uv run python client.py
```

**NOTE:** Bisa dicoba dengan mengubah "python" dengan "py" atau "python3" tergantung pada konfigurasi pengguna

## Pengembang

| **NIM**  | **Nama Anggota**               |**Jobdesk**|
| -------- | ------------------------------ |-|
| 13523081 | Jethro Jens Norbert Simatupang | Pengerjaan 4.1.4 |
| 13523100 | Aryo Wisanggeni | Pengerjaan 4.1.1 - 4.1.3|
| 13523106 | Athian Nugraha Muarajuang | pengerjaan 4.1.4  |
| 13523116 | Fityatul Haq Rosyidi | Pengerjaan 4.2 |
