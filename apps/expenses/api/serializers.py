from rest_framework import serializers
from apps.expenses.models import Expense, RecurringExpense, ExpenseAttachment, ExpenseQuota, Budget
from apps.reports.models import SpendingPlan
from apps.categories.api.serializers import CategorySerializer, SubcategorySerializer
from apps.users.api.serializers import UserSerializer


class ExpenseQuotaSerializer(serializers.ModelSerializer):
    """Serializer per le quote di pagamento"""
    is_overdue = serializers.ReadOnlyField()
    days_until_due = serializers.SerializerMethodField()
    
    # Informazioni dalla spesa collegata
    expense_description = serializers.CharField(source='expense.description', read_only=True)
    expense_category = serializers.CharField(source='expense.category.name', read_only=True)
    expense_category_id = serializers.IntegerField(source='expense.category.id', read_only=True)
    expense_subcategory = serializers.CharField(source='expense.subcategory.name', read_only=True)
    expense_subcategory_id = serializers.IntegerField(source='expense.subcategory.id', read_only=True)
    expense_user = serializers.CharField(source='expense.user.username', read_only=True)
    
    class Meta:
        model = ExpenseQuota
        fields = [
            'id', 'expense', 'quota_number', 'amount', 'due_date', 'paid_date',
            'is_paid', 'payment_method', 'notes', 'is_overdue',
            'days_until_due', 'expense_description', 'expense_category',
            'expense_category_id', 'expense_subcategory', 'expense_subcategory_id',
            'expense_user', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'expense_description',
            'expense_category', 'expense_category_id', 'expense_subcategory',
            'expense_subcategory_id', 'expense_user'
        ]
    
    def get_days_until_due(self, obj):
        """Restituisce i giorni alla scadenza"""
        return obj.days_until_due()


class ExpenseQuotaCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer per creare/aggiornare quote"""
    
    class Meta:
        model = ExpenseQuota
        fields = [
            'quota_number', 'amount', 'due_date', 'is_paid',
            'paid_date', 'payment_method', 'notes'
        ]
    
    def validate(self, attrs):
        """Valida la quota"""
        quota_number = attrs.get('quota_number')
        amount = attrs.get('amount')
        
        # Verifica che il numero quota sia positivo
        if quota_number and quota_number <= 0:
            raise serializers.ValidationError({
                "quota_number": "Il numero quota deve essere positivo."
            })
        
        # Verifica che l'importo sia positivo
        if amount and amount <= 0:
            raise serializers.ValidationError({
                "amount": "L'importo deve essere positivo."
            })
        
        return attrs


class ExpenseAttachmentSerializer(serializers.ModelSerializer):
    """Serializer per gli allegati delle spese"""
    
    class Meta:
        model = ExpenseAttachment
        fields = ['id', 'file', 'description', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer per le spese"""
    user = UserSerializer(read_only=True)
    category_detail = CategorySerializer(source='category', read_only=True)
    subcategory_detail = SubcategorySerializer(source='subcategory', read_only=True)
    shared_with_details = UserSerializer(source='shared_with', many=True, read_only=True)
    attachments = ExpenseAttachmentSerializer(many=True, read_only=True)
    quote = ExpenseQuotaSerializer(many=True, read_only=True)
    budget_detail = serializers.SerializerMethodField()
    spending_plan = serializers.IntegerField(source='spending_plan.id', read_only=True)
    split_amount = serializers.SerializerMethodField()

    # Campi per gestione quote
    has_quote = serializers.SerializerMethodField()
    total_paid_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    payment_progress_percentage = serializers.SerializerMethodField()
    paid_quote_count = serializers.SerializerMethodField()
    total_quote_count = serializers.SerializerMethodField()
    next_due_quota = serializers.SerializerMethodField()
    my_share = serializers.SerializerMethodField()
    other_share = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            'id', 'user', 'category', 'category_detail', 'subcategory',
            'subcategory_detail', 'amount', 'description', 'notes', 'date',
            'payment_method', 'payment_source', 'payment_type', 'my_share_amount', 'paid_by_user', 'status', 'receipt', 'shared_with',
            'shared_with_details', 'is_recurring', 'is_personal', 'budget', 'budget_detail',
            'spending_plan', 'attachments', 'quote', 'split_amount', 'has_quote', 'total_paid_amount',
            'remaining_amount', 'payment_progress_percentage', 'paid_quote_count',
            'total_quote_count', 'next_due_quota', 'my_share', 'other_share', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'updated_at', 'spending_plan', 'split_amount',
            'has_quote', 'total_paid_amount', 'remaining_amount',
            'payment_progress_percentage', 'paid_quote_count', 'total_quote_count',
            'next_due_quota', 'my_share', 'other_share'
        ]
    
    def get_split_amount(self, obj):
        """Restituisce l'importo diviso tra gli utenti"""
        return str(obj.get_split_amount())
    
    def get_has_quote(self, obj):
        """Verifica se ha quote"""
        return obj.has_quote()
    
    def get_total_paid_amount(self, obj):
        """Importo totale pagato"""
        return str(obj.get_total_paid_amount())
    
    def get_remaining_amount(self, obj):
        """Importo rimanente"""
        return str(obj.get_remaining_amount())
    
    def get_payment_progress_percentage(self, obj):
        """Percentuale di completamento"""
        return obj.get_payment_progress_percentage()
    
    def get_paid_quote_count(self, obj):
        """Numero quote pagate"""
        return obj.get_paid_quote_count()
    
    def get_total_quote_count(self, obj):
        """Numero totale quote"""
        return obj.get_total_quote_count()
    
    def get_next_due_quota(self, obj):
        """Prossima quota in scadenza"""
        next_quota = obj.get_next_due_quota()
        if next_quota:
            return ExpenseQuotaSerializer(next_quota).data
        return None
    
    def get_budget_detail(self, obj):
        """Dettagli del budget associato"""
        if obj.budget:
            return BudgetSerializer(obj.budget).data
        return None

    def get_my_share(self, obj):
        """Calcola la quota da pagare"""
        return str(obj.get_my_share())

    def get_other_share(self, obj):
        """Calcola la quota dell'altra persona"""
        return str(obj.get_other_share())


class ExpenseCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer per creare/aggiornare spese"""
    shared_with = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=UserSerializer.Meta.model.objects.all(),
        required=False,
        allow_null=True
    )
    spending_plan = serializers.PrimaryKeyRelatedField(
        queryset=SpendingPlan.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Expense
        fields = [
            'category', 'subcategory', 'amount', 'description', 'notes',
            'date', 'payment_method', 'payment_source', 'payment_type', 'my_share_amount', 'paid_by_user', 'status', 'receipt', 'shared_with',
            'is_recurring', 'is_personal', 'budget', 'spending_plan'
        ]

    def to_internal_value(self, data):
        """Converte null in lista vuota per shared_with"""
        if 'shared_with' in data and data['shared_with'] is None:
            data['shared_with'] = []
        return super().to_internal_value(data)
    
    def validate(self, attrs):
        """Valida che la sottocategoria appartenga alla categoria"""
        category = attrs.get('category')
        subcategory = attrs.get('subcategory')
        
        if subcategory and category:
            if subcategory.category != category:
                raise serializers.ValidationError({
                    "subcategory": "La sottocategoria deve appartenere alla categoria selezionata."
                })
        
        return attrs
    
    def create(self, validated_data):
        """Crea una nuova spesa"""
        shared_with = validated_data.pop('shared_with', [])
        if shared_with is None:
            shared_with = []
        expense = Expense.objects.create(**validated_data)
        expense.shared_with.set(shared_with)
        return expense
    
    def update(self, instance, validated_data):
        """Aggiorna una spesa esistente"""
        shared_with = validated_data.pop('shared_with', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if shared_with is not None:
            instance.shared_with.set(shared_with)

        return instance


class RecurringExpenseSerializer(serializers.ModelSerializer):
    """Serializer per le spese ricorrenti"""
    user = UserSerializer(read_only=True)
    category_detail = CategorySerializer(source='category', read_only=True)
    subcategory_detail = SubcategorySerializer(source='subcategory', read_only=True)
    shared_with_details = UserSerializer(source='shared_with', many=True, read_only=True)
    
    class Meta:
        model = RecurringExpense
        fields = [
            'id', 'user', 'category', 'category_detail', 'subcategory',
            'subcategory_detail', 'amount', 'description', 'frequency',
            'start_date', 'end_date', 'payment_method', 'shared_with',
            'shared_with_details', 'is_active', 'last_generated',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'last_generated', 'created_at', 'updated_at']


class RecurringExpenseCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer per creare/aggiornare spese ricorrenti"""
    shared_with = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=UserSerializer.Meta.model.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = RecurringExpense
        fields = [
            'category', 'subcategory', 'amount', 'description', 'frequency',
            'start_date', 'end_date', 'payment_method', 'shared_with', 'is_active'
        ]

    def to_internal_value(self, data):
        """Converte null in lista vuota per shared_with"""
        if 'shared_with' in data and data['shared_with'] is None:
            data['shared_with'] = []
        return super().to_internal_value(data)
    
    def validate(self, attrs):
        """Valida le date e la sottocategoria"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "La data di fine deve essere successiva alla data di inizio."
            })
        
        category = attrs.get('category')
        subcategory = attrs.get('subcategory')
        
        if subcategory and category:
            if subcategory.category != category:
                raise serializers.ValidationError({
                    "subcategory": "La sottocategoria deve appartenere alla categoria selezionata."
                })
        
        return attrs
    
    def create(self, validated_data):
        """Crea una nuova spesa ricorrente"""
        shared_with = validated_data.pop('shared_with', [])
        if shared_with is None:
            shared_with = []
        recurring_expense = RecurringExpense.objects.create(**validated_data)
        recurring_expense.shared_with.set(shared_with)
        return recurring_expense
    
    def update(self, instance, validated_data):
        """Aggiorna una spesa ricorrente esistente"""
        shared_with = validated_data.pop('shared_with', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if shared_with is not None:
            instance.shared_with.set(shared_with)

        return instance


class BudgetSerializer(serializers.ModelSerializer):
    """Serializer per i budget"""
    created_by = UserSerializer(read_only=True)
    total_planned_amount = serializers.SerializerMethodField()
    total_spent_amount = serializers.SerializerMethodField()
    remaining_budget = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    planning_percentage = serializers.SerializerMethodField()
    planned_expenses_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Budget
        fields = [
            'id', 'name', 'description', 'budget_type', 'event_type',
            'year', 'month', 'start_date', 'end_date', 'total_budget',
            'created_by', 'is_active', 'created_at', 'updated_at',
            'total_planned_amount', 'total_spent_amount', 'remaining_budget',
            'progress_percentage', 'planning_percentage', 'planned_expenses_count'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at',
            'total_planned_amount', 'total_spent_amount', 'remaining_budget',
            'progress_percentage', 'planning_percentage', 'planned_expenses_count'
        ]
    
    def get_total_planned_amount(self, obj):
        return str(obj.get_total_planned_amount())
    
    def get_total_spent_amount(self, obj):
        return str(obj.get_total_spent_amount())
    
    def get_remaining_budget(self, obj):
        return str(obj.get_remaining_budget())
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()
    
    def get_planning_percentage(self, obj):
        return obj.get_planning_percentage()
    
    def get_planned_expenses_count(self, obj):
        return obj.planned_expenses.count()


class ConvertToRecurringSerializer(serializers.Serializer):
    """Serializer per convertire una spesa in ricorrente"""
    frequency = serializers.ChoiceField(
        choices=RecurringExpense.FREQUENCY_CHOICES,
        help_text="Frequenza della ricorrenza"
    )
    start_date = serializers.DateField(
        help_text="Data di inizio della ricorrenza"
    )
    end_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Data di fine della ricorrenza (opzionale)"
    )
    generate_immediately = serializers.BooleanField(
        default=True,
        help_text="Se generare immediatamente le spese future"
    )

    def validate(self, attrs):
        """Valida le date"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')

        if end_date and start_date and end_date <= start_date:
            raise serializers.ValidationError({
                "end_date": "La data di fine deve essere successiva alla data di inizio."
            })

        return attrs


class BudgetCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer per creare/aggiornare budget"""

    class Meta:
        model = Budget
        fields = [
            'name', 'description', 'budget_type', 'event_type',
            'year', 'month', 'start_date', 'end_date', 'total_budget', 'is_active'
        ]

    def validate(self, attrs):
        budget_type = attrs.get('budget_type')

        if budget_type == 'mensile':
            # Per budget mensili, year e month sono obbligatori
            if not attrs.get('year') or not attrs.get('month'):
                raise serializers.ValidationError({
                    "year": "Anno e mese sono obbligatori per i budget mensili.",
                    "month": "Anno e mese sono obbligatori per i budget mensili."
                })
            # Pulisce i campi degli eventi
            attrs['event_type'] = None
            attrs['start_date'] = None
            attrs['end_date'] = None

        elif budget_type == 'evento':
            # Per eventi, event_type e start_date sono obbligatori
            if not attrs.get('event_type'):
                raise serializers.ValidationError({
                    "event_type": "Il tipo evento è obbligatorio per i budget evento."
                })
            if not attrs.get('start_date'):
                raise serializers.ValidationError({
                    "start_date": "La data di inizio è obbligatoria per i budget evento."
                })
            # Verifica che end_date sia dopo start_date
            if attrs.get('end_date') and attrs.get('start_date'):
                if attrs['end_date'] < attrs['start_date']:
                    raise serializers.ValidationError({
                        "end_date": "La data di fine deve essere successiva alla data di inizio."
                    })
            # Pulisce i campi mensili
            attrs['year'] = None
            attrs['month'] = None

        return attrs

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return Budget.objects.create(**validated_data)