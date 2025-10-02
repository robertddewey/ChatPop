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

    @classmethod
    def create_session_token(
        cls,
        chat_code: str,
        username: str,
        user_id: Optional[str] = None
    ) -> str:
        """
        Create a JWT session token for chat access

        Args:
            chat_code: Chat room code
            username: User's display name in chat
            user_id: Optional authenticated user ID

        Returns:
            JWT token string
        """
        payload = {
            'chat_code': chat_code,
            'username': username,
            'user_id': user_id,
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
        username: Optional[str] = None
    ) -> Dict:
        """
        Validate a JWT session token

        Args:
            token: JWT token to validate
            chat_code: Optional chat code to verify against
            username: Optional username to verify against

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
            raise PermissionDenied("Session token has expired")
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
