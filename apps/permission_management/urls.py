"""
==========================================================================
 PERMISSION MANAGEMENT URLs
==========================================================================
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'permission_management'

urlpatterns = [
    path('', RedirectView.as_view(url='/access/roles/'), name='index'),
    # Matrix Permission - Edit semua modul + sub-modul dalam satu halaman
    path('role-permissions/', views.RolePermissionMatrixView.as_view(), name='role_permission_matrix'),
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/ajax/create/', views.RoleCreateAjaxView.as_view(), name='role_create'),
    path('roles/ajax/<str:role>/data/', views.RoleDataAjaxView.as_view(), name='role_data'),
    path('roles/ajax/<str:role>/update/', views.RoleUpdateAjaxView.as_view(), name='role_update'),
    path('roles/delete/<str:role_code>/', views.RoleDeleteView.as_view(), name='role_delete'),
]
