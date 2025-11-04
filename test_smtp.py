#!/usr/bin/env python3
"""
Test SMTP connection for no-reply@mycrisisfamily.com
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# SMTP Configuration
SMTP_HOST = 'smtp.zoho.com'
SMTP_PORT = 587
SMTP_USER = 'no-reply@mycrisisfamily.com'
SMTP_PASSWORD = 'Mumble100%'

# Test email details
FROM_EMAIL = 'no-reply@mycrisisfamily.com'
TO_EMAIL = 'serra.marco@mycrisisfamily.com'  # Email a te stesso per test
SUBJECT = 'Test SMTP Configuration - MyCrisisFamily'

def test_smtp_connection():
    """Test SMTP connection and authentication"""
    print("=" * 60)
    print("Testing SMTP Connection")
    print("=" * 60)
    print(f"Host: {SMTP_HOST}")
    print(f"Port: {SMTP_PORT}")
    print(f"User: {SMTP_USER}")
    print(f"From: {FROM_EMAIL}")
    print(f"To: {TO_EMAIL}")
    print("=" * 60)

    try:
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = SUBJECT
        message['From'] = f'MyCrisisFamily <{FROM_EMAIL}>'
        message['To'] = TO_EMAIL

        # Create text and HTML versions
        text_content = """
Ciao!

Questo è un test del sistema email di MyCrisisFamily.

Se ricevi questa email, significa che la configurazione SMTP è corretta!

Dettagli:
- Server SMTP: smtp.zoho.com
- Account: no-reply@mycrisisfamily.com
- Protocollo: TLS (porta 587)

Saluti,
Il sistema MyCrisisFamily
        """.strip()

        html_content = """
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #239db0 0%, #2a5f82 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
        .success { color: #10B981; font-weight: bold; }
        .info-box { background: white; padding: 15px; border-left: 4px solid #239db0; margin: 20px 0; }
        .footer { text-align: center; margin-top: 20px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Test SMTP Riuscito!</h1>
        </div>
        <div class="content">
            <p>Ciao!</p>
            <p class="success">Questo è un test del sistema email di MyCrisisFamily.</p>
            <p>Se ricevi questa email, significa che la <strong>configurazione SMTP è corretta</strong>!</p>

            <div class="info-box">
                <h3>Dettagli Configurazione:</h3>
                <ul>
                    <li><strong>Server SMTP:</strong> smtp.zoho.com</li>
                    <li><strong>Account:</strong> no-reply@mycrisisfamily.com</li>
                    <li><strong>Protocollo:</strong> TLS (porta 587)</li>
                    <li><strong>Status:</strong> <span class="success">Funzionante</span></li>
                </ul>
            </div>

            <p>Il sistema è ora pronto per inviare:</p>
            <ul>
                <li>Email di benvenuto ai nuovi utenti</li>
                <li>Email di recupero password</li>
                <li>Notifiche di sistema</li>
            </ul>

            <div class="footer">
                <p>MyCrisisFamily - Sistema di Gestione Spese Familiari</p>
                <p>© 2025 MUMBLE.GROUP</p>
            </div>
        </div>
    </div>
</body>
</html>
        """.strip()

        # Attach parts
        part1 = MIMEText(text_content, 'plain', 'utf-8')
        part2 = MIMEText(html_content, 'html', 'utf-8')
        message.attach(part1)
        message.attach(part2)

        # Connect to server
        print("\n[1/4] Connessione al server SMTP...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)

        print("[2/4] Avvio TLS...")
        server.starttls()

        print("[3/4] Autenticazione...")
        server.login(SMTP_USER, SMTP_PASSWORD)

        print("[4/4] Invio email di test...")
        server.send_message(message)

        print("\n" + "=" * 60)
        print("✅ SUCCESS! Email inviata con successo!")
        print("=" * 60)
        print(f"\nControlla la casella: {TO_EMAIL}")
        print("(Controlla anche spam/posta indesiderata)")

        server.quit()
        return True

    except smtplib.SMTPAuthenticationError as e:
        print("\n" + "=" * 60)
        print("❌ ERRORE: Autenticazione fallita!")
        print("=" * 60)
        print(f"Dettagli: {e}")
        print("\nPossibili cause:")
        print("1. Email o password errate")
        print("2. Account non esistente")
        print("3. Account non configurato per SMTP")
        print("4. Autenticazione a due fattori attiva (serve app password)")
        return False

    except smtplib.SMTPConnectError as e:
        print("\n" + "=" * 60)
        print("❌ ERRORE: Connessione al server fallita!")
        print("=" * 60)
        print(f"Dettagli: {e}")
        print("\nPossibili cause:")
        print("1. Server SMTP non raggiungibile")
        print("2. Firewall bloccante")
        print("3. Porta 587 chiusa")
        return False

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERRORE GENERICO!")
        print("=" * 60)
        print(f"Tipo errore: {type(e).__name__}")
        print(f"Dettagli: {e}")
        return False

if __name__ == '__main__':
    success = test_smtp_connection()
    exit(0 if success else 1)
