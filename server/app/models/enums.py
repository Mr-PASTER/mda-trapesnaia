import enum


class UserRole(str, enum.Enum):
    eater = "eater"
    admin = "admin"
    accountant = "accountant"
    operator = "operator"


class MealKind(str, enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    snack = "snack"
    dinner = "dinner"
