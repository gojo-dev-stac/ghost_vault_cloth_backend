from rest_framework.routers import SimpleRouter

from .views import ProductViewSet

router = SimpleRouter()
router.register("", ProductViewSet, basename="product")

urlpatterns = router.urls
