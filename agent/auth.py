from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse

def login_required_json(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        accept = request.headers.get("Accept", "")
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if "application/json" in accept or is_ajax:
            return JsonResponse({"error": "auth_required"}, status=401)
        return redirect_to_login(request.get_full_path())
    return _wrapped

