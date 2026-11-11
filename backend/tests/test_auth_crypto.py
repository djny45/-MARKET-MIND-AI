import unittest

from app.auth_crypto import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_csrf_token,
    verify_password,
)


class AuthenticationCryptoTests(unittest.TestCase):
    def test_password_hash_is_salted_and_verifiable(self):
        first = hash_password("correct horse battery staple")
        second = hash_password("correct horse battery staple")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("correct horse battery staple", first))
        self.assertFalse(verify_password("incorrect password", first))

    def test_password_verification_rejects_malformed_hashes(self):
        for malformed in ("", "scrypt$1$1$1$bad$bad", "plain-text-password", None):
            with self.subTest(malformed=malformed):
                self.assertFalse(verify_password("anything", malformed))

    def test_password_hash_rejects_empty_or_oversized_input(self):
        with self.assertRaises(ValueError):
            hash_password("")
        with self.assertRaises(ValueError):
            hash_password("x" * 1025)

    def test_session_token_is_random_and_only_digest_is_persistable(self):
        first = generate_session_token()
        second = generate_session_token()
        self.assertNotEqual(first, second)
        digest = hash_session_token(first)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, hash_session_token(first))
        self.assertNotEqual(digest, first)
        with self.assertRaises(ValueError):
            hash_session_token("not-a-session-token")

    def test_csrf_tokens_are_random_and_compared_safely(self):
        expected = generate_csrf_token()
        supplied = generate_csrf_token()
        self.assertTrue(verify_csrf_token(expected, expected))
        self.assertFalse(verify_csrf_token(supplied, expected))
        self.assertFalse(verify_csrf_token("", expected))
        self.assertFalse(verify_csrf_token(None, expected))


if __name__ == "__main__":
    unittest.main()
