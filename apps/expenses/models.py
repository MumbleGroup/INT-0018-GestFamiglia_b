from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.categories.models import Category, Subcategory


class Expense(models.Model):
    """
    Modello principale per le spese famigliari
    """
    PAYMENT_METHOD_CHOICES = [
        ('contanti', 'Contanti'),
        ('carta_credito', 'Carta di Credito'),
        ('carta_debito', 'Carta di Debito'),
        ('bonifico', 'Bonifico'),
        ('assegno', 'Assegno'),
        ('paypal', 'PayPal'),
        ('contributo', 'Da Contributo Famiglia'),
        ('altro', 'Altro'),
    ]

    PAYMENT_SOURCE_CHOICES = [
        ('personal', 'Fondi Personali'),
        ('contribution', 'Da Contributo Famiglia'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('shared', 'Condivisa'),
        ('partial', 'Parziale'),
        ('individual', 'Individuale'),
    ]

    STATUS_CHOICES = [
        ('pianificata', 'Pianificata'),
        ('da_pagare', 'Da Pagare'),
        ('parzialmente_pagata', 'Parzialmente Pagata'),
        ('pagata', 'Pagata'),
        ('ricorrente', 'Ricorrente'),
        ('annullata', 'Annullata'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='expenses',
        verbose_name="Utente"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='expenses',
        verbose_name="Categoria"
    )
    subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name="Sottocategoria"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Importo"
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Descrizione"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Note aggiuntive"
    )
    date = models.DateField(
        verbose_name="Data della spesa"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='contanti',
        verbose_name="Metodo di pagamento"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pagata',
        verbose_name="Stato"
    )
    receipt = models.FileField(
        upload_to='receipts/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Ricevuta/Scontrino"
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='shared_expenses',
        verbose_name="Condivisa con"
    )
    is_recurring = models.BooleanField(
        default=False,
        verbose_name="Spesa ricorrente"
    )
    is_personal = models.BooleanField(
        default=False,
        verbose_name="Spesa personale",
        help_text="Se True, la spesa è visibile solo al creatore e non condivisa con la famiglia"
    )
    budget = models.ForeignKey(
        'Budget',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planned_expenses',
        verbose_name="Budget di appartenenza",
        help_text="Budget mensile o evento a cui appartiene questa spesa"
    )
    planned_expense = models.ForeignKey(
        'reports.PlannedExpense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actual_payments',
        verbose_name="Spesa Pianificata",
        help_text="Spesa pianificata a cui questo pagamento contribuisce"
    )
    spending_plan = models.ForeignKey(
        'reports.SpendingPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actual_expenses',
        verbose_name="Piano di Spesa",
        help_text="Piano di spesa a cui appartiene questa spesa"
    )
    payment_source = models.CharField(
        max_length=20,
        choices=PAYMENT_SOURCE_CHOICES,
        default='personal',
        verbose_name="Fonte del Pagamento",
        help_text="Indica se il pagamento viene da fondi personali o dal contributo famiglia"
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='shared',
        verbose_name="Tipo Pagamento",
        help_text="Indica se la spesa è condivisa, parziale o individuale"
    )
    my_share_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Mia Quota",
        help_text="Importo effettivamente pagato da me (solo per spese parziali)"
    )
    paid_by_user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='individual_expenses_paid',
        verbose_name="Pagata da",
        help_text="Utente che paga la spesa (solo per spese individuali)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Spesa"
        verbose_name_plural = "Spese"
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['user', '-date']),
            models.Index(fields=['category', '-date']),
        ]
    
    def __str__(self):
        return f"{self.description} - €{self.amount} ({self.date})"
    
    def get_split_amount(self):
        """Calcola l'importo diviso tra gli utenti condivisi"""
        shared_count = self.shared_with.count()
        if shared_count > 0:
            return self.amount / (shared_count + 1)  # +1 per includere il creatore
        return self.amount
    
    def has_quote(self):
        """Verifica se la spesa è divisa in quote"""
        return self.quote.exists()
    
    def get_total_paid_amount(self):
        """Calcola l'importo totale già pagato tramite quote"""
        return self.quote.filter(is_paid=True).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    def get_remaining_amount(self):
        """Calcola l'importo rimanente da pagare"""
        if self.has_quote():
            return self.amount - self.get_total_paid_amount()
        return self.amount if self.status != 'pagata' else Decimal('0.00')
    
    def get_paid_quote_count(self):
        """Restituisce il numero di quote pagate"""
        return self.quote.filter(is_paid=True).count()
    
    def get_total_quote_count(self):
        """Restituisce il numero totale di quote"""
        return self.quote.count()
    
    def get_payment_progress_percentage(self):
        """Calcola la percentuale di completamento dei pagamenti"""
        if not self.has_quote():
            return 100.0 if self.status == 'pagata' else 0.0

        total_amount = self.amount
        paid_amount = self.get_total_paid_amount()

        if total_amount > 0:
            return float((paid_amount / total_amount) * 100)
        return 0.0

    def get_contributions_used(self):
        """Restituisce i contributi utilizzati per questa spesa"""
        from apps.contributions.models import ExpenseContribution
        return ExpenseContribution.objects.filter(expense=self)

    def get_total_contribution_amount(self):
        """Calcola il totale prelevato dai contributi per questa spesa"""
        from django.db.models import Sum
        total = self.expense_contributions.aggregate(
            total=Sum('amount_used')
        )['total'] or Decimal('0.00')
        return total

    def is_paid_with_contribution(self):
        """Verifica se la spesa è pagata con contributi famiglia"""
        return self.payment_source == 'contribution' or self.payment_method == 'contributo'
    
    def get_next_due_quota(self):
        """Restituisce la prossima quota in scadenza"""
        from django.utils import timezone
        return self.quote.filter(
            is_paid=False,
            due_date__gte=timezone.now().date()
        ).order_by('due_date').first()
    
    def get_overdue_quote(self):
        """Restituisce le quote scadute"""
        from django.utils import timezone
        return self.quote.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).order_by('due_date')

    def get_my_share(self):
        """Calcola la quota da pagare in base al payment_type"""
        if self.payment_type == 'individual':
            # Spesa individuale: pago tutto
            return self.amount
        elif self.payment_type == 'partial':
            # Spesa parziale: uso my_share_amount se valorizzato, altrimenti metà
            if self.my_share_amount is not None:
                return self.my_share_amount
            return self.amount / 2
        else:
            # Spesa condivisa: nessuna quota specifica
            return Decimal('0.00')

    def get_other_share(self):
        """Calcola la quota dell'altra persona"""
        if self.payment_type == 'partial':
            my_share = self.get_my_share()
            return self.amount - my_share
        return Decimal('0.00')


