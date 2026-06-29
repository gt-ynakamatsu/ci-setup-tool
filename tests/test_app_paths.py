from cisetup.app_paths import get_package_root


def test_package_root_is_directory():
    root = get_package_root()
    assert root.is_dir()
    assert (root / "bundled_templates").is_dir()
