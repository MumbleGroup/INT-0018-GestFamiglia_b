#!/usr/bin/env python3
"""
Test email templates - Send to marcoserra@pcbuster.it
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from django.contrib.auth import get_user_model
from apps.users.models import PasswordResetToken
from apps.users.services import EmailService
from django.utils import timezone

User = get_user_model()

def test_emails():
    """Test both welcome and password reset emails"""

    print("=" * 70)
    print("🧪 TEST EMAIL TEMPLATES")
    print("=" * 70)
    print(f"Destinatario: marcoserra@pcbuster.it")
    print("=" * 70)

    # Create or get test user
    test_email = "marcoserra@pcbuster.it"

    try:
        # Try to get existing user or create new one
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

        print("\n" + "-" * 70)
        print("📧 TEST 1: WELCOME EMAIL")
        print("-" * 70)

        # Test welcome email
        result1 = EmailService.send_welcome_email(user)

        if result1:
            print("✅ Welcome email sent successfully!")
        else:
            print("❌ Failed to send welcome email")

        print("\n" + "-" * 70)
        print("📧 TEST 2: PASSWORD RESET EMAIL")
        print("-" * 70)

        # Create password reset token
        # Delete old tokens for this user
        PasswordResetToken.objects.filter(user=user).delete()

        reset_token = PasswordResetToken.objects.create(user=user)

        # Test password reset email
        result2 = EmailService.send_password_reset_email(user, reset_token)

        if result2:
            print("✅ Password reset email sent successfully!")
            print(f"\n🔗 Reset URL: {reset_token.token}")
        else:
            print("❌ Failed to send password reset email")

        print("\n" + "=" * 70)
        print("✅ TEST COMPLETATO!")
        print("=" * 70)
        print(f"\n📬 Controlla la casella: {test_email}")
        print("   (Controlla anche spam/posta indesiderata)")
        print("\n📊 Riepilogo:")
        print(f"   - Welcome Email: {'✅ Inviata' if result1 else '❌ Fallita'}")
        print(f"   - Password Reset Email: {'✅ Inviata' if result2 else '❌ Fallita'}")
        print("=" * 70)

        return result1 and result2

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ ERRORE DURANTE IL TEST")
        print("=" * 70)
        print(f"Tipo: {type(e).__name__}")
        print(f"Dettagli: {e}")
        import traceback
        print("\nStacktrace:")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_emails()
    exit(0 if success else 1)
