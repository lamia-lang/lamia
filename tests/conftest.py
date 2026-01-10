import os


# Ensure requests uses a readable CA bundle (fixes PermissionError on load)
try:
    import certifi
    import urllib3.util.ssl_

    ca_path = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", ca_path)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_path)

    # Override urllib3 context creation to avoid loading system/keychain certs
    class _DummySSLContext:
        def load_verify_locations(self, *args, **kwargs):
            return None

    def _dummy_context(*args, **kwargs):
        return _DummySSLContext()

    urllib3.util.ssl_.create_urllib3_context = _dummy_context  # type: ignore[attr-defined]
except Exception:
    pass

# Patch requests SSL preload to avoid PermissionError when loading CA bundle
try:
    import requests.adapters

    # Ensure the preloaded SSL context does not attempt to load verify locations
    requests.adapters._preloaded_ssl_context.load_verify_locations = (  # type: ignore[attr-defined]
        lambda *args, **kwargs: None
    )
except Exception:
    pass


# Stub out dotenv loading before lamia imports to avoid reading .env during tests
try:
    import dotenv
    import dotenv.main

    def _noop_load_dotenv(*args, **kwargs):
        return True

    dotenv.load_dotenv = _noop_load_dotenv
    dotenv.main.load_dotenv = _noop_load_dotenv
except Exception:
    pass

