import json
import datetime
from typing import List, Dict, Optional, Any


class LimitExceededError(Exception):
    pass
class Subscription:
    def __init__(
        self,
        title: str,
        cost: float,
        category: str,
        next_billing_date: datetime.date,
        is_active: bool = True
    ):
        self.title = title
        self.cost = cost
        self.category = category
        self.next_billing_date = next_billing_date
        self.is_active = is_active

    def get_days_left(self) -> int:
        today = datetime.date.today()
        delta = self.next_billing_date - today
        return delta.days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "cost": self.cost,
            "category": self.category,
            "next_billing_date": self.next_billing_date.strftime("%Y-%m-%d"),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        return cls(
            title=data["title"],
            cost=data["cost"],
            category=data["category"],
            next_billing_date=datetime.datetime.strptime(
                data["next_billing_date"], "%Y-%m-%d"
            ).date(),
            is_active=data.get("is_active", True),
        )
    def __str__(self) -> str:
        status = "Активна" if self.is_active else "Приостановлена"
        days_left = self.get_days_left()
        return (
            f"[{status}] {self.title} | {self.category} | "
            f"{self.cost:.2f} ₽ | Следующее списание: {self.next_billing_date} "
            f"({days_left} дн.)"
        )

class Expense:
    def __init__(
        self,
        amount: float,
        category: str,
        description: str = "",
        date: Optional[datetime.date] = None
    ):
        self.amount = amount
        self.category = category
        self.date = date or datetime.date.today()
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "amount": self.amount,
            "category": self.category,
            "date": self.date.strftime("%Y-%m-%d"),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Expense":
        return cls(
            amount=data["amount"],
            category=data["category"],
            description=data.get("description", ""),
            date=datetime.datetime.strptime(data["date"], "%Y-%m-%d").date(),
        )


