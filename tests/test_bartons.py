from bartons import kernels


def test_kernels_importable_and_versioned():
    assert isinstance(kernels.__version__, str)
    assert kernels.__version__
