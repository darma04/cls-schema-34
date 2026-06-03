"""
==========================================================================
 PERMISSION MANAGEMENT VIEWS — CRUD Permission & Roles
==========================================================================
"""
from django.views.generic import ListView, View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.db.models import Count

from web_project import TemplateLayout
from apps.core.models import RolePermission
from auth.models import Profile

from apps.core.mixins import (
    ReadPermissionMixin, CreatePermissionMixin, UpdatePermissionMixin, DeletePermissionMixin
)
from apps.core.cache_utils import invalidate_role_permissions_cache

import json


@method_decorator(login_required, name='dispatch')
class RoleListView(ReadPermissionMixin, ListView):
    """Halaman utama Access Control — Daftar Role dengan Permission Matrix."""
    permission_module = 'access_control'
    model = User
    template_name = 'permission_management/role_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return User.objects.select_related('profile').all()

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Access Control'

        role_choices = RolePermission.get_all_roles()
        all_permissions = RolePermission.objects.all()
        all_users_with_role = User.objects.select_related('profile').all()

        role_data = []
        for role_code, role_name in role_choices:
            users_with_role = [u for u in all_users_with_role if hasattr(u, 'profile') and u.profile.role == role_code]
            permissions = [p for p in all_permissions if p.role == role_code]
            total_permissions = sum(1 for p in permissions if p.can_view)

            role_data.append({
                'code': role_code,
                'name': role_name,
                'user_count': len(users_with_role),
                'users': users_with_role[:4],
                'total_permissions': total_permissions,
            })

        context['roles'] = role_data
        context['role_choices'] = role_choices
        context['modules'] = RolePermission.MODULE_CHOICES

        # Module structure for JavaScript modal
        module_structure = {}
        for module_code, module_name in RolePermission.MODULE_CHOICES:
            module_structure[module_code] = {
                'name': module_name,
                'sub_modules': [
                    {'code': sub_code, 'name': sub_name}
                    for sub_code, sub_name in RolePermission.SUB_MODULE_CHOICES.get(module_code, [])
                ]
            }
        context['module_structure'] = json.dumps(module_structure)

        return context


