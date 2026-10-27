import os
from django.shortcuts import render


def index(request):
    return render(request, "index.html", {"salary_api_url": os.environ.get("SALARY_API_URL", "http://127.0.0.1:8001")})
