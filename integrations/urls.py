from django.urls import path, include

urlpatterns = [

    path('spotify/', include('integrations.urls.spotify')),
]