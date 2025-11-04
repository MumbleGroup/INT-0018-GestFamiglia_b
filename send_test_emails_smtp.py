#!/usr/bin/env python3
"""
Send test emails via SMTP (production settings)
This script uses base.py settings to actually send emails via SMTP
"""
import os
import sys
import django

# Setup Django with BASE settings (not local)
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from django.contrib.auth import get_user_model
from apps.users.models import PasswordResetToken, UserProfile
from apps.users.services import EmailService

User = get_user_model()

def send_emails():
    """Send test emails in English via SMTP"""

    print("=" * 70)
    print("🧪 SEND MULTILINGUAL EMAIL VIA SMTP - ENGLISH")
    print("=" * 70)
    print("Recipient: marcoserra@pcbuster.it")
    print("SMTP: smtp.zoho.com (no-reply@mycrisisfamily.com)")
    print("=" * 70)

    # Get or create test user
    test_email = "marcoserra@pcbuster.it"

    try:
        user, created = User.objects.get_or_create(
            email=test_email,
            defaults={
                'username': 'marco_test',
                'first_name': 'Marco',
                'last_name': 'Serra',
                'is_active': True
            }
        )

        if created:
            user.set_password('test123456')
            user.save()
            print(f"✅ Test user created: {test_email}")
        else:
            print(f"✅ Using existing user: {test_email}")

        # Create or update profile with English language preference
        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'master',
                'family_role': 'padre',
                'ui_preferences': {'language': 'en'}
            }
        )

        if not profile_created:
            # Update existing profile
            profile.ui_preferences = {'language': 'en'}
            profile.save()
            print(f"✅ Updated profile language to English")
        else:
            print(f"✅ Created profile with English language")

        print(f"🌍 User language: {EmailService.get_user_language(user)}")

        print("\n" + "-" * 70)
        print("📧 TEST 1: WELCOME EMAIL (ENGLISH)")
        print("-" * 70)

        result1 = EmailService.send_welcome_email(user)

        if result1:
            print("✅ Welcome email sent successfully!")
        else:
            print("❌ Failed to send welcome email")

        print("\n" + "-" * 70)
        print("📧 TEST 2: PASSWORD RESET EMAIL (ENGLISH)")
        print("-" * 70)

        # Create password reset token
        PasswordResetToken.objects.filter(user=user).delete()
        reset_token = PasswordResetToken.objects.create(user=user)

        result2 = EmailService.send_password_reset_email(user, reset_token)

        if result2:
            print("✅ Password reset email sent successfully!")
        else:
            print("❌ Failed to send password reset email")

        print("\n" + "=" * 70)
        print("✅ EMAILS SENT VIA SMTP!")
        print("=" * 70)
        print(f"\n📬 Check inbox: {test_email}")
        print("   ⚠️  Also check SPAM/JUNK folder!")
        print("\n📊 Summary:")
        print(f"   - Welcome Email: {'✅ Sent' if result1 else '❌ Failed'}")
        print(f"   - Password Reset Email: {'✅ Sent' if result2 else '❌ Failed'}")
        print("=" * 70)

        return result1 and result2

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ ERROR DURING EMAIL SENDING")
        print("=" * 70)
        print(f"Type: {type(e).__name__}")
        print(f"Details: {e}")
        import traceback
        print("\nStacktrace:")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = send_emails()
    exit(0 if success else 1)