class RecurringExpense(models.Model):
    """
    Modello per gestire le spese ricorrenti
    """
    FREQUENCY_CHOICES = [
        ('giornaliera', 'Giornaliera'),
        ('settimanale', 'Settimanale'),
        ('bisettimanale', 'Bisettimanale'),
        ('mensile', 'Mensile'),
        ('bimestrale', 'Bimestrale'),
        ('trimestrale', 'Trimestrale'),
        ('semestrale', 'Semestrale'),
        ('annuale', 'Annuale'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recurring_expenses',
        verbose_name="Utente"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Categoria"
    )
    subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sottocategoria"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Importo"
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Descrizione"
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='mensile',
        verbose_name="Frequenza"
    )
    start_date = models.DateField(
        verbose_name="Data di inizio"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data di fine"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=Expense.PAYMENT_METHOD_CHOICES,
        default='bonifico',
        verbose_name="Metodo di pagamento"
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='shared_recurring_expenses',
        verbose_name="Condivisa con"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Attiva"
    )
    last_generated = models.DateField(
        null=True,
        blank=True,
        verbose_name="Ultima generazione"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Spesa Ricorrente"
        verbose_name_plural = "Spese Ricorrenti"
        ordering = ['frequency', 'description']
    
    def __str__(self):
        return f"{self.description} - €{self.amount} ({self.get_frequency_display()})"


class ExpenseAttachment(models.Model):
    """
    Modello per gestire allegati multipli per ogni spesa
    """
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name="Spesa"
    )
    file = models.FileField(
        upload_to='expense_attachments/%Y/%m/',
        verbose_name="File"
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Descrizione"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Allegato Spesa"
        verbose_name_plural = "Allegati Spese"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Allegato per {self.expense.description}"


class ExpenseQuota(models.Model):
    """
    Modello per gestire i pagamenti a quote delle spese
    """
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='quote',
        verbose_name="Spesa"
    )
    quota_number = models.PositiveIntegerField(
        verbose_name="Numero quota",
        help_text="Numero progressivo della quota (1, 2, 3...)"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Importo quota"
    )
    due_date = models.DateField(
        verbose_name="Data scadenza",
        help_text="Data entro cui deve essere pagata questa quota"
    )
    paid_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data pagamento",
        help_text="Data in cui è stata effettivamente pagata"
    )
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Pagata"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=Expense.PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True,
        verbose_name="Metodo di pagamento",
        help_text="Metodo usato per pagare questa quota specifica"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Note",
        help_text="Note specifiche per questa quota"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Quota Spesa"
        verbose_name_plural = "Quote Spese"
        ordering = ['expense', 'quota_number']
        unique_together = ['expense', 'quota_number']
        indexes = [
            models.Index(fields=['expense', 'quota_number']),
            models.Index(fields=['due_date']),
            models.Index(fields=['is_paid']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_paid else "○"
        return f"{status} Quota {self.quota_number}/{self.expense.quote.count()} - €{self.amount} ({self.expense.description})"
    
    def save(self, *args, **kwargs):
        # Se viene impostata come pagata, imposta automaticamente la data di pagamento
        if self.is_paid and not self.paid_date:
            from django.utils import timezone
            self.paid_date = timezone.now().date()
        # Se viene rimossa come pagata, rimuovi la data di pagamento
        elif not self.is_paid:
            self.paid_date = None
        
        super().save(*args, **kwargs)
        
        # Aggiorna lo stato della spesa principale
        self._update_expense_status()
    
    def _update_expense_status(self):
        """Aggiorna lo stato della spesa in base alle quote pagate"""
        expense = self.expense
        total_quote = expense.quote.count()
        paid_quote = expense.quote.filter(is_paid=True).count()
        
        if paid_quote == 0:
            expense.status = 'da_pagare'
        elif paid_quote == total_quote:
            expense.status = 'pagata'
        else:
            # Stato intermedio per pagamenti parziali
            if not hasattr(expense, '_original_status'):
                expense.status = 'parzialmente_pagata'
        
        expense.save(update_fields=['status'])
    
    @property
    def is_overdue(self):
        """Verifica se la quota è in ritardo"""
        if self.is_paid or not self.due_date:
            return False
        from django.utils import timezone
        return self.due_date < timezone.now().date()
    
    def days_until_due(self):
        """Restituisce i giorni rimanenti alla scadenza"""
        if self.is_paid or not self.due_date:
            return None
        from django.utils import timezone
        delta = self.due_date - timezone.now().date()
        return delta.days


class Budget(models.Model):
    """
    Modello per gestire budget di spesa (mensili o per eventi specifici)
    """
    BUDGET_TYPE_CHOICES = [
        ('mensile', 'Budget Mensile'),
        ('evento', 'Evento Specifico'),
    ]
    
    EVENT_TYPE_CHOICES = [
        ('vacanze', 'Vacanze'),
        ('matrimonio', 'Matrimonio'),
        ('ristrutturazione', 'Ristrutturazione'),
        ('auto', 'Acquisto Auto'),
        ('casa', 'Acquisto Casa'),
        ('compleanno', 'Festa Compleanno'),
        ('natale', 'Regali Natale'),
        ('scuola', 'Spese Scolastiche'),
        ('medico', 'Spese Mediche'),
        ('altro', 'Altro Evento'),
    ]
    
    name = models.CharField(
        max_length=255,
        verbose_name="Nome Budget",
        help_text="Es: 'Budget Gennaio 2024' o 'Vacanze Sicilia 2024'"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descrizione",
        help_text="Dettagli aggiuntivi sul budget"
    )
    budget_type = models.CharField(
        max_length=20,
        choices=BUDGET_TYPE_CHOICES,
        default='mensile',
        verbose_name="Tipo Budget"
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        blank=True,
        null=True,
        verbose_name="Tipo Evento",
        help_text="Solo se tipo budget è 'evento'"
    )
    
    # Per budget mensili
    year = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Anno",
        help_text="Per budget mensili"
    )
    month = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, i) for i in range(1, 13)],
        verbose_name="Mese",
        help_text="Per budget mensili"
    )
    
    # Per eventi specifici
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Inizio",
        help_text="Per eventi specifici"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Fine",
        help_text="Per eventi specifici"
    )
    
    total_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Budget Totale"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_budgets',
        verbose_name="Creato da"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Attivo"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Budget"
        verbose_name_plural = "Budget"
        ordering = ['-created_at']
        unique_together = [
            ['budget_type', 'year', 'month'],  # Un solo budget mensile per mese
        ]
    
    def __str__(self):
        if self.budget_type == 'mensile':
            return f"Budget {self.month}/{self.year} - €{self.total_budget}"
        else:
            return f"{self.name} - €{self.total_budget}"
    
    def get_total_planned_amount(self):
        """Calcola il totale delle spese pianificate per questo budget"""
        return self.planned_expenses.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    def get_total_spent_amount(self):
        """Calcola il totale delle spese effettivamente sostenute"""
        return self.planned_expenses.filter(
            status__in=['pagata', 'parzialmente_pagata']
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    def get_remaining_budget(self):
        """Calcola il budget rimanente"""
        return self.total_budget - self.get_total_planned_amount()
    
    def get_progress_percentage(self):
        """Calcola la percentuale di completamento del budget"""
        if self.total_budget > 0:
            spent = self.get_total_spent_amount()
            return float((spent / self.total_budget) * 100)
        return 0.0
    
    def get_planning_percentage(self):
        """Calcola la percentuale di pianificazione del budget"""
        if self.total_budget > 0:
            planned = self.get_total_planned_amount()
            return float((planned / self.total_budget) * 100)
        return 0.0