class FinanceTracker:
    def __init__(self):
        self.balance: float = 0.0
        self.limits: Dict[str, float] = {}
        self.subscriptions: List[Subscription] = []
        self.expenses: List[Expense] = []

    def set_balance(self, amount: float) -> None:
        self.balance = amount
    #Устанавливает или обновляет лимит для конкретной категории
    def set_limit(self, category: str, amount: float) -> None:
        if amount < 0:
            raise ValueError("Лимит не может быть отрицательным.")
        self.limits[category] = amount

    def add_subscription(
        self,
        title: str,
        cost: float,
        category: str,
        next_billing_date: datetime.date
    ) -> None:
        sub = Subscription(title, cost, category, next_billing_date)
        self.subscriptions.append(sub)

    def remove_subscription(self, title: str) -> bool:
        for i, sub in enumerate(self.subscriptions):
            if sub.title == title:
                del self.subscriptions[i]
                return True
        return False

    def get_safe_balance(self) -> float:
        today = datetime.date.today()
        deduction = 0.0
        for sub in self.subscriptions:
            if not sub.is_active:
                continue
            days_left = (sub.next_billing_date - today).days
            if days_left <= 7:
                deduction += sub.cost
        return self.balance - deduction

    def _get_current_month_expenses_by_category(self) -> Dict[str, float]:
        today = datetime.date.today()
        result: Dict[str, float] = {}
        for e in self.expenses:
            if e.date.year == today.year and e.date.month == today.month:
                result[e.category] = result.get(e.category, 0.0) + e.amount
        return result

    def add_expense(
        self,
        amount: float,
        category: str,
        description: str = "",
        date: Optional[datetime.date] = None
    ) -> Optional[str]:
        if amount <= 0:
            raise ValueError("Сумма расхода должна быть положительной.")

        current_month_totals = self._get_current_month_expenses_by_category()
        current_total = current_month_totals.get(category, 0.0)
        limit = self.limits.get(category)

        if limit is not None and current_total + amount > limit:
            excess = (current_total + amount) - limit
            raise LimitExceededError(
                f"Бюджет превышен! Вы вышли за рамки лимита по категории "
                f"{category} на {excess:.2f} рублей!"
            )

        warning_msg = None
        if limit is not None:
            threshold = limit * 0.8
            if current_total + amount >= threshold:
                warning_msg = (
                    f"Внимание! Вы исчерпали 80% бюджета по категории {category}."
                )

        expense = Expense(amount, category, description, date)
        self.expenses.append(expense)
        self.balance -= amount

        return warning_msg


    def process_auto_billings(self) -> List[str]:
        logs: List[str] = []
        today = datetime.date.today()

        for sub in self.subscriptions:
            while sub.is_active and sub.next_billing_date <= today:
                if self.balance >= sub.cost:
                    self.balance -= sub.cost
                    expense = Expense(
                        amount=sub.cost,
                        category="Подписки",
                        description=f"Автосписание: {sub.title}",
                        date=today,
                    )
                    self.expenses.append(expense)
                    logs.append(
                        f"Списано: {sub.cost:.2f} ₽ за подписку {sub.title}. "
                        f"Новый баланс: {self.balance:.2f} ₽"
                    )
                    sub.next_billing_date = self._add_one_month(sub.next_billing_date)
                else:
                    sub.is_active = False
                    logs.append(
                        f"Ошибка автосписания: подписка {sub.title} приостановлена. "
                        f"Недостаточно средств!"
                    )
                    break
        return logs

    @staticmethod
    def _add_one_month(date: datetime.date) -> datetime.date:
        month = date.month + 1
        year = date.year
        if month > 12:
            month = 1
            year += 1
        day = min(date.day, 28)
        try:
            return datetime.date(year, month, date.day)
        except ValueError:
            if month == 12:
                next_month_first = datetime.date(year + 1, 1, 1)
            else:
                next_month_first = datetime.date(year, month + 1, 1)
            last_day = next_month_first - datetime.timedelta(days=1)
            return last_day

    def get_monthly_forecast(self) -> float:
        today = datetime.date.today()
        forecast = 0.0
        for sub in self.subscriptions:
            if not sub.is_active:
                continue
            delta_days = (sub.next_billing_date - today).days
            if 0 <= delta_days <= 30:
                forecast += sub.cost
        return forecast

    def get_category_stats(self) -> Dict[str, Dict[str, Any]]:
        today = datetime.date.today()
        totals: Dict[str, float] = {}

        for e in self.expenses:
            if e.date.year == today.year and e.date.month == today.month:
                totals[e.category] = totals.get(e.category, 0.0) + e.amount

        overall_sum = sum(totals.values())
        stats: Dict[str, Dict[str, Any]] = {}

        for cat, total in totals.items():
            percent = (total / overall_sum * 100) if overall_sum > 0 else 0.0
            limit = self.limits.get(cat)
            remaining = None
            if limit is not None:
                remaining = limit - total
            stats[cat] = {
                "sum": total,
                "percent": percent,
                "limit": limit,
                "remaining": remaining,
            }
        return stats


    def to_dict(self) -> Dict[str, Any]:
        return {
            "balance": self.balance,
            "limits": self.limits,
            "subscriptions": [s.to_dict() for s in self.subscriptions],
            "expenses": [e.to_dict() for e in self.expenses],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FinanceTracker":
        tracker = cls()
        tracker.balance = data.get("balance", 0.0)
        tracker.limits = data.get("limits", {})
        tracker.subscriptions = [
            Subscription.from_dict(s) for s in data.get("subscriptions", [])
        ]
        tracker.expenses = [
            Expense.from_dict(e) for e in data.get("expenses", [])
        ]
        return tracker

    @staticmethod
    def load(filepath: str = "wallet.json") -> "FinanceTracker":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return FinanceTracker.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError):
            return FinanceTracker()

    def save(self, filepath: str = "wallet.json") -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def get_float_input(prompt: str) -> float:
    while True:
        try:
            value = input(prompt)
            return float(value)
        except ValueError:
            print("Пожалуйста, введите корректное число.")


