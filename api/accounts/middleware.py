from django.http import JsonResponse

class ProfileCompletionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.role == "patient":
            # Allowed paths for incomplete profiles
            allowed_prefixes = [
                "/api/auth/users/me/",
                "/api/me/auth/logout/",
                "/api/regions/",
                "/api/districts/",
            ]
            path = request.path
            
            profile = getattr(request.user, "patient_profile", None)
            if profile and not profile.is_profile_complete:
                if not any(path.startswith(prefix) for prefix in allowed_prefixes):
                    return JsonResponse(
                        {
                            "detail": "Please complete your patient profile before using the system.",
                            "profile_incomplete": True
                        },
                        status=403
                    )

        response = self.get_response(request)
        return response
