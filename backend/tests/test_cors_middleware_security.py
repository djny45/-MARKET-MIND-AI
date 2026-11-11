import unittest

from fastapi.middleware.cors import CORSMiddleware

from app.main import app


class CorsMiddlewareSecurityTests(unittest.TestCase):
    def test_cross_origin_credentials_are_disabled(self):
        cors_middleware = next(
            middleware
            for middleware in app.user_middleware
            if middleware.cls is CORSMiddleware
        )

        self.assertFalse(cors_middleware.kwargs["allow_credentials"])


if __name__ == "__main__":
    unittest.main()
