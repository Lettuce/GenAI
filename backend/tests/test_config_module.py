from app.config import settings as app_settings
from app.schemas.config import settings as schema_settings


def test_settings_module_is_available_from_app_config() -> None:
    assert app_settings is schema_settings
