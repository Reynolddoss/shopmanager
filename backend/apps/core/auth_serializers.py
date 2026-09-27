"""Validate shop registration and login payloads."""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    """
    First-run shop setup. Creates the owner account and shop identity.

    One database = one shop. Registration is allowed only until an owner exists.
    """

    shop_name = serializers.CharField(max_length=255)
    owner_name = serializers.CharField(max_length=128)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    gstin = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    invoice_prefix = serializers.CharField(max_length=16, required=False, allow_blank=True, default="SH")
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def validate_username(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(username__iexact=normalized).exists():
            raise serializers.ValidationError("This username is already taken.")
        return normalized

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class LoginSerializer(serializers.Serializer):
    """Username + password for a local session cookie."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        user = authenticate(username=attrs["username"].strip().lower(), password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")
        attrs["user"] = user
        return attrs
