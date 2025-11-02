from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
from apps.reports.models import Budget, BudgetCategory, SavingGoal, PlannedExpense, SpendingPlan
from apps.expenses.models import Expense
from .serializers import (
    BudgetSerializer,
    BudgetCreateUpdateSerializer,
    BudgetCategorySerializer,
    BudgetCategoryCreateUpdateSerializer,
    SavingGoalSerializer,
    SavingGoalCreateUpdateSerializer,
    PlannedExpenseSerializer,
    PlannedExpenseCreateUpdateSerializer,
    SpendingPlanSerializer,
    SpendingPlanCreateUpdateSerializer
)


class BudgetViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione dei budget"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['plan_type', 'is_active']
    ordering_fields = ['start_date', 'end_date', 'created_at']
    ordering = ['-start_date', '-created_at']
    
    def get_queryset(self):
        """Restituisce i budget della famiglia dell'utente"""
        user = self.request.user

        # Se l'utente non appartiene a nessuna famiglia, non vede nessun budget
        if not user.family:
            return Budget.objects.none()

        # Filtra per budget che includono utenti della stessa famiglia
        family_users = user.family.members.all()
        return Budget.objects.filter(users__in=family_users).distinct()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BudgetCreateUpdateSerializer
        return BudgetSerializer
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Restituisce i budget attivi nel periodo corrente della famiglia"""
        from django.utils import timezone
        today = timezone.now().date()
        user = request.user

        # Se l'utente non appartiene a nessuna famiglia, non vede nessun budget
        if not user.family:
            return Response([])

        # Filtra per budget attivi che includono utenti della stessa famiglia
        family_users = user.family.members.all()
        budgets = Budget.objects.filter(
            users__in=family_users,
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).distinct()

        serializer = BudgetSerializer(budgets, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_category(self, request, pk=None):
        """Aggiunge una categoria al budget"""
        budget = self.get_object()
        serializer = BudgetCategoryCreateUpdateSerializer(data={
            'budget': budget.id,
            'category': request.data.get('category'),
            'amount': request.data.get('amount')
        })
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def copy_to_next_period(self, request, pk=None):
        """Copia il budget al periodo successivo"""
        budget = self.get_object()
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta

        # Calcola il periodo successivo
        period_length = (budget.end_date - budget.start_date).days
        new_start_date = budget.end_date + timedelta(days=1)
        new_end_date = new_start_date + timedelta(days=period_length)

        # Verifica se esiste già un budget sovrapposto
        if Budget.objects.filter(
            name=budget.name,
            start_date__lte=new_end_date,
            end_date__gte=new_start_date
        ).exists():
            return Response(
                {'detail': 'Esiste già un budget per il periodo selezionato.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea il nuovo budget
        new_budget = Budget.objects.create(
            name=budget.name,
            description=f"Copiato da {budget.start_date} - {budget.end_date}",
            plan_type=budget.plan_type,
            start_date=new_start_date,
            end_date=new_end_date,
            is_active=True
        )
        new_budget.users.set(budget.users.all())
        
        # Copia le categorie
        for cat_budget in budget.category_budgets.all():
            BudgetCategory.objects.create(
                budget=new_budget,
                category=cat_budget.category,
                amount=cat_budget.amount
            )
        
        serializer = BudgetSerializer(new_budget)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def comparison(self, request):
        """Confronto tra budget di diversi mesi"""
        months = int(request.query_params.get('months', 6))
        today = datetime.today()
        
        comparison_data = []
        for i in range(months):
            month = today.month - i
            year = today.year
            if month <= 0:
                month += 12
                year -= 1
            
            budget = Budget.objects.filter(
                users=request.user,
                year=year,
                month=month
            ).first()
            
            if budget:
                spent = budget.get_spent_amount()
                comparison_data.append({
                    'year': year,
                    'month': month,
                    'budget_name': budget.name,
                    'budget_amount': str(budget.total_amount),
                    'spent_amount': str(spent),
                    'remaining': str(budget.total_amount - spent),
                    'percentage': float(budget.get_percentage_used())
                })
            else:
                # Se non c'� budget, mostra solo le spese
                spent = Expense.objects.filter(
                    user=request.user,
                    date__year=year,
                    date__month=month,
                    status='pagata'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                comparison_data.append({
                    'year': year,
                    'month': month,
                    'budget_name': None,
                    'budget_amount': '0',
                    'spent_amount': str(spent),
                    'remaining': '0',
                    'percentage': 0
                })
        
        return Response(comparison_data)


class SavingGoalViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione degli obiettivi di risparmio"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_completed']
    ordering_fields = ['target_amount', 'target_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Restituisce gli obiettivi a cui l'utente appartiene"""
        return SavingGoal.objects.filter(users=self.request.user)
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SavingGoalCreateUpdateSerializer
        return SavingGoalSerializer
    
    @action(detail=True, methods=['post'])
    def add_amount(self, request, pk=None):
        """Aggiunge un importo all'obiettivo di risparmio"""
        goal = self.get_object()
        amount = request.data.get('amount', 0)
        
        try:
            amount = float(amount)
            if amount <= 0:
                return Response(
                    {'detail': 'L\'importo deve essere positivo.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Importo non valido.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        goal.current_amount += amount
        if goal.current_amount >= goal.target_amount:
            goal.is_completed = True
        goal.save()
        
        serializer = SavingGoalSerializer(goal)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def withdraw_amount(self, request, pk=None):
        """Preleva un importo dall'obiettivo di risparmio"""
        goal = self.get_object()
        amount = request.data.get('amount', 0)
        
        try:
            amount = float(amount)
            if amount <= 0:
                return Response(
                    {'detail': 'L\'importo deve essere positivo.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if amount > goal.current_amount:
                return Response(
                    {'detail': 'Importo superiore al saldo disponibile.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Importo non valido.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        goal.current_amount -= amount
        goal.is_completed = False
        goal.save()
        
        serializer = SavingGoalSerializer(goal)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active_goals(self, request):
        """Restituisce solo gli obiettivi attivi (non completati)"""
        goals = self.get_queryset().filter(is_completed=False)
        serializer = SavingGoalSerializer(goals, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def completed_goals(self, request):
        """Restituisce solo gli obiettivi completati"""
        goals = self.get_queryset().filter(is_completed=True)
        serializer = SavingGoalSerializer(goals, many=True)
        return Response(serializer.data)


class PlannedExpenseViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione delle spese pianificate"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'priority', 'is_completed', 'spending_plan']
    ordering_fields = ['due_date', 'amount', 'priority', 'created_at']
    ordering = ['due_date', '-priority', 'created_at']

    def get_queryset(self):
        """Restituisce le spese pianificate della famiglia dell'utente"""
        user = self.request.user

        # Se l'utente non appartiene a nessuna famiglia, non vede nessuna spesa pianificata
        if not user.family:
            return PlannedExpense.objects.none()

        # Filtra per spese pianificate che appartengono a spending plan della famiglia
        family_users = user.family.members.all()
        return PlannedExpense.objects.filter(
            spending_plan__users__in=family_users
        ).select_related(
            'spending_plan', 'category', 'subcategory'
        ).prefetch_related(
            'actual_expense'  # Per get_related_expenses()
        ).distinct()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PlannedExpenseCreateUpdateSerializer
        return PlannedExpenseSerializer


    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """Aggiunge un pagamento a una spesa pianificata"""
        try:
            print(f"🔍 Inizio add_payment con dati: {request.data}")
            planned_expense = self.get_object()
            print(f"🔍 Spesa pianificata trovata: {planned_expense.id}")
        except Exception as e:
            print(f"❌ Errore nel recupero spesa: {e}")
            import traceback
            traceback.print_exc()
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Validazione dei dati del pagamento
        print(f"🔍 Request data: {request.data}")
        amount = request.data.get('amount')
        description = request.data.get('description', f'Pagamento per {planned_expense.description}')
        print(f"🔍 Amount: {amount}, Description: {description}")

        # Handle category - can be an ID from request or Category instance from planned_expense
        category_data = request.data.get('category')
        if category_data is not None:
            # If category comes from request, it's likely an ID, convert to Category instance
            from apps.categories.models import Category
            if isinstance(category_data, (int, str)):
                try:
                    category = Category.objects.get(id=int(category_data))
                except Category.DoesNotExist:
                    category = planned_expense.category
            else:
                category = category_data
        else:
            category = planned_expense.category

        # Handle subcategory - can be an ID from request or Subcategory instance from planned_expense
        subcategory_data = request.data.get('subcategory')
        if subcategory_data is not None:
            # If subcategory comes from request, it's likely an ID, convert to Subcategory instance
            from apps.categories.models import Subcategory
            if isinstance(subcategory_data, (int, str)):
                try:
                    subcategory = Subcategory.objects.get(id=int(subcategory_data))
                except Subcategory.DoesNotExist:
                    subcategory = planned_expense.subcategory
            else:
                subcategory = subcategory_data
        else:
            subcategory = planned_expense.subcategory

        date = request.data.get('date')
        payment_method = request.data.get('payment_method', 'carta')
        payment_source = request.data.get('payment_source', 'personal')
        print(f"🔍 Parsed: date={date}, method={payment_method}, source={payment_source}")

        if not amount:
            return Response(
                {'detail': 'Importo del pagamento obbligatorio.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from decimal import Decimal
            amount = Decimal(str(amount))
            if amount <= 0:
                return Response(
                    {'detail': 'L\'importo deve essere maggiore di zero.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Importo non valido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica che il pagamento non superi l'importo rimanente
        remaining = planned_expense.get_remaining_amount()
        print(f"🔍 Amount validation: amount={amount}, remaining={remaining}")
        if amount > remaining:
            return Response(
                {'detail': f'Il pagamento di €{amount} supera l\'importo rimanente di €{remaining}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Se la fonte è 'contribution', verifica e gestisci i contributi famiglia
        available_contributions = None
        if payment_source == 'contribution':
            try:
                print(f"🔍 Processing contribution payment")
                if not request.user.family:
                    print(f"🔍 User has no family")
                    return Response(
                        {'detail': 'Utente non appartiene a nessuna famiglia.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                from apps.contributions.models import Contribution, ExpenseContribution
                print(f"🔍 User family: {request.user.family.id}")

                # Verifica saldo disponibile
                available_contributions = Contribution.objects.filter(
                    family=request.user.family,
                    available_balance__gt=0
                ).order_by('created_at')
                print(f"🔍 Found {available_contributions.count()} available contributions")

                total_available = sum(c.available_balance for c in available_contributions)
                print(f"🔍 Total available: €{total_available}")

                if amount > total_available:
                    print(f"🔍 Insufficient balance: requested {amount}, available {total_available}")
                    return Response(
                        {'detail': f'Saldo insufficiente. Disponibile: €{total_available}, richiesto: €{amount}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                print(f"❌ ERRORE in contribution validation: {e}")
                import traceback
                traceback.print_exc()
                return Response({'detail': f'Errore nella gestione contributi: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Crea la spesa reale collegata
        print(f"🔍 Preparing expense data...")
        from datetime import datetime
        expense_data = {
            'description': description,
            'amount': amount,
            'category': category,
            'subcategory': subcategory,
            'user': request.user,
            'date': date or datetime.now().date(),
            'status': 'pagata',
            'planned_expense': planned_expense,
            'payment_method': payment_method,
            'payment_source': payment_source
        }
        print(f"🔍 Expense data prepared successfully")

        try:
            from apps.expenses.models import Expense
            print(f"🔍 Creating expense with data: {expense_data}")
            expense = Expense.objects.create(**expense_data)
            print(f"🔍 Expense created successfully with ID: {expense.id}")
        except Exception as e:
            print(f"❌ ERRORE nella creazione spesa: {e}")
            import traceback
            traceback.print_exc()
            return Response({'detail': f'Errore nella creazione della spesa: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            # Se la fonte è 'contribution', registra l'utilizzo dei contributi con logica FIFO
            if payment_source == 'contribution':
                print(f"🔍 Payment source is contribution, available_contributions={available_contributions is not None}")
                if available_contributions:
                    print(f"🔍 Processing contributions usage")
                    remaining_amount = amount

                    for contribution in available_contributions:
                        if remaining_amount <= 0:
                            break

                        # Calcola quanto usare da questo contributo
                        use_amount = min(remaining_amount, contribution.available_balance)
                        print(f"🔍 Using {use_amount} from contribution {contribution.id}")

                        # Crea il record di utilizzo
                        ExpenseContribution.objects.create(
                            contribution=contribution,
                            expense=expense,
                            amount_used=use_amount
                        )

                        # Aggiorna il saldo disponibile
                        contribution.available_balance -= use_amount
                        contribution.save()

                        remaining_amount -= use_amount

            # Aggiorna lo stato della spesa pianificata se completamente pagata
            print(f"🔍 Checking if expense is fully paid")
            if planned_expense.is_fully_paid():
                planned_expense.is_completed = True
                planned_expense.save()
                print(f"🔍 Planned expense marked as completed")

            print(f"🔍 Preparing response")
            serializer = PlannedExpenseSerializer(planned_expense)
            return Response({
                'planned_expense': serializer.data,
                'expense_id': expense.id,
                'message': 'Pagamento aggiunto con successo.'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"❌ ERRORE nella finalizzazione: {e}")
            import traceback
            traceback.print_exc()
            return Response({'detail': f'Errore nella finalizzazione: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """Filtra le spese pianificate per stato di pagamento"""
        status_filter = request.query_params.get('status', 'all')
        queryset = self.get_queryset()

        if status_filter == 'pending':
            # Spese non ancora pagate
            queryset = [pe for pe in queryset if pe.get_payment_status() == 'pending']
        elif status_filter == 'partial':
            # Spese parzialmente pagate
            queryset = [pe for pe in queryset if pe.get_payment_status() == 'partial']
        elif status_filter == 'completed':
            # Spese completamente pagate
            queryset = [pe for pe in queryset if pe.get_payment_status() == 'completed']
        elif status_filter == 'overdue':
            # Spese scadute
            queryset = [pe for pe in queryset if pe.get_payment_status() == 'overdue']

        serializer = PlannedExpenseSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def due_soon(self, request):
        """Restituisce le spese pianificate in scadenza nei prossimi giorni"""
        from datetime import timedelta
        from django.utils import timezone

        days = int(request.query_params.get('days', 7))
        today = timezone.now().date()
        due_date = today + timedelta(days=days)

        queryset = self.get_queryset().filter(
            due_date__lte=due_date,
            due_date__gte=today,
            is_completed=False
        )

        serializer = PlannedExpenseSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def payment_summary(self, request):
        """Riepilogo dei pagamenti per tutte le spese pianificate"""
        queryset = self.get_queryset()

        summary = {
            'total_planned': 0,
            'total_paid': 0,
            'total_remaining': 0,
            'completed_count': 0,
            'partial_count': 0,
            'pending_count': 0,
            'overdue_count': 0
        }

        for pe in queryset:
            summary['total_planned'] += float(pe.amount)
            summary['total_paid'] += float(pe.get_total_paid())
            summary['total_remaining'] += float(pe.get_remaining_amount())

            status = pe.get_payment_status()
            if status == 'completed':
                summary['completed_count'] += 1
            elif status == 'partial':
                summary['partial_count'] += 1
            elif status == 'pending':
                summary['pending_count'] += 1
            elif status == 'overdue':
                summary['overdue_count'] += 1

        return Response(summary)

    @action(detail=True, methods=['post'])
    def generate_recurring(self, request, pk=None):
        """Genera le rate ricorrenti future per questa spesa pianificata"""
        planned_expense = self.get_object()

        # Validazione: deve essere ricorrente
        if not planned_expense.is_recurring:
            return Response(
                {'detail': 'Questa spesa non è configurata come ricorrente.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validazione: deve avere rate totali
        if not planned_expense.total_installments or planned_expense.total_installments <= 1:
            return Response(
                {'detail': 'Numero di rate totali non valido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Se non ha parent_recurring_id, è la prima rata - genera ID
        if not planned_expense.parent_recurring_id:
            import uuid
            planned_expense.parent_recurring_id = str(uuid.uuid4())
            planned_expense.save(update_fields=['parent_recurring_id'])

        # Prima pulisci le rate orfane (senza piano di spesa)
        from apps.reports.models import PlannedExpense
        orphaned_count = 0  # Inizializza sempre

        orphaned_installments = PlannedExpense.objects.filter(
            parent_recurring_id=planned_expense.parent_recurring_id,
            spending_plan__isnull=True
        ).exclude(id=planned_expense.id)  # Escludi la rata corrente

        orphaned_count = orphaned_installments.count()
        if orphaned_count > 0:
            orphaned_installments.delete()
            # Log per tracciare la pulizia
            print(f"Auto-pulizia: eliminate {orphaned_count} rate orfane per {planned_expense.description}")

        # Ora calcola le rate esistenti VALIDE (con piano)
        existing_count = PlannedExpense.objects.filter(
            parent_recurring_id=planned_expense.parent_recurring_id,
            spending_plan__isnull=False
        ).count()

        missing_count = planned_expense.total_installments - existing_count

        if missing_count <= 0:
            # Prepara messaggio informativo
            detail_msg = 'Tutte le rate sono già state generate.'
            if orphaned_count > 0:
                detail_msg += f' (Pulite {orphaned_count} rate orfane automaticamente)'

            return Response({
                'detail': detail_msg,
                'existing_installments': existing_count,
                'orphaned_cleaned': orphaned_count,
                'total_installments': planned_expense.total_installments
            })

        # Genera le rate mancanti
        from dateutil.relativedelta import relativedelta
        from apps.reports.models import SpendingPlan

        current_plan = planned_expense.spending_plan
        current_date = current_plan.start_date
        created_plans = []
        created_expenses = []

        for i in range(existing_count + 1, planned_expense.total_installments + 1):
            # Calcola la data per questa rata
            if planned_expense.recurring_frequency == 'monthly':
                installment_date = current_date + relativedelta(months=i-1)
            elif planned_expense.recurring_frequency == 'bimonthly':
                installment_date = current_date + relativedelta(months=(i-1)*2)
            elif planned_expense.recurring_frequency == 'quarterly':
                installment_date = current_date + relativedelta(months=(i-1)*3)
            else:
                installment_date = current_date + relativedelta(months=i-1)

            # Trova o crea il piano per questo mese
            plan = self._get_or_create_plan_for_date(
                installment_date, current_plan, request.user
            )

            if plan in created_plans:
                pass  # Piano già creato in questa sessione
            elif plan.auto_generated:
                created_plans.append(plan)

            # Crea la rata
            installment_description = (
                f"{planned_expense.description} "
                f"(rata {i}/{planned_expense.total_installments})"
            )

            new_expense = PlannedExpense.objects.create(
                spending_plan=plan,
                description=installment_description,
                amount=planned_expense.amount,
                category=planned_expense.category,
                subcategory=planned_expense.subcategory,
                priority=planned_expense.priority,
                due_date=installment_date,
                notes=f"Rata {i} di {planned_expense.total_installments} - Auto-generata",
                is_recurring=True,
                total_installments=planned_expense.total_installments,
                installment_number=i,
                parent_recurring_id=planned_expense.parent_recurring_id,
                recurring_frequency=planned_expense.recurring_frequency
            )
            created_expenses.append(new_expense)

        # Aggiungi una nota alla spesa originale per indicare che è stata processata
        if created_expenses:
            if planned_expense.notes:
                planned_expense.notes += f"\n\n✅ Rate generate il {timezone.now().strftime('%d/%m/%Y %H:%M')}"
            else:
                planned_expense.notes = f"✅ Rate generate il {timezone.now().strftime('%d/%m/%Y %H:%M')}"
            planned_expense.save(update_fields=['notes'])

        # Prepara messaggio dettagliato
        detail_msg = f'Generate {len(created_expenses)} rate ricorrenti.'
        if orphaned_count > 0:
            detail_msg += f' (Pulite {orphaned_count} rate orfane automaticamente)'

        return Response({
            'detail': detail_msg,
            'created_installments': len(created_expenses),
            'created_plans': len(created_plans),
            'orphaned_cleaned': orphaned_count,
            'total_installments': planned_expense.total_installments,
            'parent_recurring_id': planned_expense.parent_recurring_id
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def recurring_status(self, request, pk=None):
        """Restituisce lo stato di tutte le rate ricorrenti per questa spesa"""
        planned_expense = self.get_object()

        # Validazione: deve essere ricorrente
        if not planned_expense.is_recurring or not planned_expense.parent_recurring_id:
            return Response(
                {'detail': 'Questa spesa non è ricorrente o non ha rate collegate.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Trova tutte le rate collegate
        from apps.reports.models import PlannedExpense
        installments = PlannedExpense.objects.filter(
            parent_recurring_id=planned_expense.parent_recurring_id
        ).order_by('installment_number')

        # Costruisci la risposta con lo stato di ogni rata
        installments_data = []
        for installment in installments:
            installments_data.append({
                'id': installment.id,
                'installment_number': installment.installment_number,
                'total_installments': installment.total_installments,
                'amount': str(installment.amount),
                'is_completed': installment.is_completed,
                'total_paid': str(installment.get_total_paid()),
                'is_fully_paid': installment.is_fully_paid(),
                'is_partially_paid': installment.is_partially_paid(),
                'due_date': installment.due_date,
                'spending_plan_name': installment.spending_plan.name if installment.spending_plan else None
            })

        return Response({
            'parent_recurring_id': planned_expense.parent_recurring_id,
            'total_installments': planned_expense.total_installments,
            'installments': installments_data
        })

    @action(detail=True, methods=['patch'], url_path='installments/(?P<installment_number>[^/.]+)')
    def update_installment(self, request, pk=None, installment_number=None):
        """Aggiorna l'importo di una specifica rata ricorrente"""
        planned_expense = self.get_object()

        # Validazione: deve essere ricorrente
        if not planned_expense.is_recurring or not planned_expense.parent_recurring_id:
            return Response(
                {'detail': 'Questa spesa non è ricorrente o non ha rate collegate.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validazione dell'installment_number
        try:
            installment_num = int(installment_number)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Numero rata non valido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Trova la rata specifica
        from apps.reports.models import PlannedExpense
        target_installment = PlannedExpense.objects.filter(
            parent_recurring_id=planned_expense.parent_recurring_id,
            installment_number=installment_num
        ).first()

        if not target_installment:
            return Response(
                {'detail': f'Rata {installment_num} non trovata.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validazione dell'importo
        amount = request.data.get('amount')
        if not amount:
            return Response(
                {'detail': 'Campo amount obbligatorio.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Importo deve essere un numero positivo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Aggiorna l'importo
        old_amount = target_installment.amount
        target_installment.amount = amount
        target_installment.save(update_fields=['amount'])

        # Calcola il nuovo summary per tutte le rate
        from decimal import Decimal
        installments = PlannedExpense.objects.filter(
            parent_recurring_id=planned_expense.parent_recurring_id
        )

        total_amount = Decimal('0.00')
        completed_amount = Decimal('0.00')
        pending_amount = Decimal('0.00')

        for inst in installments:
            inst_amount = inst.amount or Decimal('0.00')
            total_amount += inst_amount

            if inst.is_completed or inst.is_fully_paid():
                completed_amount += inst_amount
            else:
                pending_amount += inst_amount

        updated_summary = {
            'total_amount': str(total_amount),
            'completed_amount': str(completed_amount),
            'pending_amount': str(pending_amount),
            'total_count': installments.count()
        }

        return Response({
            'detail': f'Rata {installment_num} aggiornata da €{old_amount} a €{amount}.',
            'installment_number': installment_num,
            'old_amount': str(old_amount),
            'new_amount': str(amount),
            'updated_installment': {
                'id': target_installment.id,
                'installment_number': target_installment.installment_number,
                'amount': str(target_installment.amount),
                'due_date': target_installment.due_date,
                'is_completed': target_installment.is_completed
            },
            'updated_summary': updated_summary
        })

    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        """
        Restituisce tutti i pagamenti di una spesa pianificata, inclusi quelli di altri membri della famiglia
        """
        from apps.expenses.api.serializers import ExpenseSerializer

        planned_expense = self.get_object()
        user = request.user

        # Verifica che l'utente abbia accesso alla spesa pianificata
        if not user.family:
            return Response(
                {'detail': 'Famiglia richiesta per accedere ai pagamenti'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica che il piano di spesa sia condiviso o che l'utente abbia accesso
        if planned_expense.spending_plan.plan_scope == 'personal' and user not in planned_expense.spending_plan.users.all():
            return Response(
                {'detail': 'Non hai accesso ai pagamenti di questa spesa'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Restituisce tutti i pagamenti della famiglia per questa spesa pianificata
        payments = Expense.objects.filter(
            planned_expense=planned_expense,
            user__family=user.family  # Solo utenti della stessa famiglia
        ).select_related('user', 'category', 'subcategory', 'spending_plan').order_by('-date', '-created_at')

        serializer = ExpenseSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='update_payment')
    def update_payment(self, request, pk=None):
        """Modifica un pagamento specifico di una spesa pianificata"""
        from apps.expenses.models import Expense
        from apps.expenses.api.serializers import ExpenseCreateUpdateSerializer
        from decimal import Decimal

        planned_expense = self.get_object()
        user = request.user
        payment_id = request.data.get('payment_id')

        if not payment_id:
            return Response(
                {'detail': 'payment_id obbligatorio'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Trova il pagamento (spesa collegata)
            payment = Expense.objects.get(
                id=payment_id,
                planned_expense=planned_expense,
                user__family=user.family
            )
        except Expense.DoesNotExist:
            return Response(
                {'detail': 'Pagamento non trovato'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Salva l'importo originale per ricalcolare il rimanente
        original_amount = payment.amount
        new_amount = request.data.get('amount')

        if new_amount:
            try:
                new_amount = Decimal(str(new_amount))
                if new_amount <= 0:
                    return Response(
                        {'detail': 'L\'importo deve essere maggiore di zero'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Calcola quanto rimanente avremmo se togliessimo questo pagamento
                remaining_without_this = planned_expense.get_remaining_amount() + original_amount

                # Verifica che il nuovo importo non superi il rimanente
                if new_amount > remaining_without_this:
                    return Response(
                        {'detail': f'Il nuovo importo di €{new_amount} supera l\'importo disponibile di €{remaining_without_this}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'Importo non valido'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Aggiorna il pagamento
        serializer = ExpenseCreateUpdateSerializer(payment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            # Ricarica la spesa pianificata per aggiornare i totali
            planned_expense.refresh_from_db()

            from apps.expenses.api.serializers import ExpenseSerializer
            return Response(ExpenseSerializer(payment).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete_payment')
    def delete_payment(self, request, pk=None):
        """Elimina un pagamento specifico di una spesa pianificata"""
        from apps.expenses.models import Expense

        planned_expense = self.get_object()
        user = request.user
        payment_id = request.data.get('payment_id') or request.query_params.get('payment_id')

        if not payment_id:
            return Response(
                {'detail': 'payment_id obbligatorio'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Trova il pagamento (spesa collegata)
            payment = Expense.objects.get(
                id=payment_id,
                planned_expense=planned_expense,
                user__family=user.family
            )
        except Expense.DoesNotExist:
            return Response(
                {'detail': 'Pagamento non trovato'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Se il pagamento usa contributi famiglia, ripristina il saldo
        if payment.payment_source == 'contribution':
            from apps.contributions.models import ExpenseContribution

            # Trova tutti i contributi usati per questo pagamento
            expense_contributions = ExpenseContribution.objects.filter(expense=payment)

            for ec in expense_contributions:
                # Ripristina il saldo disponibile
                ec.contribution.available_balance += ec.amount_used
                ec.contribution.save()

            # Elimina i record di collegamento
            expense_contributions.delete()

        # Elimina il pagamento
        payment.delete()

        # Ricarica la spesa pianificata per aggiornare i totali
        planned_expense.refresh_from_db()

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _get_or_create_plan_for_date(self, target_date, template_plan, user):
        """Helper: trova o crea un piano per la data target"""
        from apps.reports.models import SpendingPlan
        from dateutil.relativedelta import relativedelta

        # Cerca piano esistente per questo mese
        existing_plan = SpendingPlan.objects.filter(
            plan_type='monthly',
            start_date__year=target_date.year,
            start_date__month=target_date.month
        ).first()

        if existing_plan:
            return existing_plan

        # Crea nuovo piano
        start_date = target_date.replace(day=1)
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)

        plan_name = f"{target_date.strftime('%B %Y').title()}"

        new_plan = SpendingPlan.objects.create(
            name=plan_name,
            description=f"Piano auto-generato per {plan_name}",
            plan_type='monthly',
            start_date=start_date,
            end_date=end_date,
            total_budget=template_plan.total_budget,
            plan_scope=template_plan.plan_scope,
            created_by=user,
            auto_generated=True,
            is_hidden=False  # Visibile se contiene spese ricorrenti
        )

        # Copia gli utenti
        new_plan.users.set(template_plan.users.all())

        return new_plan


class SpendingPlanViewSet(viewsets.ModelViewSet):
    """ViewSet per la gestione dei piani di spesa"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['plan_type', 'is_active']
    ordering_fields = ['start_date', 'end_date', 'created_at']
    ordering = ['-start_date', '-created_at']

    def get_queryset(self):
        """Restituisce i piani di spesa visibili all'utente (personali + famiglia)"""
        user = self.request.user
        from django.db.models import Q
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta

        # Piani personali (creati dall'utente e non condivisi)
        personal_plans = Q(created_by=user, plan_scope='personal')

        # Piani condivisi con la famiglia (se l'utente ha una famiglia)
        family_plans = Q()
        if user.family:
            family_users = user.family.members.all()
            family_plans = Q(users__in=family_users, plan_scope='family')

        # Query base
        queryset = SpendingPlan.objects.filter(
            personal_plans | family_plans
        ).select_related(
            'created_by'
        ).prefetch_related(
            'users',
            'planned_expenses__category',
            'planned_expenses__subcategory'
        ).distinct()

        # Applica filtro temporale se non richiesto "show_all"
        show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
        if not show_all:
            # Limita ai piani nei prossimi 3 mesi (default)
            today = timezone.now().date()
            three_months_from_now = today + relativedelta(months=3)
            queryset = queryset.filter(start_date__lte=three_months_from_now)

        return queryset

    def list(self, request, *args, **kwargs):
        """Override list per aggiungere il conteggio totale ed evitare doppia chiamata API"""
        from django.db.models import Q, Sum, Count, Case, When, Value, DecimalField, Exists, OuterRef, BooleanField
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta
        from apps.reports.models import UserSpendingPlanPreference
        from decimal import Decimal

        user = request.user
        show_all = request.query_params.get('show_all', 'false').lower() == 'true'
        show_hidden = request.query_params.get('show_hidden', 'false').lower() == 'true'

        # Base queryset (stesso logic di get_queryset)
        personal_plans = Q(created_by=user, plan_scope='personal')
        family_plans = Q()
        if user.family:
            family_users = user.family.members.all()
            family_plans = Q(users__in=family_users, plan_scope='family')

        # Annotazioni per evitare N+1 query
        base_queryset = SpendingPlan.objects.filter(
            personal_plans | family_plans
        ).select_related(
            'created_by'
        ).prefetch_related(
            'users'
        ).annotate(
            # Somma importi pianificati
            total_planned_amount=Sum('planned_expenses__amount', default=Decimal('0.00')),
            # Conta spese pianificate
            planned_expenses_count=Count('planned_expenses', distinct=True),
            # Conta spese non pianificate
            unplanned_expenses_count=Count(
                'actual_expenses',
                filter=Q(actual_expenses__status__in=['pagata', 'parzialmente_pagata']),
                distinct=True
            ),
            # Somma spese non pianificate (actual_expenses è il related_name corretto)
            unplanned_expenses_amount=Sum(
                Case(
                    When(
                        Q(actual_expenses__status__in=['pagata', 'parzialmente_pagata']),
                        then='actual_expenses__amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                ),
                default=Decimal('0.00')
            ),
            # Importo spese completate (planned expenses pagate)
            completed_expenses_amount=Sum(
                'planned_expenses__actual_payments__amount',
                default=Decimal('0.00')
            ),
            # Conta spese completate
            completed_count=Count(
                'planned_expenses',
                filter=Q(planned_expenses__actual_payments__isnull=False),
                distinct=True
            ),
            # Pin personalizzato dell'utente
            is_pinned_by_user=Exists(
                UserSpendingPlanPreference.objects.filter(
                    spending_plan=OuterRef('pk'),
                    user=user,
                    is_pinned=True
                )
            )
        ).distinct()

        # Filtra per piani nascosti o visibili in base al parametro show_hidden
        if show_hidden:
            # Mostra SOLO i piani nascosti
            base_queryset = base_queryset.filter(is_hidden=True)
        else:
            # Mostra SOLO i piani visibili (comportamento default)
            base_queryset = base_queryset.filter(is_hidden=False)

        # Conta il totale dei piani (nascosti o visibili in base al filtro)
        total_count = base_queryset.count()

        # Applica filtro temporale se richiesto
        if not show_all:
            today = timezone.now().date()
            three_months_from_now = today + relativedelta(months=3)
            queryset = base_queryset.filter(start_date__lte=three_months_from_now)
        else:
            queryset = base_queryset

        # Ordina: piani pinnati per primi, poi per data di inizio (più recenti prima)
        queryset = queryset.order_by('-is_pinned_by_user', '-start_date')

        # Serializza i risultati
        serializer = self.get_serializer(queryset, many=True)

        # Aggiungi metadati nella risposta
        response_data = {
            'results': serializer.data,
            'count': len(serializer.data),
            'total_count': total_count,
            'show_all': show_all,
            'show_hidden': show_hidden
        }

        return Response(response_data)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SpendingPlanCreateUpdateSerializer
        elif self.action == 'list':
            from .serializers import SpendingPlanListSerializer
            return SpendingPlanListSerializer
        return SpendingPlanSerializer

    def perform_create(self, serializer):
        """Salva automaticamente il creatore del piano"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Restituisce i piani di spesa attivi nel periodo corrente della famiglia"""
        from django.utils import timezone
        today = timezone.now().date()
        user = request.user

        # Se l'utente non appartiene a nessuna famiglia, non vede nessun piano
        if not user.family:
            return Response([])

        # Filtra per piani attivi che includono utenti della stessa famiglia
        family_users = user.family.members.all()
        plans = SpendingPlan.objects.filter(
            users__in=family_users,
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).distinct()

        serializer = SpendingPlanSerializer(plans, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def select_options(self, request):
        """Restituisce piani di spesa ottimizzati per select (solo ID e nome)"""
        user = request.user
        from django.db.models import Q

        # Piani personali (creati dall'utente e non condivisi)
        personal_plans = Q(created_by=user, plan_scope='personal')

        # Piani condivisi con la famiglia (se l'utente ha una famiglia)
        family_plans = Q()
        if user.family:
            family_users = user.family.members.all()
            family_plans = Q(users__in=family_users, plan_scope='family')

        # Query ottimizzata - solo campi necessari per select
        plans = SpendingPlan.objects.filter(
            personal_plans | family_plans
        ).filter(
            is_active=True
        ).values('id', 'name', 'plan_type').order_by('name').distinct()

        return Response(list(plans))

    @action(detail=True, methods=['post'])
    def copy_to_next_period(self, request, pk=None):
        """Copia il piano di spesa al periodo successivo"""
        plan = self.get_object()
        from datetime import timedelta

        # Calcola il periodo successivo
        period_length = (plan.end_date - plan.start_date).days
        new_start_date = plan.end_date + timedelta(days=1)
        new_end_date = new_start_date + timedelta(days=period_length)

        # Verifica se esiste già un piano sovrapposto
        if SpendingPlan.objects.filter(
            name=plan.name,
            start_date__lte=new_end_date,
            end_date__gte=new_start_date
        ).exists():
            return Response(
                {'detail': 'Esiste già un piano per il periodo selezionato.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea il nuovo piano
        new_plan = SpendingPlan.objects.create(
            name=plan.name,
            description=f"Copiato da {plan.start_date} - {plan.end_date}",
            plan_type=plan.plan_type,
            start_date=new_start_date,
            end_date=new_end_date,
            is_active=True
        )
        new_plan.users.set(plan.users.all())

        # Copia le spese pianificate
        for planned_expense in plan.planned_expenses.all():
            PlannedExpense.objects.create(
                spending_plan=new_plan,
                description=planned_expense.description,
                amount=planned_expense.amount,
                category=planned_expense.category,
                subcategory=planned_expense.subcategory,
                priority=planned_expense.priority,
                notes=planned_expense.notes
            )

        serializer = SpendingPlanSerializer(new_plan)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def smart_clone(self, request, pk=None):
        """Clona intelligentemente un piano di spesa con riconoscimento pattern e date"""
        plan = self.get_object()
        from apps.reports.utils.plan_pattern_recognition import generate_intelligent_clone_data

        # Controlla se è solo preview o creazione effettiva
        preview_only = request.data.get('preview_only', False)

        # Usa il nuovo utility per generare i dati del clone
        clone_data = generate_intelligent_clone_data(
            plan_name=plan.name,
            start_date=plan.start_date,
            end_date=plan.end_date,
            plan_type=plan.plan_type
        )

        new_title = clone_data['new_title']
        new_start_date = clone_data['new_start_date']
        new_end_date = clone_data['new_end_date']
        pattern_detection = clone_data['pattern_detection']

        # Verifica se esiste già un piano sovrapposto
        existing_plan = SpendingPlan.objects.filter(
            name=new_title,
            start_date__lte=new_end_date,
            end_date__gte=new_start_date
        ).first()

        if existing_plan:
            return Response({
                'detail': f'Esiste già un piano "{new_title}" per il periodo selezionato.',
                'suggested_title': new_title,
                'suggested_start_date': new_start_date.isoformat(),
                'suggested_end_date': new_end_date.isoformat(),
                'conflict_with_existing_plan': {
                    'id': existing_plan.id,
                    'name': existing_plan.name,
                    'period': f"{existing_plan.start_date} - {existing_plan.end_date}"
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Se è solo preview, restituisci i dati senza creare nulla
        if preview_only:
            # Simula le spese clonate senza salvarle
            simulated_expenses = []
            for planned_expense in plan.planned_expenses.all():
                # Calcola la nuova data di scadenza
                if planned_expense.due_date:
                    days_from_start = (planned_expense.due_date - plan.start_date).days
                    new_due_date = new_start_date + timedelta(days=days_from_start)
                    if new_due_date > new_end_date:
                        new_due_date = new_end_date
                else:
                    new_due_date = None

                simulated_expenses.append({
                    'id': None,  # Non esiste ancora
                    'description': planned_expense.description,
                    'amount': str(planned_expense.amount),
                    'category': planned_expense.category.id if planned_expense.category else None,
                    'category_name': planned_expense.category.name if planned_expense.category else None,
                    'subcategory': planned_expense.subcategory.id if planned_expense.subcategory else None,
                    'priority': planned_expense.priority,
                    'due_date': new_due_date.isoformat() if new_due_date else None,
                    'notes': planned_expense.notes
                })

            # Prepara risposta preview
            preview_data = {
                'cloned_plan': {
                    'id': None,  # Non esiste ancora
                    'name': new_title,
                    'description': plan.description,
                    'plan_type': plan.plan_type,
                    'total_budget': str(plan.total_budget) if plan.total_budget else None,
                    'start_date': new_start_date.isoformat(),
                    'end_date': new_end_date.isoformat(),
                    'plan_scope': plan.plan_scope,
                    'planned_expenses_detail': simulated_expenses
                },
                'cloning_details': {
                    'original_plan': {
                        'id': plan.id,
                        'name': plan.name,
                        'period': f"{plan.start_date} - {plan.end_date}"
                    },
                    'pattern_detection': pattern_detection,
                    'new_period': {
                        'start_date': new_start_date.isoformat(),
                        'end_date': new_end_date.isoformat(),
                        'title': new_title
                    },
                    'expenses_cloned': len(simulated_expenses),
                    'expenses_with_dates_adjusted': len([e for e in simulated_expenses if e['due_date']])
                }
            }

            return Response(preview_data, status=status.HTTP_200_OK)

        # Se non è preview, crea effettivamente il piano
        new_plan = SpendingPlan.objects.create(
            name=new_title,
            description=plan.description,
            plan_type=plan.plan_type,
            total_budget=plan.total_budget,
            start_date=new_start_date,
            end_date=new_end_date,
            plan_scope=plan.plan_scope,
            is_active=True,
            created_by=request.user
        )

        # Copia gli utenti
        new_plan.users.set(plan.users.all())

        # Clona le spese pianificate
        cloned_expenses = []
        for planned_expense in plan.planned_expenses.all():
            if planned_expense.due_date:
                days_from_start = (planned_expense.due_date - plan.start_date).days
                new_due_date = new_start_date + timedelta(days=days_from_start)
                if new_due_date > new_end_date:
                    new_due_date = new_end_date
            else:
                new_due_date = None

            cloned_expense = PlannedExpense.objects.create(
                spending_plan=new_plan,
                description=planned_expense.description,
                amount=planned_expense.amount,
                category=planned_expense.category,
                subcategory=planned_expense.subcategory,
                priority=planned_expense.priority,
                due_date=new_due_date,
                notes=planned_expense.notes
            )
            cloned_expenses.append(cloned_expense)

        # Prepara risposta con piano creato
        response_data = {
            'cloned_plan': SpendingPlanSerializer(new_plan).data,
            'cloning_details': {
                'original_plan': {
                    'id': plan.id,
                    'name': plan.name,
                    'period': f"{plan.start_date} - {plan.end_date}"
                },
                'pattern_detection': pattern_detection,
                'new_period': {
                    'start_date': new_start_date.isoformat(),
                    'end_date': new_end_date.isoformat(),
                    'title': new_title
                },
                'expenses_cloned': len(cloned_expenses),
                'expenses_with_dates_adjusted': len([e for e in cloned_expenses if e.due_date])
            }
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """Endpoint ottimizzato con paginazione DRF standard per spese pianificate

        Supporta filtri per status:
        - ?status=all (default) - tutte le spese
        - ?status=pending - solo spese in attesa
        - ?status=partial - solo spese parzialmente pagate
        - ?status=completed - solo spese completate
        - ?status=overdue - solo spese scadute
        """
        plan = self.get_object()
        status_filter = request.query_params.get('status', 'all')

        # Ottieni QuerySet delle spese pianificate del piano
        from apps.reports.models import PlannedExpense
        planned_expenses_qs = PlannedExpense.objects.filter(
            spending_plan=plan
        ).select_related(
            'category', 'subcategory'
        ).prefetch_related(
            'actual_payments'
        ).order_by('-created_at')

        # Applica filtro status se necessario
        if status_filter != 'all':
            from datetime import date
            today = date.today()

            # Per i filtri complessi che richiedono logica Python, dobbiamo filtrare manualmente
            if status_filter in ['pending', 'partial', 'completed']:
                filtered_expenses = []
                for pe in planned_expenses_qs:
                    payment_status = pe.get_payment_status()
                    if status_filter == payment_status:
                        filtered_expenses.append(pe.pk)
                planned_expenses_qs = planned_expenses_qs.filter(pk__in=filtered_expenses)

            elif status_filter == 'overdue':
                overdue_expenses = []
                for pe in planned_expenses_qs:
                    if pe.due_date and pe.due_date < today and pe.get_payment_status() != 'completed':
                        overdue_expenses.append(pe.pk)
                planned_expenses_qs = planned_expenses_qs.filter(pk__in=overdue_expenses)

        # Usa la paginazione DRF standard
        paginator = self.paginate_queryset(planned_expenses_qs)
        if paginator is not None:
            from .serializers import PlannedExpenseLightSerializer
            planned_expenses_serializer = PlannedExpenseLightSerializer(paginator, many=True)

            # Serializza i dati del piano
            from .serializers import SpendingPlanDetailSerializer
            plan_serializer = SpendingPlanDetailSerializer(plan, context={'request': request})

            # Carica le spese reali del piano (non paginate)
            from apps.expenses.models import Expense
            unplanned_expenses = Expense.objects.filter(
                spending_plan=plan,
                planned_expense__isnull=True
            ).select_related('category', 'subcategory', 'user')

            # Applica filtro anche alle spese non pianificate
            if status_filter != 'all':
                if status_filter == 'completed':
                    unplanned_expenses = unplanned_expenses.filter(status='pagata')
                elif status_filter == 'pending':
                    unplanned_expenses = unplanned_expenses.filter(status__in=['pianificata', 'in_sospeso'])
                elif status_filter == 'overdue':
                    from datetime import date
                    today = date.today()
                    unplanned_expenses = unplanned_expenses.filter(
                        date__lt=today,
                        status__in=['pianificata', 'in_sospeso']
                    )
                else:
                    unplanned_expenses = unplanned_expenses.none()

            from apps.expenses.api.serializers import ExpenseSerializer
            unplanned_serializer = ExpenseSerializer(unplanned_expenses, many=True)

            # Restituisce response con formato DRF standard
            return self.get_paginated_response({
                'plan': plan_serializer.data,
                'planned_expenses': planned_expenses_serializer.data,
                'unplanned_expenses': unplanned_serializer.data,
                'applied_filter': status_filter
            })

        # Fallback se la paginazione non è disponibile
        from .serializers import SpendingPlanDetailSerializer, PlannedExpenseLightSerializer
        plan_serializer = SpendingPlanDetailSerializer(plan, context={'request': request})
        planned_expenses_serializer = PlannedExpenseLightSerializer(planned_expenses_qs, many=True)

        return Response({
            'plan': plan_serializer.data,
            'planned_expenses': planned_expenses_serializer.data,
            'unplanned_expenses': [],
            'applied_filter': status_filter
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiche generali sui piani di spesa della famiglia"""
        user = request.user

        if not user.family:
            return Response({
                'total_plans': 0,
                'active_plans': 0,
                'total_planned_amount': '0.00',
                'total_spent_amount': '0.00',
                'average_completion': 0.0
            })

        family_users = user.family.members.all()
        plans = SpendingPlan.objects.filter(users__in=family_users).distinct()

        total_plans = plans.count()
        active_plans = plans.filter(is_active=True).count()

        total_planned = sum(float(plan.get_total_planned_amount()) for plan in plans)
        total_spent = sum(float(plan.get_completed_expenses_amount()) for plan in plans)

        # Calcola la media di completamento
        completion_percentages = [float(plan.get_completion_percentage()) for plan in plans if plan.get_total_expenses_count() > 0]
        average_completion = sum(completion_percentages) / len(completion_percentages) if completion_percentages else 0.0

        return Response({
            'total_plans': total_plans,
            'active_plans': active_plans,
            'total_planned_amount': str(total_planned),
            'total_spent_amount': str(total_spent),
            'average_completion': round(average_completion, 2)
        })

    @action(detail=True, methods=['post'])
    def toggle_pin(self, request, pk=None):
        """Toggle lo stato pinnato di un piano di spesa per l'utente corrente"""
        from apps.reports.models import UserSpendingPlanPreference

        plan = self.get_object()
        user = request.user

        # Ottieni o crea la preferenza dell'utente per questo piano
        preference, created = UserSpendingPlanPreference.objects.get_or_create(
            user=user,
            spending_plan=plan,
            defaults={'is_pinned': False}
        )

        # Toggle del pin
        preference.is_pinned = not preference.is_pinned
        preference.save()

        # Aggiungi l'attributo is_pinned_by_user al piano per il serializer
        plan.is_pinned_by_user = preference.is_pinned

        serializer = self.get_serializer(plan)
        return Response({
            'detail': f'Piano {"pinnato" if preference.is_pinned else "spinnato"} con successo.',
            'is_pinned_by_user': preference.is_pinned,
            'plan': serializer.data
        })