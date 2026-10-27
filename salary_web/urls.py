from django.urls import path
from webapp.views import index

urlpatterns = [path("", index, name="index")]
