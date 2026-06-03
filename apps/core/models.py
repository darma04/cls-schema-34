"""
==========================================================================
 CORE MODELS - Sistem RBAC (Role-Based Access Control)
==========================================================================
 File ini berisi model RolePermission — jantung sistem keamanan proyek.

 Apa itu RBAC?
 - Role-Based Access Control = Kontrol akses berdasarkan peran
 - Setiap user punya 1 role (dari Profile.role)
 - Setiap role punya daftar permission per modul/sub-modul
 - Permission: can_view, can_create, can_edit, can_delete

 Contoh penggunaan:
 - Role 'KASIR' → hanya bisa akses modul 'pos' dan 'penjualan'
 - Role 'ADMIN' → bisa akses semua modul kecuali pengaturan sistem
 - Role 'SUPERUSER' → bypass semua pengecekan (akses penuh)

 Koneksi penting:
 - auth/models.py → Profile.role menyimpan role user
 - apps/core/permissions.py → Fungsi has_permission() membaca model ini
 - apps/core/mixins.py → Mixin menggunakan has_permission() di views
 - apps/core/context_processors.py → Menyuntikkan permission ke template
 - apps/permission_management/ → UI untuk mengelola permissions
 - templates/layout/partials/menu/ → Sidebar difilter berdasarkan permission
==========================================================================
"""

from django.db import models  # Django ORM untuk definisi model database


