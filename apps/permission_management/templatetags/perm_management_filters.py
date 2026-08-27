"""
==========================================================================
 PERM MANAGEMENT FILTERS - Template Filter untuk Permission Management
==========================================================================
 Custom template filters untuk halaman permission management:

 Filters:
 - {{ dict|get_item:key }}           → Ambil value dari dictionary
 - {{ perm_list|get_module_perm:code }} → Cari permission berdasarkan module

 Dipakai di template permission_management untuk render matriks permission.

 Terhubung dengan:
 - templates/permission_management/ → Template yang menggunakan filter
==========================================================================
"""

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Mengambil nilai dari dictionary berdasarkan key yang diberikan"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_module_perm(permissions_list, module_code):
    """Mencari objek permission untuk modul tertentu dari list permission"""
    if not permissions_list:
        return None
    for perm in permissions_list:
        if perm.module == module_code:
            return perm
    return None
