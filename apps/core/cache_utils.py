"""
Utilitas cache terpusat untuk permission, response cache, dan context cache.

Cache dibuat berbasis versi supaya bisa di-refresh tanpa delete by pattern.
Scope cache juga membawa schema/host aktif agar aman untuk varian Isolated Schema.
"""
from functools import wraps
import hashlib

from django.core.cache import cache
from django.db import connection


DEFAULT_TENANT_CACHE_NAMESPACES = ('view_response', 'context_processor')


def normalize_role_code(role_code):
    """Normalisasi role agar cache key konsisten."""
    return str(role_code or '').strip().upper()


def get_user_permissions_cache_version(user_id):
    return cache.get(f'user_perms_version_{user_id}', 1)


def bump_user_permissions_cache_version(user_id):
    if not user_id:
        return
    cache_key = f'user_perms_version_{user_id}'
    cache.set(cache_key, cache.get(cache_key, 1) + 1, None)


def get_role_permissions_cache_version(role_code):
    role = normalize_role_code(role_code)
    return cache.get(f'role_perms_version_{role}', 1)


def bump_role_permissions_cache_version(role_code):
    role = normalize_role_code(role_code)
    cache_key = f'role_perms_version_{role}'
    cache.set(cache_key, cache.get(cache_key, 1) + 1, None)


def get_role_permissions_cache_key(role_code):
    role = normalize_role_code(role_code)
    version = get_role_permissions_cache_version(role)
    return f'role_perms_{role}_v{version}'


def get_tenant_cache_scope(request=None):
    """Scope response cache per schema/host."""
    tenant = getattr(request, 'tenant', None) if request is not None else None
    schema_name = (
        getattr(tenant, 'schema_name', None)
        or getattr(connection, 'schema_name', None)
        or 'default'
    )
    host = request.get_host() if request is not None else ''
    return f'{schema_name}:{host}'


def get_tenant_cache_version_scope(request=None):
    """Scope versi cache per schema, dipakai juga oleh signal tanpa request."""
    tenant = getattr(request, 'tenant', None) if request is not None else None
    return str(
        getattr(tenant, 'schema_name', None)
        or getattr(connection, 'schema_name', None)
        or 'default'
    )


def get_tenant_namespace_cache_version(namespace, request=None):
    scope = get_tenant_cache_version_scope(request)
    return cache.get(f'tenant_cache_version:{scope}:{namespace}', 1)


def bump_tenant_namespace_cache_version(namespace, request=None):
    scope = get_tenant_cache_version_scope(request)
    cache_key = f'tenant_cache_version:{scope}:{namespace}'
    next_version = cache.get(cache_key, 1) + 1
    cache.set(cache_key, next_version, None)
    return next_version


def invalidate_tenant_response_cache(request=None, namespaces=None):
    """Invalidate dashboard/laporan/context tenant aktif via version bump."""
    target_namespaces = namespaces or DEFAULT_TENANT_CACHE_NAMESPACES
    versions = {}
    for namespace in target_namespaces:
        versions[namespace] = bump_tenant_namespace_cache_version(namespace, request=request)
    return {
        'scope': get_tenant_cache_version_scope(request),
        'versions': versions,
    }


def build_scoped_cache_key(namespace, *parts, request=None):
    """Buat cache key pendek yang aman untuk tenant, user, role, dan query string."""
    scope_parts = [
        namespace,
        get_tenant_cache_scope(request),
        f'cache_ver:{get_tenant_namespace_cache_version(namespace, request=request)}',
    ]
    if request is not None:
        user = getattr(request, 'user', None)
        scope_parts.extend([request.method, request.get_full_path()])
        if user and getattr(user, 'is_authenticated', False):
            try:
                role = normalize_role_code(getattr(user.profile, 'role', ''))
            except Exception:
                role = ''
            scope_parts.extend([
                f'user:{user.pk}',
                f'user_ver:{get_user_permissions_cache_version(user.pk)}',
                f'role:{role}',
                f'role_ver:{get_role_permissions_cache_version(role)}',
            ])
        else:
            scope_parts.append('anonymous')
    scope_parts.extend(str(part) for part in parts)
    digest = hashlib.sha256('|'.join(scope_parts).encode('utf-8')).hexdigest()
    return f'{namespace}:{digest}'


def cache_user_permissions(timeout=300):
    """Decorator permission cache berbasis versi user."""
    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            if not user or not user.is_authenticated:
                return func(user, *args, **kwargs)
            version = get_user_permissions_cache_version(user.id)
            cache_key = f'user_perms_{user.id}_v{version}_{func.__name__}_{"-".join(map(str, args))}'
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = func(user, *args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def invalidate_user_permissions_cache(user_id):
    bump_user_permissions_cache_version(user_id)


def invalidate_role_permissions_cache(role_code):
    """Invalidate permission role dan user yang memakai role tersebut."""
    from auth.models import Profile

    role = normalize_role_code(role_code)
    bump_role_permissions_cache_version(role)
    for candidate in {role, role.lower(), str(role_code or '').strip()}:
        if candidate:
            cache.delete(f'role_perms_{candidate}')

    user_ids = Profile.objects.filter(role__iexact=role).values_list('user_id', flat=True)
    for user_id in user_ids:
        invalidate_user_permissions_cache(user_id)
