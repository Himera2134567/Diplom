import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import Order

class Command(BaseCommand):
    help = "Populate the Order table with 100 random orders over the last year"

    def handle(self, *args, **options):
        Order.objects.all().delete()
        base_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365)
        for i in range(100):
            # разброс по 12 месяцам
            created = base_date + timedelta(days=random.randint(0, 365))
            amount = random.randint(10_000, 500_000) / 100.0
            # допустим, profit = 30% ± 10%
            profit = amount * (0.3 + (random.random() - 0.5) * 0.2)
            Order.objects.create(
                created_at=created,
                amount=amount,
                profit=round(profit, 2),
            )
        self.stdout.write(self.style.SUCCESS("✓ 100 orders created"))
