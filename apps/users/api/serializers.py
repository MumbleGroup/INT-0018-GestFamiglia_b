from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from apps.users.models import UserProfile, Family, FamilyInvitation
from apps.users.services import EmailService

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer per il profilo utente"""
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'role', 'family_role', 'phone_number', 'birth_date',
            'profile_picture', 'bio', 'ui_preferences', 'is_master', 'can_plan_budget',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_master', 'can_plan_budget', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    """Serializer per il modello User con profilo e famiglia"""
    profile = UserProfileSerializer(read_only=True)
    family_name = serializers.CharField(source='family.name', read_only=True)
    family_detail = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'last_login', 'profile',
            'family', 'family_name', 'family_detail', 'preferred_language'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'family']

    def get_family_detail(self, obj):
        """Restituisce i dettagli della famiglia inclusi i membri"""
        if not obj.family:
            return None

        return {
            'id': obj.family.id,
            'name': obj.family.name,
            'members': [
                {
                    'id': member.id,
                    'name': f"{member.first_name} {member.last_name}".strip(),
                    'email': member.email,
                    'family_role': member.profile.family_role if hasattr(member, 'profile') else ''
                }
                for member in obj.family.members.all()
            ]
        }


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer per la creazione di nuovi utenti"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    # Campo per il codice invito (opzionale)
    invitation_code = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Codice invito per unirsi a una famiglia esistente"
    )

    # Campi del profilo
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, default='familiare')
    family_role = serializers.ChoiceField(choices=UserProfile.FAMILY_ROLE_CHOICES, default='altro')
    phone_number = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password2',
            'first_name', 'last_name', 'invitation_code',
            'role', 'family_role', 'phone_number', 'birth_date', 'bio'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "I campi password non corrispondono."
            })

        # Valida il codice invito se fornito
        if attrs.get('invitation_code'):
            try:
                # Verifica che il codice invito esista e sia valido
                FamilyInvitation.objects.get(token=attrs['invitation_code'], status='pending')
            except FamilyInvitation.DoesNotExist:
                raise serializers.ValidationError({
                    "invitation_code": "Codice invito non valido o già utilizzato."
                })

        return attrs
    
    def create(self, validated_data):
        # Estrae il codice invito se presente
        invitation_code = validated_data.pop('invitation_code', None)

        # Estrae i campi del profilo
        profile_data = {
            'role': validated_data.pop('role', 'familiare'),
            'family_role': validated_data.pop('family_role', 'altro'),
            'phone_number': validated_data.pop('phone_number', ''),
            'birth_date': validated_data.pop('birth_date', None),
            'bio': validated_data.pop('bio', ''),
        }

        validated_data.pop('password2')

        # Genera username dall'email se non fornito
        if 'username' not in validated_data:
            validated_data['username'] = validated_data['email']

        user = User.objects.create_user(**validated_data)

        # Gestisce l'invito se presente
        if invitation_code:
            try:
                invitation = FamilyInvitation.objects.get(token=invitation_code, status='pending')
                # Associa l'utente alla famiglia
                user.family = invitation.family
                user.save()

                # Marca l'invito come accettato
                invitation.status = 'accepted'
                invitation.accepted_at = timezone.now()
                invitation.save()

            except FamilyInvitation.DoesNotExist:
                # Questo non dovrebbe accadere perché è già stato validato
                pass

        # Aggiorna o crea il profilo (il profilo potrebbe essere già stato creato da un signal)
        profile, created = UserProfile.objects.get_or_create(user=user, defaults=profile_data)
        if not created:
            # Aggiorna il profilo esistente
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()

        # Invia email di benvenuto
        try:
            EmailService.send_welcome_email(user)
        except Exception as e:
            # Log dell'errore ma non blocca la registrazione
            print(f"⚠️ Failed to send welcome email: {e}")

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer per l'aggiornamento degli utenti"""
    
    # Campi del profilo
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False)
    family_role = serializers.ChoiceField(choices=UserProfile.FAMILY_ROLE_CHOICES, required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    ui_preferences = serializers.JSONField(required=False)
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'preferred_language',
            'role', 'family_role', 'phone_number', 'birth_date',
            'profile_picture', 'bio', 'ui_preferences'
        ]
    
    def update(self, instance, validated_data):
        # Estrae i campi del profilo
        profile_data = {}
        profile_fields = ['role', 'family_role', 'phone_number', 'birth_date', 'profile_picture', 'bio', 'ui_preferences']

        for field in profile_fields:
            if field in validated_data:
                profile_data[field] = validated_data.pop(field)

        # Aggiorna l'utente
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Aggiorna o crea il profilo
        if profile_data:
            profile, created = UserProfile.objects.get_or_create(user=instance)

            # Gestione speciale per ui_preferences - merge invece di sovrascrivere
            if 'ui_preferences' in profile_data:
                current_preferences = profile.ui_preferences or {}
                new_preferences = profile_data['ui_preferences'] or {}
                # Merge delle preferenze: mantieni quelle esistenti e aggiungi/aggiorna quelle nuove
                merged_preferences = {**current_preferences, **new_preferences}
                profile.ui_preferences = merged_preferences
                profile_data.pop('ui_preferences')  # Rimuovi dal loop standard

            # Aggiorna gli altri campi normalmente
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer per il cambio password"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        validators=[validate_password]
    )
    new_password2 = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "I campi password non corrispondono."
            })
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Password attuale non corretta.")
        return value


class MCFTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer JWT personalizzato che include i dati utente"""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Aggiungi dati personalizzati al token
        token['email'] = user.email
        token['name'] = user.get_full_name()
        
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)

        # Aggiungi dati utente alla risposta
        user = self.user
        data['user'] = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'name': user.get_full_name(),
            'preferred_language': user.preferred_language,
        }
        
        # Aggiungi dati del profilo se esiste
        try:
            profile = user.profile
            data['user']['userprofile'] = {
                'role': profile.role,
                'family_role': profile.family_role,
                'is_master': profile.is_master,
                'can_plan_budget': profile.can_plan_budget,
            }
        except UserProfile.DoesNotExist:
            data['user']['userprofile'] = None
        
        return data


class FamilySerializer(serializers.ModelSerializer):
    """Serializer per le famiglie"""
    members = UserSerializer(many=True, read_only=True)
    members_count = serializers.IntegerField(source='get_members_count', read_only=True)
    masters_count = serializers.IntegerField(source='get_masters_count', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Family
        fields = [
            'id', 'name', 'invite_code', 'created_by', 'created_by_name',
            'created_at', 'is_active', 'members', 'members_count', 'masters_count'
        ]
        read_only_fields = ['id', 'invite_code', 'created_by', 'created_at']


class FamilyCreateSerializer(serializers.ModelSerializer):
    """Serializer per creare famiglie"""

    class Meta:
        model = Family
        fields = ['name']

    def create(self, validated_data):
        user = self.context['request'].user

        # Verifica che l'utente non sia già in una famiglia
        if user.family:
            raise serializers.ValidationError(
                "Sei già membro di una famiglia. Non puoi crearne un'altra."
            )

        # Crea la famiglia
        family = Family.objects.create(
            name=validated_data['name'],
            created_by=user
        )

        # Aggiungi l'utente alla famiglia
        user.family = family
        user.save()

        # Crea o aggiorna il profilo come master
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.role = 'master'
        profile.save()

        return family


class FamilyInvitationSerializer(serializers.ModelSerializer):
    """Serializer per gli inviti famiglia"""
    family_name = serializers.CharField(source='family.name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.get_full_name', read_only=True)
    can_be_accepted = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    # Campi aggiuntivi per l'utente che ha fatto l'invito
    invited_by_first_name = serializers.CharField(source='invited_by.first_name', read_only=True)
    invited_by_last_name = serializers.CharField(source='invited_by.last_name', read_only=True)
    invited_by_email = serializers.CharField(source='invited_by.email', read_only=True)

    class Meta:
        model = FamilyInvitation
        fields = [
            'id', 'family', 'family_name', 'invited_by', 'invited_by_name',
            'invited_by_first_name', 'invited_by_last_name', 'invited_by_email',
            'email', 'family_role', 'token', 'status', 'created_at',
            'expires_at', 'can_be_accepted', 'is_expired'
        ]
        read_only_fields = [
            'id', 'family', 'invited_by', 'token', 'status',
            'created_at', 'expires_at'
        ]


class FamilyInvitationCreateSerializer(serializers.ModelSerializer):
    """Serializer per creare inviti famiglia"""

    class Meta:
        model = FamilyInvitation
        fields = ['email', 'family_role', 'token', 'expires_at']
        read_only_fields = ['token', 'expires_at']

    def validate_email(self, value):
        # Verifica che l'email non sia già registrata nella famiglia
        user = self.context['request'].user
        if not user.family:
            raise serializers.ValidationError("Devi essere membro di una famiglia per invitare utenti.")

        # Verifica se l'utente con questa email esiste ed è già nella famiglia
        try:
            existing_user = User.objects.get(email=value)
            if existing_user.family == user.family:
                raise serializers.ValidationError("Questo utente è già membro della tua famiglia.")
        except User.DoesNotExist:
            pass

        # Verifica se c'è già un invito pending per questa email
        if FamilyInvitation.objects.filter(
            family=user.family,
            email=value,
            status='pending'
        ).exists():
            raise serializers.ValidationError("C'è già un invito pending per questa email.")

        return value

    def create(self, validated_data):
        user = self.context['request'].user

        # Verifica che l'utente possa invitare (master)
        if not user.can_manage_family():
            raise serializers.ValidationError("Non hai i permessi per invitare utenti.")

        # Crea l'invito
        invitation = FamilyInvitation.objects.create(
            family=user.family,
            invited_by=user,
            **validated_data
        )

        # Invia email automaticamente
        try:
            from apps.users.services import InvitationEmailService
            email_sent = InvitationEmailService.send_invitation_email(invitation)
            if email_sent:
                print(f"✅ Email di invito inviata a {invitation.email}")
            else:
                print(f"❌ Errore nell'invio email a {invitation.email}")
        except Exception as e:
            print(f"❌ Errore nel servizio email: {e}")
            # Non blocchiamo la creazione dell'invito se l'email fallisce

        return invitation


class JoinFamilySerializer(serializers.Serializer):
    """Serializer per unirsi a una famiglia tramite codice invito"""
    invite_code = serializers.CharField(max_length=8)

    def validate_invite_code(self, value):
        try:
            family = Family.objects.get(invite_code=value.upper(), is_active=True)
        except Family.DoesNotExist:
            raise serializers.ValidationError("Codice invito non valido.")

        user = self.context['request'].user
        if user.family:
            raise serializers.ValidationError("Sei già membro di una famiglia.")

        return value

    def save(self):
        user = self.context['request'].user
        invite_code = self.validated_data['invite_code'].upper()

        family = Family.objects.get(invite_code=invite_code)
        user.family = family
        user.save()

        # Crea il profilo come familiare se non esiste
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            profile.role = 'familiare'
            profile.save()

        return family


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer per richiedere il reset della password"""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Verifica che l'email esista nel sistema"""
        try:
            user = User.objects.get(email=value, is_active=True)
            self.user = user
            return value
        except User.DoesNotExist:
            # Per sicurezza, non rivelare che l'email non esiste
            # Restituiamo sempre successo ma logghiamo l'errore
            return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer per confermare il reset della password con token"""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        validators=[validate_password]
    )
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "I campi password non corrispondono."
            })
        return attrs

    def validate_token(self, value):
        """Verifica che il token sia valido e non scaduto"""
        try:
            from apps.users.models import PasswordResetToken
            token = PasswordResetToken.objects.get(token=value)

            if not token.can_be_used():
                if token.is_expired():
                    raise serializers.ValidationError("Il token è scaduto.")
                elif token.is_used():
                    raise serializers.ValidationError("Il token è già stato utilizzato.")

            self.reset_token = token
            return value
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Token non valido.")

    def save(self):
        """Cambia la password e marca il token come utilizzato"""
        user = self.reset_token.user
        user.set_password(self.validated_data['new_password'])
        user.save()

        # Marca il token come utilizzato
        self.reset_token.mark_as_used()

        return user