from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid


class Family(models.Model):
    """
    Modello per rappresentare una famiglia/gruppo che condivide le spese
    """
    name = models.CharField(
        max_length=100,
        verbose_name="Nome Famiglia"
    )
    created_by = models.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        related_name='created_families',
        verbose_name="Creata da",
        null=True  # Temporaneo per migrazione
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Codice invito univoco per aggiungere membri
    invite_code = models.CharField(
        max_length=8,
        unique=True,
        verbose_name="Codice Invito"
    )

    class Meta:
        verbose_name = "Famiglia"
        verbose_name_plural = "Famiglie"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = self.generate_invite_code()
        super().save(*args, **kwargs)

    def generate_invite_code(self):
        """Genera un codice di invito univoco di 8 caratteri"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Family.objects.filter(invite_code=code).exists():
                return code

    def get_members_count(self):
        """Restituisce il numero di membri della famiglia"""
        return self.members.count()

    def get_masters_count(self):
        """Restituisce il numero di master della famiglia"""
        return self.members.filter(profile__role='master').count()


class UserManager(BaseUserManager):
    """Manager personalizzato per User con login via email"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('L\'indirizzo email è obbligatorio')
        email = self.normalize_email(email)
        
        # Se username non è fornito, usa la parte locale dell'email
        if 'username' not in extra_fields:
            extra_fields['username'] = email.split('@')[0]
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Il superuser deve avere is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Il superuser deve avere is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Modello utente personalizzato per la gestione degli utenti famigliari
    Login via email invece che username
    """
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    objects = UserManager()

    email = models.EmailField(unique=True, verbose_name="Email")

    # Relazione con la famiglia
    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name='members',
        null=True,
        blank=True,
        verbose_name="Famiglia"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Preferenze utente
    preferred_language = models.CharField(
        max_length=10,
        choices=[
            ('it-IT', 'Italiano'),
            ('en-US', 'English'),
        ],
        default='it-IT',
        verbose_name="Lingua Preferita",
        help_text="Lingua preferita dall'utente per l'interfaccia"
    )

    # === ENCRYPTION FIELDS ===
    encrypted_profile = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Profilo Crittografato",
        help_text="Dati personali sensibili crittografati (email, nome, telefono, etc.)"
    )
    encryption_version = models.IntegerField(
        default=1,
        verbose_name="Versione Crittografia",
        help_text="Versione dell'algoritmo di crittografia utilizzato"
    )

    class Meta:
        verbose_name = "Utente"
        verbose_name_plural = "Utenti"
        ordering = ['email']
    
    def __str__(self):
        return f"{self.get_full_name() or self.email}"

    def is_family_master(self):
        """Verifica se l'utente è un master della famiglia"""
        return hasattr(self, 'profile') and self.profile.role == 'master'

    def can_manage_family(self):
        """Verifica se l'utente può gestire la famiglia (invitare, rimuovere membri)"""
        return self.is_family_master()

    def get_family_members(self):
        """Restituisce tutti i membri della stessa famiglia"""
        if self.family:
            return self.family.members.filter(is_active=True)
        return User.objects.none()

    def create_family(self, family_name):
        """Crea una nuova famiglia e rende questo utente il creatore"""
        if self.family is not None:
            raise ValueError("L'utente è già membro di una famiglia")

        family = Family.objects.create(
            name=family_name,
            created_by=self
        )
        self.family = family
        self.save()

        # Crea il profilo come master se non esiste
        if hasattr(self, 'profile'):
            self.profile.role = 'master'
            self.profile.save()

        return family

    # === ENCRYPTION METHODS ===
    def encrypt_profile_data(self, family_password: str) -> bool:
        """
        Crittografa i dati sensibili dell'utente

        Args:
            family_password: Password della famiglia per derivare la chiave

        Returns:
            bool: True se la crittografia è riuscita
        """
        from .crypto import encrypt_user_data
        return encrypt_user_data(self, family_password)

    def decrypt_profile_data(self, family_password: str) -> dict:
        """
        Decrittografa i dati sensibili dell'utente

        Args:
            family_password: Password della famiglia per derivare la chiave

        Returns:
            dict: Dati decrittografati
        """
        from .crypto import decrypt_user_data
        return decrypt_user_data(self, family_password)

    @property
    def is_profile_encrypted(self) -> bool:
        """Verifica se il profilo utente è crittografato"""
        return bool(self.encrypted_profile and self.encrypted_profile.get('data'))

    @property
    def safe_email(self):
        """
        Ritorna l'email sicura (decrittografata se disponibile, altrimenti fallback)
        NOTA: Questa property richiede il context della famiglia per decrittografare
        """
        if self.is_profile_encrypted:
            # Se è crittografato, non possiamo decrittografarlo senza la password
            # Ritorna una versione offuscata
            if self.email:
                local, domain = self.email.split('@')
                return f"{local[:2]}***@{domain}"
            return "***@***.***"
        return self.email

    @property
    def safe_display_name(self):
        """Ritorna un nome visualizzabile sicuro"""
        if self.is_profile_encrypted:
            # Se crittografato, usa username o email offuscata
            return self.username or self.safe_email
        return self.get_full_name() or self.email