@method_decorator(login_required, name='dispatch')
class RoleDataAjaxView(ReadPermissionMixin, View):
    """AJAX: Ambil data permission suatu role."""
    permission_module = 'access_control'
    def get(self, request, role):
        try:
            permissions = RolePermission.objects.filter(role=role).values(
                'module', 'sub_module', 'can_view', 'can_create', 'can_edit', 'can_delete'
            )
            role_name = dict(RolePermission.get_all_roles()).get(role, role.replace('_', ' ').title())
            return JsonResponse({
                'success': True,
                'role_code': role,
                'role_display': role_name,
                'permissions': list(permissions)
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@method_decorator(login_required, name='dispatch')
class RoleCreateAjaxView(CreatePermissionMixin, View):
    """AJAX: Buat role baru dengan permissions."""
    permission_module = 'access_control'
    def post(self, request):
        from django.db import transaction
        try:
            role_name = request.POST.get('role_name', '').strip().replace(' ', '_').upper()
            if not role_name:
                return JsonResponse({'success': False, 'message': 'Nama role wajib diisi!'}, status=400)

            existing_roles = [code for code, name in RolePermission.get_all_roles()]
            if role_name in existing_roles:
                return JsonResponse({'success': False, 'message': f'Role {role_name} sudah ada!'}, status=400)

            with transaction.atomic():
                perm_keys = [k for k in request.POST.keys() if k.startswith('perms[')]
                permissions_to_create = {}

                for key in perm_keys:
                    parts = key.replace('perms[', '').replace(']', '').split('[')
                    if len(parts) == 2:
                        module, action = parts
                        perm_key = (module, '__MODULE__')
                        if perm_key not in permissions_to_create:
                            permissions_to_create[perm_key] = {'module': module, 'sub_module': None, 'can_view': False, 'can_create': False, 'can_edit': False, 'can_delete': False}
                        if action == 'view': permissions_to_create[perm_key]['can_view'] = True
                        elif action == 'create': permissions_to_create[perm_key]['can_create'] = True
                        elif action == 'edit': permissions_to_create[perm_key]['can_edit'] = True
                        elif action == 'delete': permissions_to_create[perm_key]['can_delete'] = True
                    elif len(parts) == 4 and parts[1] == 'subs':
                        module, _, sub_module, action = parts
                        perm_key = (module, sub_module)
                        if perm_key not in permissions_to_create:
                            permissions_to_create[perm_key] = {'module': module, 'sub_module': sub_module, 'can_view': False, 'can_create': False, 'can_edit': False, 'can_delete': False}
                        if action == 'view': permissions_to_create[perm_key]['can_view'] = True
                        elif action == 'create': permissions_to_create[perm_key]['can_create'] = True
                        elif action == 'edit': permissions_to_create[perm_key]['can_edit'] = True
                        elif action == 'delete': permissions_to_create[perm_key]['can_delete'] = True

                new_permissions = [RolePermission(role=role_name, **d) for d in permissions_to_create.values()]
                if new_permissions:
                    RolePermission.objects.bulk_create(new_permissions)

            invalidate_role_permissions_cache(role_name)
            return JsonResponse({'success': True, 'message': f'Role {role_name} berhasil ditambahkan dengan {len(new_permissions)} permissions!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@method_decorator(login_required, name='dispatch')
class RoleUpdateAjaxView(UpdatePermissionMixin, View):
    """AJAX: Update permission role."""
    permission_module = 'access_control'
    def post(self, request, role):
        from django.db import transaction
        try:
            if role == 'SUPERUSER':
                return JsonResponse({'success': False, 'message': 'Role SUPERUSER tidak dapat diedit.'}, status=400)

            new_role_name = request.POST.get('role_name', '').strip()
            if new_role_name:
                new_role_name = new_role_name.replace(' ', '_').upper()

            old_role_name = role
            role_renamed = new_role_name and new_role_name != old_role_name

            with transaction.atomic():
                if role_renamed:
                    existing_roles = [code for code, name in RolePermission.get_all_roles()]
                    if new_role_name in existing_roles:
                        return JsonResponse({'success': False, 'message': f'Role {new_role_name} sudah ada!'}, status=400)
                    Profile.objects.filter(role=old_role_name).update(role=new_role_name)
                    RolePermission.objects.filter(role=old_role_name).update(role=new_role_name)
                    target_role = new_role_name
                else:
                    target_role = old_role_name

                perm_keys = [k for k in request.POST.keys() if k.startswith('perms[')]
                permissions_to_create = {}

                for key in perm_keys:
                    parts = key.replace('perms[', '').replace(']', '').split('[')
                    if len(parts) == 2:
                        module, action = parts
                        perm_key = (module, '__MODULE__')
                        if perm_key not in permissions_to_create:
                            permissions_to_create[perm_key] = {'module': module, 'sub_module': None, 'can_view': False, 'can_create': False, 'can_edit': False, 'can_delete': False}
                        if action == 'view': permissions_to_create[perm_key]['can_view'] = True
                        elif action == 'create': permissions_to_create[perm_key]['can_create'] = True
                        elif action == 'edit': permissions_to_create[perm_key]['can_edit'] = True
                        elif action == 'delete': permissions_to_create[perm_key]['can_delete'] = True
                    elif len(parts) == 4 and parts[1] == 'subs':
                        module, _, sub_module, action = parts
                        perm_key = (module, sub_module)
                        if perm_key not in permissions_to_create:
                            permissions_to_create[perm_key] = {'module': module, 'sub_module': sub_module, 'can_view': False, 'can_create': False, 'can_edit': False, 'can_delete': False}
                        if action == 'view': permissions_to_create[perm_key]['can_view'] = True
                        elif action == 'create': permissions_to_create[perm_key]['can_create'] = True
                        elif action == 'edit': permissions_to_create[perm_key]['can_edit'] = True
                        elif action == 'delete': permissions_to_create[perm_key]['can_delete'] = True

                RolePermission.objects.filter(role=target_role).delete()
                new_permissions = [RolePermission(role=target_role, **d) for d in permissions_to_create.values()]
                if new_permissions:
                    RolePermission.objects.bulk_create(new_permissions)

            invalidate_role_permissions_cache(old_role_name)
            invalidate_role_permissions_cache(target_role)

            return JsonResponse({'success': True, 'message': f'Permissions untuk role berhasil diupdate! ({len(new_permissions)} permissions)'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@method_decorator(login_required, name='dispatch')
class RoleDeleteView(DeletePermissionMixin, View):
    """AJAX: Hapus role beserta semua permission-nya."""
    permission_module = 'access_control'
    def post(self, request, role_code):
        import json as json_lib
        try:
            if role_code == 'SUPERUSER':
                return JsonResponse({'success': False, 'message': 'Role SUPERUSER tidak dapat dihapus.'}, status=400)

            user_count = Profile.objects.filter(role=role_code).count()
            force = False
            try:
                body = json_lib.loads(request.body) if request.body else {}
                force = body.get('force', False)
            except (json_lib.JSONDecodeError, ValueError):
                force = False

            if user_count > 0 and not force:
                return JsonResponse({
                    'success': False, 'has_users': True, 'user_count': user_count,
                    'message': f'Role masih digunakan oleh {user_count} user.'
                }, status=400)

            from django.db import transaction
            with transaction.atomic():
                if user_count > 0 and force:
                    Profile.objects.filter(role=role_code).update(role='')

                deleted_count, _ = RolePermission.objects.filter(role=role_code).delete()
            invalidate_role_permissions_cache(role_code)

            return JsonResponse({'success': True, 'message': f'Role berhasil dihapus. ({deleted_count} permission records dihapus)'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)
