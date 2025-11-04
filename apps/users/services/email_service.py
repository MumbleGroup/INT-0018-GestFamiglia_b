"""
Email service for user-related notifications
"""
from django.core.mail import EmailMultiAlternatives
from django.conf import settings


class EmailService:
    """Service for sending user-related emails"""

    @staticmethod
    def get_user_language(user):
        """
        Get user's preferred language from profile

        Args:
            user: User instance

        Returns:
            str: Language code ('it' or 'en')
        """
        if hasattr(user, 'profile') and user.profile.ui_preferences:
            return user.profile.ui_preferences.get('language', 'it')
        return 'it'

    @staticmethod
    def send_welcome_email(user):
        """
        Send welcome email to newly registered user

        Args:
            user: User instance

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        # Get user language
        lang = EmailService.get_user_language(user)

        # Translations
        translations = {
            'it': {
                'subject': 'Benvenuto in MyCrisisFamily',
                'greeting': 'Ciao',
                'intro': 'Il tuo account è stato creato con successo.',
                'account_details': 'DETTAGLI ACCOUNT',
                'email_label': 'Email',
                'plan_label': 'Piano',
                'plan_value': 'Gratuito (tutte le funzionalità)',
                'status_label': 'Stato',
                'status_value': 'Attivo',
                'login_now': 'ACCEDI ORA',
                'login_button': 'Accedi ora →',
                'what_you_can_do': 'Cosa puoi fare',
                'feature_1': 'Traccia le spese familiari',
                'feature_2': 'Gestisci budget mensili',
                'feature_3': 'Condividi con la famiglia',
                'feature_4': 'Visualizza report e statistiche',
                'questions': 'Hai domande? Rispondi a questa email.',
                'app_name': 'MyCrisisFamily',
                'app_tagline': 'Gestione Spese Familiari',
            },
            'en': {
                'subject': 'Welcome to MyCrisisFamily',
                'greeting': 'Hello',
                'intro': 'Your account has been successfully created.',
                'account_details': 'ACCOUNT DETAILS',
                'email_label': 'Email',
                'plan_label': 'Plan',
                'plan_value': 'Free (all features)',
                'status_label': 'Status',
                'status_value': 'Active',
                'login_now': 'LOGIN NOW',
                'login_button': 'Login now →',
                'what_you_can_do': 'What you can do',
                'feature_1': 'Track family expenses',
                'feature_2': 'Manage monthly budgets',
                'feature_3': 'Share with family',
                'feature_4': 'View reports and statistics',
                'questions': 'Have questions? Reply to this email.',
                'app_name': 'MyCrisisFamily',
                'app_tagline': 'Family Expense Management',
            }
        }

        t = translations.get(lang, translations['it'])
        subject = t['subject']

        # Context
        context = {
            'user_name': user.first_name if user.first_name else user.username,
            'user_email': user.email,
            'login_url': f"{settings.FRONTEND_URL}/#/login",
            'app_url': settings.FRONTEND_URL,
        }

        # Plain text - PRIORITARIO
        text_content = f"""
{t['subject']}

{t['greeting']} {context['user_name']},

{t['intro']}

{t['account_details']}
{t['email_label']}: {context['user_email']}
{t['plan_label']}: {t['plan_value']}
{t['status_label']}: {t['status_value']}

{t['login_now']}
{context['login_url']}

{t['what_you_can_do'].upper()}

• {t['feature_1']}
• {t['feature_2']}
• {t['feature_3']}
• {t['feature_4']}

{t['questions']}

---
{t['app_name']}
{t['app_tagline']}
{context['app_url']}

© 2025 MUMBLE.GROUP
        """.strip()

        # HTML minimale - solo per formattazione base
        html_content = f"""