class UserProfile(models.Model):
    """
    Profilo utente con informazioni aggiuntive
    """
    ROLE_CHOICES = [
        ('master', 'Master (Genitore)'),
        ('familiare', 'Familiare'),
    ]
    
    FAMILY_ROLE_CHOICES = [
        ('padre', 'Padre'),
        ('madre', 'Madre'),
        ('figlio', 'Figlio/a'),
        ('altro', 'Altro'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Utente"
    )
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='familiare',
        verbose_name="Ruolo sistema",
        help_text="Master può pianificare spese, Familiare può solo inserire spese"
    )
    family_role = models.CharField(
        max_length=20, 
        choices=FAMILY_ROLE_CHOICES, 
        default='altro',
        verbose_name="Ruolo in famiglia"
    )
    phone_number = models.CharField(
        max_length=20, 
        blank=True,
        verbose_name="Numero di telefono"
    )
    birth_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Data di nascita"
    )
    profile_picture = models.ImageField(
        upload_to='profile_pics/', 
        blank=True, 
        null=True,
        verbose_name="Foto profilo"
    )
    bio = models.TextField(
        blank=True,
        verbose_name="Biografia",
        help_text="Breve descrizione"
    )

    # Preferenze UI personalizzate
    ui_preferences = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Preferenze UI",
        help_text="Impostazioni personalizzate dell'interfaccia (font, colori, etc.)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Profilo Utente"
        verbose_name_plural = "Profili Utenti"
        ordering = ['role', 'family_role']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - {self.get_role_display()}"
    
    @property
    def is_master(self):
        """Verifica se l'utente è un master"""
        return self.role == 'master'
    
    @property
    def can_plan_budget(self):
        """Verifica se può pianificare budget"""
        return self.is_master


class FamilyInvitation(models.Model):
    """
    Modello per gestire gli inviti alla famiglia
    """
    STATUS_CHOICES = [
        ('pending', 'In Attesa'),
        ('accepted', 'Accettato'),
        ('declined', 'Rifiutato'),
        ('expired', 'Scaduto'),
    ]

    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name="Famiglia"
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        verbose_name="Invitato da"
    )
    email = models.EmailField(verbose_name="Email Invitato")
    family_role = models.CharField(
        max_length=20,
        choices=UserProfile.ROLE_CHOICES,
        default='familiare',
        verbose_name="Ruolo Proposto"
    )

    # Token univoco per l'invito
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name="Token Invito"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Stato"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="Scade il")
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Invito Famiglia"
        verbose_name_plural = "Inviti Famiglia"
        unique_together = ['family', 'email', 'status']  # Un solo invito pending per email per famiglia

    def __str__(self):
        return f"Invito {self.email} → {self.family.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Invito valido per 7 giorni
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Verifica se l'invito è scaduto"""
        return timezone.now() > self.expires_at

    def can_be_accepted(self):
        """Verifica se l'invito può essere accettato"""
        return self.status == 'pending' and not self.is_expired()


class PasswordResetToken(models.Model):
    """
    Modello per gestire i token di reset password
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        verbose_name="Utente"
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="Token"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        verbose_name="Scade il"
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Utilizzato il"
    )

    class Meta:
        verbose_name = "Token Reset Password"
        verbose_name_plural = "Token Reset Password"
        ordering = ['-created_at']

    def __str__(self):
        return f"Reset token per {self.user.email} - {self.token[:8]}..."

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(48)

        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=24)

        super().save(*args, **kwargs)

    def is_expired(self):
        """Verifica se il token è scaduto"""
        return timezone.now() > self.expires_at

    def is_used(self):
        """Verifica se il token è già stato utilizzato"""
        return self.used_at is not None

    def can_be_used(self):
        """Verifica se il token può essere utilizzato"""
        return not self.is_expired() and not self.is_used()

    def mark_as_used(self):
        """Marca il token come utilizzato"""
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])