class RolePermission(models.Model):
    """
    Model untuk menyimpan konfigurasi permission setiap role.

    Setiap record = 1 aturan permission:
    - Role X di Module Y (Sub-module Z) bisa View/Create/Edit/Delete

    Contoh data:
    | role   | module  | sub_module   | can_view | can_create | can_edit | can_delete |
    |--------|---------|--------------|----------|------------|----------|------------|
    | KASIR  | pos     | None         | True     | True       | False    | False      |
    | ADMIN  | produk  | kategori     | True     | True       | True     | True       |
    | USER   | produk  | daftar_produk| True     | False      | False    | False      |

    SUPERUSER tidak perlu record di tabel ini — selalu dapat akses penuh.
    """

    # ==================== DAFTAR ROLE STATIS ====================
    ROLE_CHOICES = [
        ('SUPERUSER', 'Superuser - Full Access'),
        ('ADMIN', 'Admin - Limited Access'),
        ('USER', 'User - Read Only'),
    ]

    # ==================== DAFTAR MODUL ====================
    # Semua modul yang tersedia di Central License Server
    # Setiap modul sesuai dengan 1 menu utama di sidebar
    MODULE_CHOICES = [
        ('dashboard', 'Dashboard'),                    # Halaman utama
        ('licenses', 'Manajemen Lisensi'),              # Produk, Klien, Kunci Lisensi
        ('tenant_management', 'Tenant Management'),      # Kelola tenant SaaS
        ('pembelian', 'Pembelian Lisensi'),              # Pembelian lisensi
        ('laporan', 'Laporan'),                          # Laporan: lisensi, klien, pendapatan, keuangan
        ('ai', 'AI Manajemen'),                          # Chat AI, Dashboard AI
        ('user_management', 'Manajemen User'),           # Kelola user
        ('access_control', 'Access Control'),            # Kelola role & permission
        ('activity_log', 'Log Aktivitas'),               # Riwayat aktivitas user
        ('automation', 'Telegram'),                      # Notifikasi Telegram
        ('pengaturan', 'Pengaturan'),                    # Profil, Perusahaan, Template, Data
    ]

    # ==================== DAFTAR SUB-MODUL ====================
    # Sub-modul per modul — setiap sub-modul = 1 submenu di sidebar
    SUB_MODULE_CHOICES = {
        'dashboard': [
            ('refresh_cache', 'Tombol Refresh Cache'),
        ],
        'licenses': [
            ('produk', 'Data Produk'),
            ('klien', 'Data Klien'),
            ('kunci_lisensi', 'Kunci Lisensi'),
        ],
        'laporan': [
            ('laporan_lisensi', 'Laporan Lisensi'),
            ('laporan_klien', 'Laporan Klien'),
            ('laporan_pendapatan', 'Laporan Pendapatan'),
            ('laporan_keuangan', 'Laporan Keuangan'),
        ],
        'ai': [
            ('ai_chat', 'Chat AI'),
            ('ai_dashboard', 'Dashboard AI'),
        ],
        'automation': [
            ('pengaturan_telegram', 'Pengaturan Bot'),
            ('template_pesan', 'Template Pesan'),
            ('log_notifikasi', 'Log Notifikasi'),
        ],
        'pengaturan': [
            ('profil', 'Profil'),
            ('perusahaan', 'Perusahaan'),
            ('template_cetak', 'Template Cetak'),
            ('manajemen_data', 'Manajemen Data'),
        ],
    }

    # ==================== MAPPING SUB-MODULE KE SLUG MENU ====================
    # PENTING: Slug di sini HARUS cocok dengan bagian SETELAH dash pertama di vertical_menu.json
    # Contoh: menu slug "licenses-product" → extract_submodule → "product"
    #         Maka mapping harus: 'produk': 'product'
    SUB_MODULE_TO_SLUG = {
        # === Dashboard ===
        'refresh_cache': 'refresh-cache',
        # === Manajemen Lisensi ===
        # Menu: licenses-product, licenses-client, licenses-keys
        'produk': 'product',
        'klien': 'client',
        'kunci_lisensi': 'keys',
        # === Laporan ===
        # Menu: laporan-lisensi, laporan-klien, laporan-pendapatan, laporan-keuangan
        'laporan_lisensi': 'lisensi',
        'laporan_klien': 'klien',
        'laporan_pendapatan': 'pendapatan',
        'laporan_keuangan': 'keuangan',
        # === AI Manajemen ===
        # Menu: ai-chat, ai-dashboard
        'ai_chat': 'chat',
        'ai_dashboard': 'dashboard',
        # === Telegram / Automation ===
        # Menu: automation-settings, automation-templates, automation-logs
        'pengaturan_telegram': 'settings',
        'template_pesan': 'templates',
        'log_notifikasi': 'logs',
        # === Pengaturan ===
        # Menu: pengaturan-profil, pengaturan-perusahaan, pengaturan-template, pengaturan-data
        'profil': 'profil',
        'perusahaan': 'perusahaan',
        'template_cetak': 'template',
        'manajemen_data': 'data',
    }

    # ==================== REVERSE MAPPING: SLUG → DB CODE ====================
    # Kebalikan dari SUB_MODULE_TO_SLUG
    # Digunakan untuk konversi dari slug sidebar ke kode database
    # Dibuild otomatis dari mapping di atas menggunakan loop
    SLUG_TO_SUB_MODULE = {}
    for _module_code, _subs in SUB_MODULE_CHOICES.items():
        SLUG_TO_SUB_MODULE[_module_code] = {}
        for _sub_code, _sub_name in _subs:
            _slug = SUB_MODULE_TO_SLUG.get(_sub_code, _sub_code)
            SLUG_TO_SUB_MODULE[_module_code][_slug] = _sub_code

    # ==================== FIELD DATABASE ====================

    # Role user (contoh: 'ADMIN', 'KASIR', 'STAFF_GUDANG')
    # choices dihapus agar bisa menerima role kustom dari database
    role = models.CharField(
        max_length=50,
        verbose_name="Role"
    )

    # Modul yang diakses (contoh: 'produk', 'inventory', 'pos')
    module = models.CharField(
        max_length=50,
        choices=MODULE_CHOICES,
        verbose_name="Module"
    )

    # Sub-modul (opsional) — untuk permission lebih detail
    # Contoh: modul 'produk' → sub-modul 'kategori', 'satuan', 'daftar_produk'
    # Jika None → permission berlaku untuk SEMUA sub-modul di modul tersebut
    sub_module = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Sub Module",
        help_text="Specific page/feature within module (e.g., 'kategori', 'satuan', 'daftar_produk')"
    )

    # ==================== FIELD PERMISSION ====================
    # 4 jenis permission (CRUD):

    can_view = models.BooleanField(
        default=True,
        verbose_name="Can View",
        help_text="Dapat melihat/membaca data"
    )
    can_create = models.BooleanField(
        default=False,
        verbose_name="Can Create",
        help_text="Dapat menambah data baru"
    )
    can_edit = models.BooleanField(
        default=False,
        verbose_name="Can Edit",
        help_text="Dapat mengubah data"
    )
    can_delete = models.BooleanField(
        default=False,
        verbose_name="Can Delete",
        help_text="Dapat menghapus data"
    )

    # Catatan/deskripsi tambahan tentang permission ini
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Deskripsi",
        help_text="Catatan tambahan tentang permission ini"
    )

    # ==================== FIELD TRACKING ====================
    created_at = models.DateTimeField(auto_now_add=True)  # Tanggal dibuat (otomatis)
    updated_at = models.DateTimeField(auto_now=True)       # Tanggal terakhir diubah (otomatis)

    # ==================== META CLASS ====================
    class Meta:
        # unique_together: Kombinasi role + module + sub_module harus unik
        # Artinya: 1 role hanya bisa punya 1 record per module per sub_module
        """Konfigurasi metadata model untuk Django."""
        unique_together = ('role', 'module', 'sub_module')
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"
        ordering = ['role', 'module', 'sub_module']  # Urutan default saat query

    # ==================== METHOD ====================

    def get_role_display(self):
        """
        Mendapatkan nama role yang mudah dibaca manusia.

        Kenapa manual? Karena field 'role' tidak pakai choices=
        (agar bisa menerima role kustom), maka Django tidak otomatis
        menyediakan get_role_display().

        Contoh:
        - 'ADMIN' → 'Admin - Limited Access'
        - 'STAFF_GUDANG' → 'Staff Gudang' (format otomatis)
        """
        role_dict = dict(self.ROLE_CHOICES)
        return role_dict.get(self.role, self.role.replace('_', ' ').title())

    def __str__(self):
        """
        Representasi string RolePermission.
        Format: "Admin - Produk > Kategori" atau "Kasir - POS / Kasir"
        """
        base = f"{self.get_role_display()} - {self.get_module_display()}"
        if self.sub_module:
            return f"{base} > {self.sub_module.replace('_', ' ').title()}"
        return base

    def get_permissions_summary(self):
        """
        Menghasilkan ringkasan permission yang mudah dibaca.

        Return: String seperti "View, Create, Edit" atau "No Access"
        Digunakan di admin panel dan halaman permission management.
        """
        perms = []
        if self.can_view:
            perms.append('View')
        if self.can_create:
            perms.append('Create')
        if self.can_edit:
            perms.append('Edit')
        if self.can_delete:
            perms.append('Delete')
        return ', '.join(perms) if perms else 'No Access'

    @classmethod
    def get_all_roles(cls):
        """
        Mendapatkan semua role yang AKTIF di sistem.

        Cara kerja:
        1. Query database: ambil semua role unik yang punya RolePermission records
        2. Untuk role statis (ADMIN, USER, KASIR): hanya tampilkan jika punya records di DB
        3. SUPERUSER selalu ditampilkan (bypass semua permission checks)
        4. Role kustom di-format otomatis: 'STAFF_GUDANG' → 'Staff Gudang'

        PENTING: Jika sebuah role (termasuk statis) sudah dihapus semua
        RolePermission-nya, role tersebut TIDAK akan muncul lagi di daftar.
        Ini memungkinkan admin untuk benar-benar menghapus role statis.

        Return: List of tuples [(kode, nama), ...]
        """
        # Mapping nama untuk role statis (referensi nama saja)
        static_role_names = dict(cls.ROLE_CHOICES)

        # Ambil role unik yang BENAR-BENAR ada di database
        from django.db.models import Count
        db_roles = cls.objects.values('role').annotate(count=Count('role')).order_by('role')

        # Kumpulkan role yang ada di DB
        active_roles = {}
        for item in db_roles:
            role_code = item['role']
            if role_code in static_role_names:
                # Role statis yang punya records di DB → tampilkan dengan nama statis
                active_roles[role_code] = static_role_names[role_code]
            else:
                # Role kustom: format otomatis nama dari kode
                active_roles[role_code] = role_code.replace('_', ' ').title()

        # SUPERUSER selalu ditampilkan (tidak perlu RolePermission records)
        if 'SUPERUSER' not in active_roles:
            active_roles['SUPERUSER'] = static_role_names.get('SUPERUSER', 'Superuser - Full Access')

        # Konversi ke list of tuples dan sort
        result = [(code, name) for code, name in active_roles.items()]
        return sorted(result, key=lambda x: x[1])
