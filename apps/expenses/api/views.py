from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg, Q
from datetime import datetime, timedelta
from apps.expenses.models import Expense, RecurringExpense, ExpenseAttachment, ExpenseQuota, Budget
from .serializers import (
    ExpenseSerializer,
    ExpenseCreateUpdateSerializer,
    RecurringExpenseSerializer,
    RecurringExpenseCreateUpdateSerializer,
    ExpenseAttachmentSerializer,
    ExpenseQuotaSerializer,
    ExpenseQuotaCreateUpdateSerializer,
    BudgetSerializer,
    BudgetCreateUpdateSerializer,
    ConvertToRecurringSerializer
)


class ExpenseViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione delle spese"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Nota: is_personal è gestito manualmente in get_queryset(), non in filterset_fields
    filterset_fields = ['category', 'subcategory', 'status', 'payment_method', 'is_recurring', 'date', 'planned_expense']
    search_fields = ['description', 'notes', 'category__name', 'subcategory__name']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date', '-created_at']

    def get_queryset(self):
        """Restituisce le spese dell'utente e della sua famiglia"""
        user = self.request.user

        # Controlla se stiamo richiedendo spese personali
        is_personal = self.request.query_params.get('is_personal')

        if is_personal == 'true':
            # Solo spese personali dell'utente corrente
            queryset = Expense.objects.filter(user=user, is_personal=True)
        else:
            # Se l'utente non appartiene a nessuna famiglia, vede solo le sue spese
            if not user.family:
                queryset = Expense.objects.filter(user=user, is_personal=False)
            else:
                # Restituisce tutte le spese della famiglia (escludendo le personali degli altri):
                # 1. Tutte le spese NON personali dei membri della stessa famiglia
                # 2. Le spese condivise direttamente con l'utente
                queryset = Expense.objects.filter(
                    Q(user__family=user.family, is_personal=False) |  # Spese famiglia (non personali)
                    Q(shared_with=user)  # Spese condivise direttamente
                ).distinct()

        # Filtro per range di date
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset.select_related(
            'user', 'category', 'subcategory', 'spending_plan'
        ).prefetch_related('shared_with', 'attachments', 'quote')
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ExpenseCreateUpdateSerializer
        return ExpenseSerializer
    
    def perform_create(self, serializer):
        """Assegna l'utente corrente alla spesa"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_expenses(self, request):
        """Restituisce solo le spese create dall'utente stesso"""
        user = request.user
        expenses = Expense.objects.filter(user=user).select_related(
            'user', 'category', 'subcategory', 'spending_plan'
        ).prefetch_related('shared_with', 'attachments', 'quote')
        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def shared_expenses(self, request):
        """Restituisce le spese condivise con l'utente"""
        expenses = Expense.objects.filter(shared_with=request.user).select_related(
            'user', 'category', 'subcategory', 'spending_plan'
        ).prefetch_related('shared_with', 'attachments', 'quote')
        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def monthly_summary(self, request):
        """Restituisce un riepilogo mensile delle spese"""
        year = request.query_params.get('year', datetime.today().year)
        month = request.query_params.get('month', datetime.today().month)
        
        expenses = self.get_queryset().filter(
            date__year=year,
            date__month=month,
            status='pagata'
        )
        
        # Totale per categoria
        by_category = expenses.values('category__name', 'category__type').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Totale per metodo di pagamento
        by_payment = expenses.values('payment_method').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Totale per utente
        by_user = expenses.values('user__username').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Statistiche generali
        stats = expenses.aggregate(
            total=Sum('amount'),
            count=Count('id'),
            average=Avg('amount')
        )
        
        return Response({
            'period': {'year': year, 'month': month},
            'statistics': {
                'total': str(stats['total'] or 0),
                'count': stats['count'],
                'average': str(stats['average'] or 0)
            },
            'by_category': by_category,
            'by_payment_method': by_payment,
            'by_user': by_user
        })
    
    @action(detail=False, methods=['get'])
    def yearly_summary(self, request):
        """Restituisce un riepilogo annuale delle spese"""
        from django.db.models.functions import ExtractMonth

        year = request.query_params.get('year', datetime.today().year)

        expenses = self.get_queryset().filter(
            date__year=year,
            status='pagata'
        )

        # Totale per mese - query singola ottimizzata
        by_month_data = expenses.annotate(
            month=ExtractMonth('date')
        ).values('month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('month')

        # Crea dizionario per accesso rapido
        month_dict = {item['month']: item for item in by_month_data}

        # Costruisci array con tutti i 12 mesi
        by_month = []
        for month in range(1, 13):
            month_data = month_dict.get(month, {'total': 0, 'count': 0})
            by_month.append({
                'month': month,
                'total': str(month_data['total'] or 0),
                'count': month_data['count']
            })

        # Statistiche generali
        stats = expenses.aggregate(
            total=Sum('amount'),
            count=Count('id'),
            average=Avg('amount')
        )

        return Response({
            'year': year,
            'statistics': {
                'total': str(stats['total'] or 0),
                'count': stats['count'],
                'average': str(stats['average'] or 0),
                'monthly_average': str((stats['total'] or 0) / 12)
            },
            'by_month': by_month
        })
    
    @action(detail=True, methods=['post'])
    def add_attachment(self, request, pk=None):
        """Aggiunge un allegato a una spesa"""
        expense = self.get_object()
        serializer = ExpenseAttachmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(expense=expense)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplica una spesa esistente"""
        expense = self.get_object()
        new_expense = Expense.objects.create(
            user=request.user,
            category=expense.category,
            subcategory=expense.subcategory,
            amount=expense.amount,
            description=f"Copia di: {expense.description}",
            notes=expense.notes,
            date=datetime.today(),
            payment_method=expense.payment_method,
            status='da_pagare',
            is_recurring=False
        )
        new_expense.shared_with.set(expense.shared_with.all())
        serializer = ExpenseSerializer(new_expense)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pay_expense(self, request, pk=None):
        """Paga una spesa esistente con possibilità di scegliere la fonte"""
        expense = self.get_object()

        # Verifica che la spesa non sia già pagata
        if expense.status == 'pagata':
            return Response(
                {"detail": "La spesa è già stata pagata"},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_method = request.data.get('payment_method', expense.payment_method)
        payment_source = request.data.get('payment_source', 'personal')

        # Se si paga con contributi, verifica disponibilità
        if payment_source == 'contribution':
            from apps.contributions.models import FamilyBalance
            from decimal import Decimal

            user = request.user
            if not user.family:
                return Response(
                    {"detail": "Utente non associato a una famiglia"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verifica bilancio famiglia
            try:
                family_balance = FamilyBalance.objects.get(family=user.family)
                family_balance.update_balance()

                if family_balance.current_balance < expense.amount:
                    return Response(
                        {"detail": f"Bilancio famiglia insufficiente. Disponibile: €{family_balance.current_balance}, Richiesto: €{expense.amount}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except FamilyBalance.DoesNotExist:
                return Response(
                    {"detail": "Bilancio famiglia non trovato"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Usa i contributi per pagare la spesa
            from apps.contributions.models import Contribution, ExpenseContribution

            # Trova contributi disponibili ordinati per data (FIFO)
            available_contributions = Contribution.objects.filter(
                user__family=user.family,
                available_balance__gt=0
            ).order_by('date')

            remaining_amount = expense.amount
            used_contributions = []

            for contribution in available_contributions:
                if remaining_amount <= 0:
                    break

                amount_to_use = min(remaining_amount, contribution.available_balance)

                # Crea il collegamento spesa-contributo
                expense_contribution = ExpenseContribution.objects.create(
                    expense=expense,
                    contribution=contribution,
                    amount_used=amount_to_use
                )

                # Aggiorna il saldo del contributo
                contribution.use_amount(amount_to_use)

                used_contributions.append({
                    'contribution_id': contribution.id,
                    'amount_used': amount_to_use
                })

                remaining_amount -= amount_to_use

            # Aggiorna il bilancio famiglia
            family_balance.update_balance()

        # Aggiorna la spesa
        expense.status = 'pagata'
        expense.payment_method = payment_method
        expense.payment_source = payment_source
        expense.save()

        serializer = ExpenseSerializer(expense)

        response_data = {
            'expense': serializer.data,
            'message': 'Spesa pagata con successo'
        }

        if payment_source == 'contribution':
            response_data['used_contributions'] = used_contributions
            response_data['updated_balance'] = float(family_balance.current_balance)

        return Response(response_data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def create_quote(self, request, pk=None):
        """Crea quote per una spesa"""
        expense = self.get_object()
        
        # Verifica che l'utente possa modificare questa spesa
        if expense.user != request.user and request.user not in expense.shared_with.all():
            return Response(
                {'detail': 'Non hai i permessi per modificare questa spesa.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verifica che non ci siano già quote
        if expense.has_quote():
            return Response(
                {'detail': 'Questa spesa ha già delle quote.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quote_data = request.data.get('quote', [])
        if not quote_data:
            return Response(
                {'detail': 'Devi fornire almeno una quota.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verifica che la somma delle quote corrisponda all'importo totale
        total_amount = sum(float(quota.get('amount', 0)) for quota in quote_data)
        if abs(total_amount - float(expense.amount)) > 0.01:  # Tolleranza per arrotondamenti
            return Response(
                {'detail': f'La somma delle quote (€{total_amount}) non corrisponde all\'importo della spesa (€{expense.amount}).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crea le quote
        created_quote = []
        for quota_data in quote_data:
            quota_data['expense'] = expense.id
            serializer = ExpenseQuotaCreateUpdateSerializer(data=quota_data)
            if serializer.is_valid():
                quota = serializer.save(expense=expense)
                created_quote.append(ExpenseQuotaSerializer(quota).data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'detail': f'Create {len(created_quote)} quote per la spesa.',
            'quote': created_quote
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def quote(self, request, pk=None):
        """Restituisce le quote di una spesa"""
        expense = self.get_object()
        quote = expense.quote.all().order_by('quota_number')
        serializer = ExpenseQuotaSerializer(quote, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def overdue_quote(self, request, pk=None):
        """Restituisce le quote scadute di una spesa"""
        expense = self.get_object()
        overdue = expense.get_overdue_quote()
        serializer = ExpenseQuotaSerializer(overdue, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def with_pending_quote(self, request):
        """Restituisce spese con quote in sospeso"""
        expenses = self.get_queryset().filter(
            quote__is_paid=False
        ).distinct()
        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue_summary(self, request):
        """Riepilogo quote scadute"""
        from django.utils import timezone

        user = request.user
        overdue_quote = ExpenseQuota.objects.filter(
            Q(expense__user=user) | Q(expense__shared_with=user),
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).distinct()

        total_overdue = overdue_quote.aggregate(total=Sum('amount'))['total'] or 0
        count_overdue = overdue_quote.count()

        # Raggruppa per spesa
        expenses_with_overdue = {}
        for quota in overdue_quote:
            expense_id = quota.expense.id
            if expense_id not in expenses_with_overdue:
                expenses_with_overdue[expense_id] = {
                    'expense': ExpenseSerializer(quota.expense).data,
                    'overdue_quote': []
                }
            expenses_with_overdue[expense_id]['overdue_quote'].append(
                ExpenseQuotaSerializer(quota).data
            )

        return Response({
            'summary': {
                'total_amount': str(total_overdue),
                'count': count_overdue
            },
            'expenses': list(expenses_with_overdue.values())
        })

    @action(detail=True, methods=['post'])
    def convert_to_recurring(self, request, pk=None):
        """Converte una spesa esistente in ricorrente"""
        expense = self.get_object()

        # Verifica che l'utente possa modificare questa spesa
        if expense.user != request.user and request.user not in expense.shared_with.all():
            return Response(
                {'detail': 'Non hai i permessi per modificare questa spesa.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica che la spesa non sia già ricorrente
        if expense.is_recurring:
            return Response(
                {'detail': 'Questa spesa è già ricorrente.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica che non esista già una spesa ricorrente con gli stessi dati
        existing_recurring = RecurringExpense.objects.filter(
            user=expense.user,
            category=expense.category,
            subcategory=expense.subcategory,
            amount=expense.amount,
            description=expense.description,
            is_active=True
        ).first()

        if existing_recurring:
            return Response(
                {'detail': 'Esiste già una spesa ricorrente simile.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ConvertToRecurringSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data

        # Crea la spesa ricorrente
        recurring_expense = RecurringExpense.objects.create(
            user=expense.user,
            category=expense.category,
            subcategory=expense.subcategory,
            amount=expense.amount,
            description=expense.description,
            frequency=validated_data['frequency'],
            start_date=validated_data['start_date'],
            end_date=validated_data.get('end_date'),
            payment_method=expense.payment_method,
            is_active=True
        )

        # Copia gli utenti condivisi
        recurring_expense.shared_with.set(expense.shared_with.all())

        # Aggiorna la spesa originale come ricorrente
        expense.is_recurring = True
        expense.save()

        # Genera spese future se richiesto
        generated_expenses = []
        if validated_data.get('generate_immediately', True):
            from dateutil.relativedelta import relativedelta

            # Logica di generazione delle spese future
            current_date = validated_data['start_date']
            end_date = validated_data.get('end_date')
            today = datetime.today().date()

            frequency_map = {
                'giornaliera': lambda d: d + timedelta(days=1),
                'settimanale': lambda d: d + timedelta(weeks=1),
                'bisettimanale': lambda d: d + timedelta(weeks=2),
                'mensile': lambda d: d + relativedelta(months=1),
                'bimestrale': lambda d: d + relativedelta(months=2),
                'trimestrale': lambda d: d + relativedelta(months=3),
                'semestrale': lambda d: d + relativedelta(months=6),
                'annuale': lambda d: d + relativedelta(years=1),
            }

            next_date_func = frequency_map.get(validated_data['frequency'])
            if next_date_func:
                next_date = next_date_func(current_date)

                # Genera al massimo 12 spese future per evitare troppi dati
                count = 0
                while (not end_date or next_date <= end_date) and next_date <= today + relativedelta(months=12) and count < 12:
                    future_expense = Expense.objects.create(
                        user=expense.user,
                        category=expense.category,
                        subcategory=expense.subcategory,
                        amount=expense.amount,
                        description=f"{expense.description} (Ricorrente)",
                        date=next_date,
                        payment_method=expense.payment_method,
                        status='pianificata',
                        is_recurring=True,
                        spending_plan=expense.spending_plan
                    )
                    future_expense.shared_with.set(expense.shared_with.all())
                    generated_expenses.append(ExpenseSerializer(future_expense).data)

                    next_date = next_date_func(next_date)
                    count += 1

            # Aggiorna la data di ultima generazione
            recurring_expense.last_generated = current_date
            recurring_expense.save()

        return Response({
            'detail': f'Spesa convertita in ricorrente con successo.',
            'recurring_expense': RecurringExpenseSerializer(recurring_expense).data,
            'generated_count': len(generated_expenses),
            'generated_expenses': generated_expenses[:5]  # Mostra solo le prime 5
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def batch_by_planned_expenses(self, request):
        """
        Endpoint ottimizzato per caricare expenses di multiple planned expenses in una sola chiamata.
        Accetta: ?planned_expense_ids=1,2,3,4,5
        Restituisce: {planned_expense_id: [expenses], ...}
        """
        planned_expense_ids_param = request.query_params.get('planned_expense_ids', '')

        if not planned_expense_ids_param:
            return Response({
                'detail': 'Parametro planned_expense_ids richiesto (es: ?planned_expense_ids=1,2,3)'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Parse IDs da stringa comma-separated
            planned_expense_ids = [int(id.strip()) for id in planned_expense_ids_param.split(',') if id.strip()]
        except ValueError:
            return Response({
                'detail': 'planned_expense_ids deve contenere solo numeri separati da virgole'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not planned_expense_ids:
            return Response({
                'detail': 'Almeno un planned_expense_id è richiesto'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Limita il numero massimo di IDs per evitare query troppo grosse
        if len(planned_expense_ids) > 50:
            return Response({
                'detail': 'Massimo 50 planned_expense_ids per chiamata'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Query ottimizzata con prefetch
        expenses = self.get_queryset().filter(
            planned_expense__in=planned_expense_ids
        ).select_related(
            'user', 'category', 'subcategory', 'planned_expense'
        ).prefetch_related(
            'shared_with', 'attachments'
        ).order_by('-date', '-created_at')

        # Organizza per planned_expense_id
        expenses_by_planned = {}
        for planned_id in planned_expense_ids:
            expenses_by_planned[planned_id] = []

        for expense in expenses:
            if expense.planned_expense_id in expenses_by_planned:
                expenses_by_planned[expense.planned_expense_id].append(
                    ExpenseSerializer(expense).data
                )

        return Response({
            'expenses_by_planned_expense': expenses_by_planned,
            'total_expenses': len(expenses),
            'planned_expense_ids_requested': planned_expense_ids
        })


class RecurringExpenseViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione delle spese ricorrenti"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'frequency', 'is_active']
    search_fields = ['description']
    ordering_fields = ['frequency', 'amount', 'start_date']
    ordering = ['frequency', 'description']
    
    def get_queryset(self):
        """Restituisce le spese ricorrenti dell'utente e quelle condivise"""
        user = self.request.user
        return RecurringExpense.objects.filter(
            Q(user=user) | Q(shared_with=user)
        ).distinct().select_related(
            'user', 'category', 'subcategory'
        ).prefetch_related('shared_with')
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return RecurringExpenseCreateUpdateSerializer
        return RecurringExpenseSerializer
    
    def perform_create(self, serializer):
        """Assegna l'utente corrente alla spesa ricorrente"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def generate_expense(self, request, pk=None):
        """Genera una spesa dal modello ricorrente"""
        recurring = self.get_object()
        
        # Crea la spesa
        expense = Expense.objects.create(
            user=recurring.user,
            category=recurring.category,
            subcategory=recurring.subcategory,
            amount=recurring.amount,
            description=recurring.description,
            date=datetime.today(),
            payment_method=recurring.payment_method,
            status='da_pagare',
            is_recurring=True
        )
        expense.shared_with.set(recurring.shared_with.all())
        
        # Aggiorna la data di ultima generazione
        recurring.last_generated = datetime.today()
        recurring.save()
        
        serializer = ExpenseSerializer(expense)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def generate_all_due(self, request):
        """Genera tutte le spese ricorrenti scadute"""
        from dateutil.relativedelta import relativedelta
        
        today = datetime.today().date()
        generated = []
        
        for recurring in RecurringExpense.objects.filter(is_active=True):
            # Verifica se � il momento di generare la spesa
            should_generate = False
            next_date = None
            
            if not recurring.last_generated:
                # Prima generazione
                should_generate = recurring.start_date <= today
                next_date = recurring.start_date
            else:
                # Calcola la prossima data in base alla frequenza
                if recurring.frequency == 'giornaliera':
                    next_date = recurring.last_generated + timedelta(days=1)
                elif recurring.frequency == 'settimanale':
                    next_date = recurring.last_generated + timedelta(weeks=1)
                elif recurring.frequency == 'bisettimanale':
                    next_date = recurring.last_generated + timedelta(weeks=2)
                elif recurring.frequency == 'mensile':
                    next_date = recurring.last_generated + relativedelta(months=1)
                elif recurring.frequency == 'bimestrale':
                    next_date = recurring.last_generated + relativedelta(months=2)
                elif recurring.frequency == 'trimestrale':
                    next_date = recurring.last_generated + relativedelta(months=3)
                elif recurring.frequency == 'semestrale':
                    next_date = recurring.last_generated + relativedelta(months=6)
                elif recurring.frequency == 'annuale':
                    next_date = recurring.last_generated + relativedelta(years=1)
                
                should_generate = next_date and next_date <= today
            
            # Verifica data di fine
            if recurring.end_date and today > recurring.end_date:
                should_generate = False
                recurring.is_active = False
                recurring.save()
            
            if should_generate:
                expense = Expense.objects.create(
                    user=recurring.user,
                    category=recurring.category,
                    subcategory=recurring.subcategory,
                    amount=recurring.amount,
                    description=f"{recurring.description} ({recurring.get_frequency_display()})",
                    date=next_date or today,
                    payment_method=recurring.payment_method,
                    status='da_pagare',
                    is_recurring=True
                )
                expense.shared_with.set(recurring.shared_with.all())
                
                recurring.last_generated = next_date or today
                recurring.save()
                
                generated.append(ExpenseSerializer(expense).data)
        
        return Response({
            'generated_count': len(generated),
            'expenses': generated
        }, status=status.HTTP_201_CREATED)


class ExpenseQuotaViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione delle quote di pagamento"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'is_paid', 'payment_method', 'due_date', 
        'expense__category', 'expense__subcategory', 
        'expense__user', 'expense__status'
    ]
    search_fields = ['expense__description', 'notes', 'expense__user__username']
    ordering_fields = ['due_date', 'quota_number', 'amount', 'expense__date']
    ordering = ['due_date', 'quota_number']
    
    def get_queryset(self):
        """Restituisce le quote dell'utente"""
        user = self.request.user
        return ExpenseQuota.objects.filter(
            Q(expense__user=user) | Q(expense__shared_with=user)
        ).distinct().select_related(
            'expense', 'expense__user', 'expense__category', 'expense__subcategory'
        ).prefetch_related('expense__shared_with')
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ExpenseQuotaCreateUpdateSerializer
        return ExpenseQuotaSerializer
    
    def perform_create(self, serializer):
        """Verifica permessi durante la creazione"""
        expense = serializer.validated_data['expense']
        user = self.request.user
        
        if expense.user != user and user not in expense.shared_with.all():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Non hai i permessi per creare quote per questa spesa.")
        
        serializer.save()
    
    def perform_update(self, serializer):
        """Verifica permessi durante l'aggiornamento"""
        quota = self.get_object()
        user = self.request.user
        
        if quota.expense.user != user and user not in quota.expense.shared_with.all():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Non hai i permessi per modificare questa quota.")
        
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Segna una quota come pagata"""
        quota = self.get_object()
        
        if quota.is_paid:
            return Response(
                {'detail': 'Questa quota è già stata pagata.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Aggiorna i dati della quota
        quota.is_paid = True
        quota.payment_method = request.data.get('payment_method', quota.payment_method)
        quota.notes = request.data.get('notes', quota.notes)
        quota.save()
        
        serializer = ExpenseQuotaSerializer(quota)
        return Response({
            'detail': 'Quota segnata come pagata.',
            'quota': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def mark_unpaid(self, request, pk=None):
        """Segna una quota come non pagata"""
        quota = self.get_object()
        
        if not quota.is_paid:
            return Response(
                {'detail': 'Questa quota non è stata ancora pagata.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quota.is_paid = False
        quota.paid_date = None
        quota.save()
        
        serializer = ExpenseQuotaSerializer(quota)
        return Response({
            'detail': 'Quota segnata come non pagata.',
            'quota': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def due_soon(self, request):
        """Restituisce quote in scadenza nei prossimi giorni"""
        from django.utils import timezone
        
        days = int(request.query_params.get('days', 7))
        end_date = timezone.now().date() + timedelta(days=days)
        
        quote = self.get_queryset().filter(
            is_paid=False,
            due_date__lte=end_date,
            due_date__gte=timezone.now().date()
        ).order_by('due_date')
        
        serializer = ExpenseQuotaSerializer(quote, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Restituisce quote scadute"""
        from django.utils import timezone
        
        overdue_quote = self.get_queryset().filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).order_by('due_date')
        
        serializer = ExpenseQuotaSerializer(overdue_quote, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """Restituisce quote organizzate per calendario"""
        from django.utils import timezone
        from collections import defaultdict
        
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        
        # Filtra quote per mese/anno
        quote = self.get_queryset().filter(
            due_date__year=year,
            due_date__month=month
        ).order_by('due_date')
        
        # Organizza per giorno
        calendar_data = defaultdict(list)
        for quota in quote:
            day = quota.due_date.day
            calendar_data[day].append(ExpenseQuotaSerializer(quota).data)
        
        return Response({
            'year': year,
            'month': month,
            'calendar': dict(calendar_data)
        })
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Restituisce quote raggruppate per categoria"""
        from collections import defaultdict
        
        quote = self.get_queryset().select_related(
            'expense', 'expense__category', 'expense__subcategory'
        )
        
        # Filtra per stato se richiesto
        is_paid = request.query_params.get('is_paid')
        if is_paid is not None:
            quote = quote.filter(is_paid=is_paid.lower() == 'true')
        
        # Raggruppa per categoria
        categories_data = defaultdict(lambda: {
            'category_name': '',
            'category_type': '',
            'total_amount': 0,
            'quote_count': 0,
            'subcategories': defaultdict(lambda: {
                'subcategory_name': '',
                'total_amount': 0,
                'quote_count': 0,
                'quote': []
            })
        })
        
        for quota in quote:
            category = quota.expense.category
            subcategory = quota.expense.subcategory
            
            if not category:
                continue
                
            cat_id = category.id
            subcat_id = subcategory.id if subcategory else 'no_subcategory'
            
            # Aggiorna dati categoria
            categories_data[cat_id]['category_name'] = category.name
            categories_data[cat_id]['category_type'] = category.type
            categories_data[cat_id]['total_amount'] += float(quota.amount)
            categories_data[cat_id]['quote_count'] += 1
            
            # Aggiorna dati sottocategoria
            if subcategory:
                categories_data[cat_id]['subcategories'][subcat_id]['subcategory_name'] = subcategory.name
            else:
                categories_data[cat_id]['subcategories'][subcat_id]['subcategory_name'] = 'Senza sottocategoria'
            
            categories_data[cat_id]['subcategories'][subcat_id]['total_amount'] += float(quota.amount)
            categories_data[cat_id]['subcategories'][subcat_id]['quote_count'] += 1
            categories_data[cat_id]['subcategories'][subcat_id]['quote'].append(
                ExpenseQuotaSerializer(quota).data
            )
        
        # Converte in lista
        result = []
        for cat_id, cat_data in categories_data.items():
            subcategories = []
            for subcat_id, subcat_data in cat_data['subcategories'].items():
                subcategories.append({
                    'subcategory_id': subcat_id if subcat_id != 'no_subcategory' else None,
                    'subcategory_name': subcat_data['subcategory_name'],
                    'total_amount': str(subcat_data['total_amount']),
                    'quote_count': subcat_data['quote_count'],
                    'quote': subcat_data['quote']
                })
            
            result.append({
                'category_id': cat_id,
                'category_name': cat_data['category_name'],
                'category_type': cat_data['category_type'],
                'total_amount': str(cat_data['total_amount']),
                'quote_count': cat_data['quote_count'],
                'subcategories': subcategories
            })
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiche generali delle quote"""
        queryset = self.get_queryset()
        
        total_quote = queryset.count()
        paid_quote = queryset.filter(is_paid=True).count()
        overdue_quote = queryset.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).count()
        
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0
        paid_amount = queryset.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0
        remaining_amount = total_amount - paid_amount
        
        return Response({
            'totals': {
                'total_quote': total_quote,
                'paid_quote': paid_quote,
                'pending_quote': total_quote - paid_quote,
                'overdue_quote': overdue_quote
            },
            'amounts': {
                'total_amount': str(total_amount),
                'paid_amount': str(paid_amount),
                'remaining_amount': str(remaining_amount),
                'completion_percentage': float((paid_amount / total_amount * 100) if total_amount > 0 else 0)
            }
        })


class BudgetViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione dei budget"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['budget_type', 'event_type', 'is_active', 'year', 'month']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'year', 'month', 'start_date', 'total_budget']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Restituisce solo i budget dell'utente corrente"""
        return Budget.objects.filter(created_by=self.request.user)
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BudgetCreateUpdateSerializer
        return BudgetSerializer
    
    def perform_create(self, serializer):
        """Assegna l'utente corrente come creatore del budget"""
        # Verifica che l'utente sia un master
        if not hasattr(self.request.user, 'profile') or not self.request.user.profile.is_master:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Solo gli utenti master possono creare budget.")
        
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def monthly(self, request):
        """Restituisce solo i budget mensili"""
        budgets = self.get_queryset().filter(budget_type='mensile').order_by('-year', '-month')
        serializer = BudgetSerializer(budgets, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def events(self, request):
        """Restituisce solo i budget per eventi"""
        budgets = self.get_queryset().filter(budget_type='evento').order_by('-start_date')
        serializer = BudgetSerializer(budgets, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def expenses(self, request, pk=None):
        """Restituisce le spese associate al budget"""
        budget = self.get_object()
        expenses = budget.planned_expenses.all().order_by('-date')
        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Riepilogo dettagliato del budget"""
        budget = self.get_object()
        
        # Statistiche per categoria
        expenses_by_category = budget.planned_expenses.values(
            'category__name', 'category__type'
        ).annotate(
            planned_amount=Sum('amount'),
            expense_count=Count('id')
        ).order_by('-planned_amount')
        
        # Statistiche per stato
        expenses_by_status = budget.planned_expenses.values('status').annotate(
            amount=Sum('amount'),
            count=Count('id')
        ).order_by('-amount')
        
        return Response({
            'budget': BudgetSerializer(budget).data,
            'by_category': expenses_by_category,
            'by_status': expenses_by_status
        })
    
    @action(detail=False, methods=['get'])
    def current_month(self, request):
        """Budget del mese corrente"""
        today = datetime.today()
        try:
            budget = self.get_queryset().get(
                budget_type='mensile',
                year=today.year,
                month=today.month
            )
            serializer = BudgetSerializer(budget)
            return Response(serializer.data)
        except Budget.DoesNotExist:
            return Response(
                {'detail': 'Nessun budget trovato per il mese corrente.'},
                status=status.HTTP_404_NOT_FOUND
            )