def get_int_input(prompt: str) -> int:
    while True:
        try:
            value = input(prompt)
            return int(value)
        except ValueError:
            print("Пожалуйста, введите корректное целое число.")


def parse_date_input(prompt: str) -> datetime.date:
    while True:
        s = input(prompt + " (формат YYYY-MM-DD): ").strip()
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            print("Неверный формат даты. Используйте YYYY-MM-DD.")


def main():
    filepath = "wallet.json"
    tracker = FinanceTracker.load(filepath)

    logs = tracker.process_auto_billings()
    if logs:
        print("\n=== Уведомления при старте ===")
        for log in logs:
            print(log)
        print()

    while True:
        print("\n--- SmartWallet: Главное меню ---")
        print("1. Показать текущее состояние")
        print("2. Добавить разовый расход")
        print("3. Управление подписками")
        print("4. Финансовый отчет и прогноз")
        print("5. Пополнить баланс")
        print("6. Выход")

        choice = input("Выберите пункт (1-6): ").strip()

        if choice == "1":
            print(f"\nТекущий баланс: {tracker.balance:.2f} ₽")
            print(f"Безопасный баланс (минус подписки ≤7 дн.): {tracker.get_safe_balance():.2f} ₽")
            print("\nАктивные подписки:")
            if tracker.subscriptions:
                for sub in tracker.subscriptions:
                    print(sub)
            else:
                print("Подписок нет.")

        elif choice == "2":
            try:
                amount = get_float_input("Сумма расхода: ")
                category = input("Категория: ").strip()
                description = input("Комментарий (необязательно): ").strip()
                warn = tracker.add_expense(amount, category, description)
                print(f"Расход добавлен. Текущий баланс: {tracker.balance:.2f} ₽")
                if warn:
                    print(warn)
            except LimitExceededError as e:
                print(str(e))
            except Exception as e:
                print(f"Ошибка: {e}")

        elif choice == "3":
            sub_choice = input("\n3. Управление подписками\n"
                               "a) Добавить подписку\nb) Удалить подписку\nВыберите (a/b): ").strip().lower()
            if sub_choice == "a":
                title = input("Название подписки: ").strip()
                cost = get_float_input("Стоимость за период: ")
                category = input("Категория: ").strip()
                next_date = parse_date_input("Дата следующего списания")
                tracker.add_subscription(title, cost, category, next_date)
                print("Подписка добавлена.")
            elif sub_choice == "b":
                title = input("Название подписки для удаления: ").strip()
                if tracker.remove_subscription(title):
                    print("Подписка удалена.")
                else:
                    print("Подписка с таким названием не найдена.")
            else:
                print("Неверная опция.")

        elif choice == "4":
            forecast = tracker.get_monthly_forecast()
            print(f"\nПрогноз трат на подписки (ближайшие 30 дней): {forecast:.2f} ₽")

            stats = tracker.get_category_stats()
            if stats:
                print("\nСтатистика по категориям (текущий месяц):")
                for cat, data in stats.items():
                    rem = data["remaining"]
                    rem_str = f"{rem:.2f} ₽" if rem is not None else "лимит не установлен"
                    print(
                        f"{cat}: {data['sum']:.2f} ₽ "
                        f"({data['percent']:.1f}% от общих трат), остаток лимита: {rem_str}"
                    )
            else:
                print("трат еще не было")

        elif choice == "5":
            amount = get_float_input("Сумма пополнения: ")
            if amount <= 0:
                print("Сумма пополнения должна быть положительной.")
            else:
                tracker.set_balance(tracker.balance + amount)
                print(f"Баланс пополнен. Новый баланс: {tracker.balance:.2f} ₽")

        elif choice == "6":
            tracker.save()
            print("Данные сохранены. До свидания!")
            break
if __name__ == "__main__":
    main()