"""
Chat session security using JWT tokens
Provides centralized validation for both REST API and WebSocket connections
"""
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied
from typing import Optional, Dict


class ChatSessionValidator:
    """JWT-based session validation for chat access control"""

    # Token expiration (24 hours)
    TOKEN_EXPIRATION_HOURS = 24

    # Epoch key TTL — must outlive longest-lived token that could carry a stale epoch.
    # Matches SESSION_COOKIE_AGE (14 days) for safety.
    EPOCH_TTL_SECONDS = 14 * 24 * 60 * 60

    @classmethod
    def _epoch_cache_key(cls, chat_code: str, username: str) -> str:
        return f"jwt_epoch:{chat_code}:{username}"

    @classmethod
    def get_epoch(cls, chat_code: str, username: str) -> int:
        """Return current revocation epoch for (chat, username). 0 if unset."""
        return cache.get(cls._epoch_cache_key(chat_code, username), 0) or 0

    @classmethod
    def bump_epoch(cls, chat_code: str, username: str) -> int:
        """
        Increment the revocation epoch for (chat, username), invalidating
        all outstanding JWT tokens for that user in that chat.
        """
        key = cls._epoch_cache_key(chat_code, username)
        try:
            new_value = cache.incr(key)
            # Refresh TTL on incr (django-redis incr does not refresh TTL)
            try:
                cache.expire(key, cls.EPOCH_TTL_SECONDS)
            except Exception:
                pass
            return new_value
        except ValueError:
            # Key doesn't exist yet — initialize it
            cache.set(key, 1, timeout=cls.EPOCH_TTL_SECONDS)
            return 1

    @classmethod
    def create_session_token(
        cls,
        chat_code: str,
        username: str,
        user_id: Optional[str] = None,
        fingerprint: Optional[str] = None,
        session_key: Optional[str] = None
    ) -> str:
        """
        Create a JWT session token for chat access

        Args:
            chat_code: Chat room code
            username: User's display name in chat
            user_id: Optional authenticated user ID
            fingerprint: Optional browser fingerprint (for ban enforcement)
            session_key: Optional Django session key (primary anonymous identifier)

        Returns:
            JWT token string
        """
        payload = {
            'chat_code': chat_code,
            'username': username,
            'user_id': str(user_id) if user_id else None,
            'fingerprint': fingerprint,  # For ban enforcement
            'session_key': session_key,  # Primary anonymous identifier
            'epoch': cls.get_epoch(chat_code, username),  # Revocation epoch
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=cls.TOKEN_EXPIRATION_HOURS)
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        # Also maintain active users in Redis for quick lookups
        cls._add_to_active_users(chat_code, username)

        return token

    @classmethod
    def validate_session_token(
        cls,
        token: str,
        chat_code: Optional[str] = None,
        username: Optional[str] = None,
        request=None,
    ) -> Dict:
        """
        Validate a JWT session token

        Args:
            token: JWT token to validate
            chat_code: Optional chat code to verify against
            username: Optional username to verify against
            request: Optional Django request — when provided, anonymous tokens
                (no user_id) are bound to the current Django session_key. This
                prevents a leaked JWT from being replayed from a different
                browser. Authenticated tokens (with user_id) skip this check
                because they authenticate via Authorization header.

        Returns:
            Decoded token payload

        Raises:
            PermissionDenied: If token is invalid, expired, or doesn't match constraints
        """
        try:
            # Decode and verify JWT
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )

            # Manually require expiration claim (PyJWT's require_exp doesn't work)
            if 'exp' not in payload:
                raise PermissionDenied("Token must have an expiration")

            # Verify chat code if provided
            if chat_code and payload.get('chat_code') != chat_code:
                raise PermissionDenied("Token not valid for this chat room")

            # Verify username if provided
            if username and payload.get('username') != username:
                raise PermissionDenied("Username mismatch in token")

            # SECURITY: Bind anonymous tokens to current Django session_key.
            # If user_id is set, the caller is an authenticated user and
            # authenticates via Authorization header — skip this check.
            # If request is None, skip for backwards compatibility.
            if request is not None and payload.get('user_id') is None:
                token_session_key = payload.get('session_key')
                if token_session_key:
                    current_session_key = getattr(
                        getattr(request, 'session', None), 'session_key', None
                    )
                    if current_session_key != token_session_key:
                        raise PermissionDenied(
                            "Session mismatch — please rejoin the chat"
                        )

            # SECURITY: JWT revocation via per-(chat, username) epoch counter.
            # If a host bumps the epoch (e.g., on ban), all outstanding tokens
            # stamped with an older epoch are immediately invalidated.
            # Legacy tokens with no `epoch` claim are treated as epoch=0; they
            # remain valid until either natural expiration or an explicit bump
            # raises the floor above 0.
            token_epoch = payload.get('epoch', 0) or 0
            current_epoch = cls.get_epoch(
                payload.get('chat_code'), payload.get('username')
            )
            if token_epoch < current_epoch:
                raise PermissionDenied(
                    "Session revoked — please rejoin the chat"
                )

            # Optionally verify user is still in active users (for extra security)
            token_chat_code = payload.get('chat_code')
            token_username = payload.get('username')

            if token_chat_code and token_username:
                active_users = cls._get_active_users(token_chat_code)
                if token_username not in active_users:
                    # User was removed from chat - refresh active users list
                    cls._add_to_active_users(token_chat_code, token_username)

            return payload

        except jwt.ExpiredSignatureError:
            raise PermissionDenied({"error": "session_expired", "detail": "Session token has expired"})
        except jwt.InvalidTokenError as e:
            raise PermissionDenied(f"Invalid session token: {str(e)}")

    @classmethod
    def revoke_session(cls, chat_code: str, username: str):
        """
        Revoke a user's session (remove from active users)
        Note: JWT tokens will still be valid until expiration, but user
        won't be in active users list
        """
        cls._remove_from_active_users(chat_code, username)

    @classmethod
    def _get_active_users(cls, chat_code: str) -> set:
        """Get set of active usernames for a chat from Redis"""
        cache_key = f"chat_{chat_code}_active_users"
        return cache.get(cache_key, set())

    @classmethod
    def _add_to_active_users(cls, chat_code: str, username: str):
        """Add username to active users set in Redis"""
        cache_key = f"chat_{chat_code}_active_users"
        active_users = cache.get(cache_key, set())
        active_users.add(username)
        # Keep in sync with token expiration
        cache.set(cache_key, active_users, timeout=cls.TOKEN_EXPIRATION_HOURS * 3600)

    @classmethod
    def _remove_from_active_users(cls, chat_code: str, username: str):
        """Remove username from active users set in Redis"""
        cache_key = f"chat_{chat_code}_active_users"
        active_users = cache.get(cache_key, set())
        active_users.discard(username)
        cache.set(cache_key, active_users, timeout=cls.TOKEN_EXPIRATION_HOURS * 3600)

    @classmethod
    def get_active_user_count(cls, chat_code: str) -> int:
        """Get count of active users in a chat"""
        return len(cls._get_active_users(chat_code))

    @classmethod
    def decode_token_ignore_expiry(cls, token: str) -> Optional[Dict]:
        """Decode a JWT without verifying expiration (for refresh flow).
        Returns None if signature is invalid."""
        try:
            return jwt.decode(
                token, settings.SECRET_KEY, algorithms=['HS256'],
                options={"verify_exp": False}
            )
        except jwt.InvalidTokenError:
            return None

