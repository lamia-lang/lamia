"""Tests for lamia.interpreter.hybrid_file_cache."""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from lamia.interpreter.hybrid_file_cache import HybridFileCache


@pytest.fixture
def temp_dir():
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


class TestHybridFileCacheInitialization:

    def test_init_with_defaults(self):
        cache = HybridFileCache()

        assert cache.cache_enabled is True
        assert cache.cache_dir_name == '.lamia_cache'

    def test_init_with_custom_parameters(self):
        cache = HybridFileCache(cache_enabled=False, cache_dir_name='custom_cache')

        assert cache.cache_enabled is False
        assert cache.cache_dir_name == 'custom_cache'

    def test_init_cache_disabled(self):
        cache = HybridFileCache(cache_enabled=False)

        assert cache.cache_enabled is False


class TestHybridFileCachePathOperations:

    def test_get_cache_path(self, temp_dir):
        cache = HybridFileCache()
        hybrid_file = os.path.join(temp_dir, "script.lm")

        cache_path = cache.get_cache_path(hybrid_file)

        expected_path = os.path.join(temp_dir, ".lamia_cache", "script.py")
        assert cache_path == expected_path

    def test_get_cache_path_creates_directory(self, temp_dir):
        cache = HybridFileCache(cache_enabled=True)
        hybrid_file = os.path.join(temp_dir, "script.lm")

        cache_path = cache.get_cache_path(hybrid_file)

        cache_dir = os.path.dirname(cache_path)
        assert os.path.exists(cache_dir)

    def test_get_cache_path_disabled_no_directory(self, temp_dir):
        cache = HybridFileCache(cache_enabled=False)
        hybrid_file = os.path.join(temp_dir, "script.lm")

        cache_path = cache.get_cache_path(hybrid_file)

        cache_dir = os.path.dirname(cache_path)
        assert not os.path.exists(cache_dir)

    def test_get_cache_path_with_subdirectory(self, temp_dir):
        cache = HybridFileCache()
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)
        hybrid_file = os.path.join(subdir, "script.lm")

        cache_path = cache.get_cache_path(hybrid_file)

        expected_path = os.path.join(subdir, ".lamia_cache", "script.py")
        assert cache_path == expected_path


class TestHybridFileCacheValidation:

    def test_is_cache_valid_no_cache_file(self, temp_dir):
        cache = HybridFileCache()
        hybrid_file = os.path.join(temp_dir, "script.lm")
        cache_path = cache.get_cache_path(hybrid_file)

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is False

    def test_is_cache_valid_cache_disabled(self, temp_dir):
        cache = HybridFileCache(cache_enabled=False)
        hybrid_file = os.path.join(temp_dir, "script.lm")
        cache_path = cache.get_cache_path(hybrid_file)

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is False

    def test_is_cache_valid_newer_cache(self, temp_dir):
        cache = HybridFileCache()
        hybrid_file = os.path.join(temp_dir, "script.lm")
        with open(hybrid_file, 'w') as f:
            f.write("def test(): pass")

        old_time = os.path.getmtime(hybrid_file) - 1
        os.utime(hybrid_file, (old_time, old_time))

        cache_path = cache.get_cache_path(hybrid_file)
        with open(cache_path, 'w') as f:
            f.write("def test(): pass")

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is True

    def test_is_cache_valid_older_cache(self, temp_dir):
        cache = HybridFileCache()
        hybrid_file = os.path.join(temp_dir, "script.lm")
        cache_path = cache.get_cache_path(hybrid_file)
        with open(cache_path, 'w') as f:
            f.write("def test(): pass")

        with open(hybrid_file, 'w') as f:
            f.write("def test(): pass")
        future_time = os.path.getmtime(cache_path) + 1
        os.utime(hybrid_file, (future_time, future_time))

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is False


class TestHybridFileCacheReadWrite:

    def test_write_to_cache(self, temp_dir):
        cache = HybridFileCache()
        cache_path = os.path.join(temp_dir, ".lamia_cache", "test.py")
        transformed_code = "def transformed(): return 42"

        success = cache.write_to_cache(cache_path, transformed_code)

        assert success is True
        assert os.path.exists(cache_path)
        with open(cache_path, 'r') as f:
            assert f.read() == transformed_code

    def test_write_to_cache_disabled(self, temp_dir):
        cache = HybridFileCache(cache_enabled=False)
        cache_path = os.path.join(temp_dir, "test.py")
        transformed_code = "def transformed(): return 42"

        success = cache.write_to_cache(cache_path, transformed_code)

        assert success is False
        assert not os.path.exists(cache_path)

    def test_read_from_cache(self, temp_dir):
        cache = HybridFileCache()
        cache_path = os.path.join(temp_dir, ".lamia_cache", "test.py")
        expected_code = "def cached(): return 42"

        cache.write_to_cache(cache_path, expected_code)
        result = cache.read_from_cache(cache_path)

        assert result == expected_code

    def test_read_from_cache_disabled(self, temp_dir):
        cache = HybridFileCache(cache_enabled=False)
        cache_path = os.path.join(temp_dir, "test.py")

        result = cache.read_from_cache(cache_path)

        assert result is None

    def test_read_from_cache_missing_file(self, temp_dir):
        cache = HybridFileCache()
        cache_path = os.path.join(temp_dir, "nonexistent.py")

        result = cache.read_from_cache(cache_path)

        assert result is None
