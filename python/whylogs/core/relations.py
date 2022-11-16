import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Optional, Union


class ValueGetter(ABC):
    @abstractmethod
    def __call__(self) -> Union[str, int, float]:
        raise NotImplementedError

    @abstractmethod
    def serialize(self) -> str:
        raise NotImplementedError


class LiteralGetter(ValueGetter):
    def __init__(self, value: Union[str, int, float]) -> None:
        self._literal = value

    def __call__(self) -> Union[str, int, float]:
        return self._literal

    def serialize(self) -> str:
        if isinstance(self._literal, str):
            return f'"{self._literal}"'
        return str(self._literal)


class Relation(Enum):
    no_op = 0
    match = 1
    fullmatch = 2
    equal = 3
    less = 4
    leq = 5
    greater = 6
    geq = 7
    neq = 8
    _and = 9
    _or = 10
    _not = 11
    _udf = 12


_TOKEN = ["", "~", "~=", "==", "<", "<=", ">", ">=", "!=", "and", "or", "not", "udf"]


class Predicate:
    def __init__(
        self,
        op: Relation = Relation.no_op,
        value: Union[str, int, float, ValueGetter] = 0,
        udf: Optional[Callable[[Any], bool]] = None,
        left: Optional["Predicate"] = None,
        right: Optional["Predicate"] = None,
    ):
        self._op = op
        self._udf = udf
        if op in {Relation.match, Relation.fullmatch}:
            if not isinstance(value, str):
                raise ValueError("match requires a string regular expression argument")
            self._re = re.compile(value)

        if isinstance(value, (str, int, float)):
            self._value = LiteralGetter(value)
        else:
            self._value = value  # type: ignore

        if op in {Relation._and, Relation._or}:
            if not left and right:
                raise ValueError("boolean operators require two operands")
        self._left = left
        self._right = right

        if op == Relation._not:
            self._right = right

    def __call__(self, x: Any) -> bool:
        op = self._op
        if op == Relation.match:
            return isinstance(x, str) and bool(self._re.match(x))
        if op == Relation.fullmatch:
            return isinstance(x, str) and bool(self._re.fullmatch(x))

        value = self._value()
        if op == Relation.equal:
            return x == value
        if op == Relation.less:
            return x < value
        if op == Relation.leq:
            return x <= value
        if op == Relation.greater:
            return x > value
        if op == Relation.geq:
            return x >= value
        if op == Relation.neq:
            return x != value
        if op == Relation._udf:
            return self._udf(x)  # type: ignore
        if op == Relation._and:
            return self._left(x) and self._right(x)  # type: ignore
        if op == Relation._or:
            return self._left(x) or self._right(x)  # type: ignore
        if op == Relation._not:
            if not self._right:
                raise ValueError("negation operator requires a predicate to negate")
            return not self._right(x)  # type: ignore

        raise ValueError("Unknown predicate")

    def _maybe_not(self, op: Relation, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        pred = Predicate(op, value)
        if self._op == Relation._not and self._right is None:
            return Predicate(Relation._not, right=pred)
        return pred

    def matches(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.match, value)

    def fullmatch(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.fullmatch, value)

    def equals(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.equal, value)

    def less_than(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.less, value)

    def less_or_equals(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.leq, value)

    def greater_than(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.greater, value)

    def greater_or_equals(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.geq, value)

    def not_equal(self, value: Union[str, int, float, ValueGetter]) -> "Predicate":
        return self._maybe_not(Relation.neq, value)

    def and_(self, right: "Predicate") -> "Predicate":
        return Predicate(Relation._and, left=self, right=right)

    def or_(self, right: "Predicate") -> "Predicate":
        return Predicate(Relation._or, left=self, right=right)

    def is_(self, udf: Callable[[Any], bool]) -> "Predicate":
        pred = Predicate(Relation._udf, udf=udf)
        if self._op == Relation._not and self._right is None:
            return Predicate(Relation._not, right=pred)
        return pred

    @property
    def not_(self) -> "Predicate":
        return Predicate(Relation._not)

    def serialize(self) -> str:
        if not (self._left or self._right):
            return f"{_TOKEN[self._op.value]} x {self._value.serialize()}"
        if self._op == Relation._not:
            return f"not {self._right.serialize()}"  # type: ignore
        return f"{_TOKEN[self._op.value]} {self._left.serialize()} {self._right.serialize()}"  # type: ignore

    def __str__(self) -> str:
        if not (self._left or self._right):
            return f"x {_TOKEN[self._op.value]} {self._value.serialize()}"
        if self._op == Relation._not:
            return f"not {str(self._right)}"
        return f"({str(self._left)}) {_TOKEN[self._op.value]} ({str(self._right)})"


def Not(p: Predicate) -> Predicate:
    return Predicate(Relation._not, right=p)
