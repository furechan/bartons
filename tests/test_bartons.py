from bartons import plugin


def test_plugin_importable_and_versioned():
    assert isinstance(plugin.__version__, str)
    assert plugin.__version__