<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background-color: #fafafa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fafafa; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background: white; border: 1px solid #e5e5e5;">

                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 24px; border-bottom: 1px solid #e5e5e5;">
                            <h1 style="margin: 0; font-size: 24px; font-weight: 600; color: #000; letter-spacing: -0.5px;">
                                {t['subject']}
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; color: #171717; font-size: 15px; line-height: 24px;">

                            <p style="margin: 0 0 24px;">
                                {t['greeting']} <strong>{context['user_name']}</strong>,
                            </p>

                            <p style="margin: 0 0 32px; color: #525252;">
                                {t['intro']}
                            </p>

                            <!-- Account Details -->
                            <div style="background: #fafafa; border-left: 2px solid #000; padding: 16px 20px; margin: 0 0 32px;">
                                <p style="margin: 0 0 12px; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #000;">
                                    {t['account_details']}
                                </p>
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td style="padding: 6px 0; color: #737373; font-size: 14px;">{t['email_label']}</td>
                                        <td style="padding: 6px 0; color: #171717; font-size: 14px; text-align: right;">{context['user_email']}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 6px 0; color: #737373; font-size: 14px;">{t['plan_label']}</td>
                                        <td style="padding: 6px 0; color: #171717; font-size: 14px; text-align: right;">{t['plan_value']}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 6px 0; color: #737373; font-size: 14px;">{t['status_label']}</td>
                                        <td style="padding: 6px 0; color: #171717; font-size: 14px; text-align: right;">{t['status_value']}</td>
                                    </tr>
                                </table>
                            </div>

                            <!-- CTA -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 32px;">
                                <tr>
                                    <td align="left">
                                        <a href="{context['login_url']}" style="display: inline-block; background: #000; color: #fff; text-decoration: none; padding: 12px 24px; font-size: 14px; font-weight: 500; border-radius: 2px;">
                                            {t['login_button']}
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Features -->
                            <p style="margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #000;">
                                {t['what_you_can_do']}
                            </p>
                            <ul style="margin: 0 0 32px; padding-left: 20px; color: #525252; font-size: 14px; line-height: 22px;">
                                <li style="margin-bottom: 8px;">{t['feature_1']}</li>
                                <li style="margin-bottom: 8px;">{t['feature_2']}</li>
                                <li style="margin-bottom: 8px;">{t['feature_3']}</li>
                                <li style="margin-bottom: 8px;">{t['feature_4']}</li>
                            </ul>

                            <p style="margin: 0; color: #737373; font-size: 14px;">
                                {t['questions']}
                            </p>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; border-top: 1px solid #e5e5e5; background: #fafafa;">
                            <p style="margin: 0 0 8px; font-size: 14px; font-weight: 600; color: #000;">
                                {t['app_name']}
                            </p>
                            <p style="margin: 0 0 16px; font-size: 13px; color: #737373;">
                                {t['app_tagline']}
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #a3a3a3;">
                                © 2025 MUMBLE.GROUP
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """.strip()

        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            print(f"✅ Welcome email sent to {user.email}")
            return True
        except Exception as e:
            print(f"❌ Failed to send welcome email to {user.email}: {e}")
            return False

    @staticmethod
    def send_password_reset_email(user, reset_token):
        """
        Send password reset email

        Args:
            user: User instance
            reset_token: PasswordResetToken instance

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        # Get user language
        lang = EmailService.get_user_language(user)

        # Translations
        translations = {
            'it': {
                'subject': 'Reset della password',
                'greeting': 'Ciao',
                'intro': 'Hai richiesto di reimpostare la password del tuo account.',
                'reset_password': 'REIMPOSTA PASSWORD',
                'reset_button': 'Reimposta password →',
                'important': 'IMPORTANTE',
                'warning_1': 'Il link è valido per 24 ore',
                'warning_2': 'Può essere usato una sola volta',
                'warning_3': 'Se non hai fatto tu questa richiesta, ignora questa email',
                'security_note': 'Il tuo account rimarrà sicuro finché non userai questo link.',
                'fallback_label': 'Se il pulsante non funziona, copia questo link:',
                'app_name': 'MyCrisisFamily',
                'app_tagline': 'Gestione Spese Familiari',
            },
            'en': {
                'subject': 'Password Reset',
                'greeting': 'Hello',
                'intro': 'You have requested to reset your account password.',
                'reset_password': 'RESET PASSWORD',
                'reset_button': 'Reset password →',
                'important': 'IMPORTANT',
                'warning_1': 'The link is valid for 24 hours',
                'warning_2': 'It can be used only once',
                'warning_3': 'If you did not make this request, ignore this email',
                'security_note': 'Your account will remain secure until you use this link.',
                'fallback_label': 'If the button doesn\'t work, copy this link:',
                'app_name': 'MyCrisisFamily',
                'app_tagline': 'Family Expense Management',
            }
        }

        t = translations.get(lang, translations['it'])
        subject = t['subject']

        reset_url = f"{settings.FRONTEND_URL}/#/reset-password?token={reset_token.token}"

        # Context
        context = {
            'user_name': user.first_name if user.first_name else user.username,
            'reset_url': reset_url,
            'app_url': settings.FRONTEND_URL,
        }

        # Plain text - PRIORITARIO
        text_content = f"""
{t['subject']}

{t['greeting']} {context['user_name']},

{t['intro']}

{t['reset_password']}
{context['reset_url']}

{t['important']}
• {t['warning_1']}
• {t['warning_2']}
• {t['warning_3']}

{t['security_note']}

---
{t['app_name']}
{t['app_tagline']}
{context['app_url']}

© 2025 MUMBLE.GROUP
        """.strip()

        # HTML minimale
        html_content = f"""
<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background-color: #fafafa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fafafa; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background: white; border: 1px solid #e5e5e5;">

                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 24px; border-bottom: 1px solid #e5e5e5;">
                            <h1 style="margin: 0; font-size: 24px; font-weight: 600; color: #000; letter-spacing: -0.5px;">
                                {t['subject']}
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; color: #171717; font-size: 15px; line-height: 24px;">

                            <p style="margin: 0 0 24px;">
                                {t['greeting']} <strong>{context['user_name']}</strong>,
                            </p>

                            <p style="margin: 0 0 32px; color: #525252;">
                                {t['intro']}
                            </p>

                            <!-- CTA -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 32px;">
                                <tr>
                                    <td align="left">
                                        <a href="{context['reset_url']}" style="display: inline-block; background: #000; color: #fff; text-decoration: none; padding: 12px 24px; font-size: 14px; font-weight: 500; border-radius: 2px;">
                                            {t['reset_button']}
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Warning -->
                            <div style="background: #fafafa; border-left: 2px solid #000; padding: 16px 20px; margin: 0 0 32px;">
                                <p style="margin: 0 0 12px; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #000;">
                                    {t['important']}
                                </p>
                                <ul style="margin: 0; padding-left: 20px; color: #525252; font-size: 14px; line-height: 22px;">
                                    <li style="margin-bottom: 8px;">{t['warning_1']}</li>
                                    <li style="margin-bottom: 8px;">{t['warning_2']}</li>
                                    <li>{t['warning_3']}</li>
                                </ul>
                            </div>

                            <p style="margin: 0 0 16px; color: #737373; font-size: 14px;">
                                {t['security_note']}
                            </p>

                            <!-- Link fallback -->
                            <div style="background: #fafafa; border: 1px solid #e5e5e5; padding: 12px; margin: 0 0 24px;">
                                <p style="margin: 0 0 8px; font-size: 12px; color: #737373;">
                                    {t['fallback_label']}
                                </p>
                                <p style="margin: 0; font-size: 12px; font-family: monospace; color: #171717; word-break: break-all;">
                                    {context['reset_url']}
                                </p>
                            </div>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; border-top: 1px solid #e5e5e5; background: #fafafa;">
                            <p style="margin: 0 0 8px; font-size: 14px; font-weight: 600; color: #000;">
                                {t['app_name']}
                            </p>
                            <p style="margin: 0 0 16px; font-size: 13px; color: #737373;">
                                {t['app_tagline']}
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #a3a3a3;">
                                © 2025 MUMBLE.GROUP
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """.strip()

        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            print(f"✅ Password reset email sent to {user.email}")
            return True
        except Exception as e:
            print(f"❌ Failed to send password reset email to {user.email}: {e}")
            return False
