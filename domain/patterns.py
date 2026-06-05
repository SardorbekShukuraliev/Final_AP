from abc import ABC, abstractmethod
from typing import List
from .models import MenuItem, Allergen

# ---- Factory Method для категорий меню ----
class MenuItemFactory(ABC):
    @abstractmethod
    def create_item(self, name: str, base_price: float, **kwargs) -> MenuItem:
        pass

class StarterFactory(MenuItemFactory):
    def create_item(self, name, base_price, **kwargs):
        return MenuItem(name=name, base_price=base_price, category="Starter")

class MainFactory(MenuItemFactory):
    def create_item(self, name, base_price, **kwargs):
        return MenuItem(name=name, base_price=base_price, category="Main")

class DessertFactory(MenuItemFactory):
    def create_item(self, name, base_price, **kwargs):
        return MenuItem(name=name, base_price=base_price, category="Dessert")

class BeverageFactory(MenuItemFactory):
    def create_item(self, name, base_price, **kwargs):
        return MenuItem(name=name, base_price=base_price, category="Beverage")

# ---- Decorator для кастомизации блюд ----
class MenuItemDecorator(MenuItem, ABC):
    def __init__(self, base: MenuItem):
        super().__init__(id=base.id, name=base.name, base_price=base.base_price, category=base.category)
        self._base = base

    @abstractmethod
    def get_price(self) -> float:
        pass

class ExtraIngredient(MenuItemDecorator):
    def __init__(self, base: MenuItem, ingredient_name: str, extra_cost: float):
        super().__init__(base)
        self.ingredient = ingredient_name
        self.extra_cost = extra_cost

    def get_price(self):
        return self._base.base_price + self.extra_cost

class AllergenFlagDecorator(MenuItemDecorator):
    def __init__(self, base: MenuItem, allergen: Allergen):
        super().__init__(base)
        self.allergen = allergen

    def get_price(self):
        return self._base.base_price

# ---- Composite для комбо-сетов ----
class MenuComponent(ABC):
    @abstractmethod
    def get_price(self) -> float:
        pass

class SingleItem(MenuComponent):
    def __init__(self, item: MenuItem):
        self.item = item

    def get_price(self) -> float:
        return self.item.base_price

class ComboSet(MenuComponent):
    def __init__(self, name: str, discount: float = 0.0):
        self.name = name
        self.children: List[MenuComponent] = []
        self.discount = discount

    def add(self, component: MenuComponent):
        self.children.append(component)

    def get_price(self) -> float:
        total = sum(c.get_price() for c in self.children)
        return total * (1 - self.discount)

# ---- Strategy для ценообразования ----
class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, base_total: float) -> float:
        pass

class HappyHourStrategy(PricingStrategy):
    def calculate(self, base_total: float) -> float:
        return base_total * 0.85  # 15% скидка

class LoyaltyCardStrategy(PricingStrategy):
    def calculate(self, base_total: float) -> float:
        return base_total * 0.9   # 10% скидка

class GroupDiscountStrategy(PricingStrategy):
    def calculate(self, base_total: float) -> float:
        return base_total * 0.8   # 20% скидка для больших компаний

# ---- Facade для биллинга ----
class BillingFacade:
    def __init__(self, strategy: PricingStrategy = None):
        self.strategy = strategy or HappyHourStrategy()   # по умолчанию

    def calculate_total(self, items_total: float, tax_rate: float = 0.18, service_charge: float = 0.1) -> float:
        discounted = self.strategy.calculate(items_total)
        tax = discounted * tax_rate
        service = discounted * service_charge
        return discounted + tax + service