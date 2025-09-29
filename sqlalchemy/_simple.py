from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, Iterator, List, Sequence, Tuple, TypeVar

__all__ = [
    "Boolean",
    "Date",
    "DateTime",
    "ForeignKey",
    "Integer",
    "Numeric",
    "String",
    "Text",
    "Mapped",
    "DeclarativeBase",
    "mapped_column",
    "relationship",
    "Session",
    "sessionmaker",
    "create_engine",
    "select",
    "func",
]


class _Type:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - debug helper
        self.args = args
        self.kwargs = kwargs


class Boolean(_Type):
    pass


class Date(_Type):
    pass


class DateTime(_Type):
    pass


class Integer(_Type):
    pass


class Numeric(_Type):
    pass


class String(_Type):
    pass


class Text(_Type):
    pass


class ForeignKey:
    def __init__(self, target: str) -> None:
        self.target = target


Mapped = TypeVar("Mapped")


class Ordering:
    def __init__(self, column: "ColumnExpression", *, descending: bool = False) -> None:
        self.column = column
        self.descending = descending

    def evaluate(self, obj: Any) -> Any:
        return self.column.evaluate(obj)


class ColumnExpression:
    def __init__(self, model: type, name: str) -> None:
        self.model = model
        self.name = name

    def evaluate(self, obj: Any) -> Any:
        return getattr(obj, self.name)

    def desc(self) -> Ordering:
        return Ordering(self, descending=True)

    def asc(self) -> Ordering:
        return Ordering(self, descending=False)

    def __eq__(self, other: Any) -> "Condition":  # type: ignore[override]
        return Condition(lambda obj: self.evaluate(obj) == other)

    def __ne__(self, other: Any) -> "Condition":  # type: ignore[override]
        return Condition(lambda obj: self.evaluate(obj) != other)

    def __lt__(self, other: Any) -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) < other)

    def __le__(self, other: Any) -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) <= other)

    def __gt__(self, other: Any) -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) > other)

    def __ge__(self, other: Any) -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) >= other)

    def is_(self, value: Any) -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) is value)

    def is_not(self, value: Any) -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) is not value)


class Condition:
    def __init__(self, predicate: Callable[[Any], bool]) -> None:
        self.predicate = predicate

    def evaluate(self, obj: Any) -> bool:
        return self.predicate(obj)


class Column:
    def __init__(
        self,
        *,
        default: Any | None = None,
        primary_key: bool = False,
        onupdate: Callable[[], Any] | None = None,
        nullable: bool = True,
        index: bool = False,
    ) -> None:
        self.default = default
        self.primary_key = primary_key
        self.onupdate = onupdate
        self.nullable = nullable
        self.index = index
        self.name: str | None = None
        self.model: type | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self.model = owner

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            if owner is None:
                raise AttributeError("Column accessed without owner")
            return ColumnExpression(owner, self.name or "")
        return instance.__dict__.get(self.name, None)

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__[self.name] = value

    def get_default(self) -> Any:
        if callable(self.default):
            return self.default()
        return self.default


def mapped_column(*args: Any, **kwargs: Any) -> Column:
    return Column(**kwargs)


class Relationship:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.setdefault(self.name, [])

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__[self.name] = value


def relationship(*args: Any, **kwargs: Any) -> Relationship:
    return Relationship()


class Metadata:
    def __init__(self) -> None:
        self.tables: list[type] = []

    def create_all(self, engine: "Engine") -> None:
        engine.create_all(self.tables)


class DeclarativeMeta(type):
    def __new__(mcls, name: str, bases: Tuple[type, ...], attrs: Dict[str, Any]):
        columns = {k: v for k, v in attrs.items() if isinstance(v, Column)}
        relationships = {k: v for k, v in attrs.items() if isinstance(v, Relationship)}
        cls = super().__new__(mcls, name, bases, attrs)

        all_columns: Dict[str, Column] = {}
        all_relationships: Dict[str, Relationship] = {}
        for base in bases:
            if isinstance(base, DeclarativeMeta):
                all_columns.update(getattr(base, "_all_columns", {}))
                all_relationships.update(getattr(base, "_all_relationships", {}))
        all_columns.update(columns)
        all_relationships.update(relationships)

        cls._columns = columns
        cls._all_columns = all_columns
        cls._relationships = relationships
        cls._all_relationships = all_relationships
        primary_keys = [name for name, col in all_columns.items() if col.primary_key]
        cls.__primary_key__ = primary_keys[0] if primary_keys else None

        base_with_meta = None
        for base in bases:
            if isinstance(base, DeclarativeMeta):
                base_with_meta = base
                break

        if base_with_meta is None:
            cls.metadata = Metadata()
        else:
            cls.metadata = base_with_meta.metadata
            cls.metadata.tables.append(cls)
        return cls


class DeclarativeBase(metaclass=DeclarativeMeta):
    metadata: Metadata

    def __init__(self, **kwargs: Any) -> None:
        cls = self.__class__
        remaining = dict(kwargs)
        for name, column in cls._all_columns.items():
            if name in remaining:
                value = remaining.pop(name)
            else:
                value = column.get_default()
            setattr(self, name, value)
        for name in cls._all_relationships:
            setattr(self, name, remaining.pop(name, []))
        for name, value in remaining.items():
            setattr(self, name, value)


class Engine:
    def __init__(self, url: str, *, connect_args: Dict[str, Any] | None = None) -> None:
        self.url = url
        self.connect_args = connect_args or {}
        self.store: Dict[type, List[Any]] = defaultdict(list)
        self.next_ids: Dict[type, int] = defaultdict(int)

    def create_all(self, tables: Iterable[type]) -> None:
        for table in tables:
            self.store.setdefault(table, [])
            self.next_ids.setdefault(table, 0)


def create_engine(url: str, *, connect_args: Dict[str, Any] | None = None) -> Engine:
    return Engine(url, connect_args=connect_args)


class sessionmaker:
    def __init__(self, engine: Engine, *, expire_on_commit: bool | None = None) -> None:
        self.engine = engine

    def __call__(self) -> "Session":
        return Session(self.engine)


class ScalarResult(Iterable[Any]):
    def __init__(self, data: List[Any]) -> None:
        self._data = data

    def all(self) -> List[Any]:
        return list(self._data)

    def first(self) -> Any:
        return self._data[0] if self._data else None

    def one(self) -> Any:
        if len(self._data) != 1:
            raise ValueError("Expected exactly one result")
        return self._data[0]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)


class Result(Iterable[Tuple[Any, ...]]):
    def __init__(self, rows: List[Tuple[Any, ...]]) -> None:
        self._rows = rows

    def all(self) -> List[Tuple[Any, ...]]:
        return list(self._rows)

    def __iter__(self) -> Iterator[Tuple[Any, ...]]:
        return iter(self._rows)


class AggregateExpression:
    def __init__(self, func_name: str, column: ColumnExpression) -> None:
        self.func_name = func_name
        self.column = column

    def evaluate(self, items: Sequence[Any]) -> Any:
        values = [self.column.evaluate(item) for item in items]
        if self.func_name == "sum":
            total = Decimal("0")
            for value in values:
                if value is None:
                    continue
                total += value
            return total
        raise ValueError(f"Unsupported aggregate function {self.func_name}")


class Select:
    def __init__(self, *entities: Any) -> None:
        if not entities:
            raise ValueError("Select requires at least one entity")
        self._entities: List[Any] = list(entities)
        self._where: List[Condition] = []
        self._order_by: List[Ordering] = []
        self._group_by: List[ColumnExpression] = []

    def where(self, *conditions: Condition) -> "Select":
        self._where.extend(conditions)
        return self

    def order_by(self, *orderings: ColumnExpression | Ordering) -> "Select":
        for ordering in orderings:
            if isinstance(ordering, Ordering):
                self._order_by.append(ordering)
            else:
                self._order_by.append(ordering.asc())
        return self

    def group_by(self, *columns: ColumnExpression) -> "Select":
        self._group_by.extend(columns)
        return self

    def _resolve_model(self) -> type:
        for entity in self._entities:
            if isinstance(entity, type) and issubclass(entity, DeclarativeBase):
                return entity
            if isinstance(entity, ColumnExpression):
                return entity.model
            if isinstance(entity, AggregateExpression):
                return entity.column.model
        raise ValueError("Unable to resolve model for select")


def select(*entities: Any) -> Select:
    return Select(*entities)


class FuncRegistry:
    def sum(self, expression: ColumnExpression) -> AggregateExpression:
        return AggregateExpression("sum", expression)


func = FuncRegistry()


class Session:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._new: List[Any] = []

    def add(self, obj: Any) -> None:
        if obj not in self._new and obj not in self.engine.store[type(obj)]:
            self._new.append(obj)

    def add_all(self, objs: Sequence[Any]) -> None:
        for obj in objs:
            self.add(obj)

    def flush(self) -> None:
        for obj in list(self._new):
            cls = type(obj)
            pk_name = getattr(cls, "__primary_key__", None)
            if pk_name and getattr(obj, pk_name) is None:
                next_id = self.engine.next_ids[cls] + 1
                setattr(obj, pk_name, next_id)
                self.engine.next_ids[cls] = next_id
            self.engine.store[cls].append(obj)
            self._new.remove(obj)

    def commit(self) -> None:
        self.flush()

    def rollback(self) -> None:
        self._new.clear()

    def close(self) -> None:  # pragma: no cover - simple no-op
        pass

    def refresh(self, obj: Any) -> None:  # pragma: no cover - no-op
        pass

    def get(self, cls: type, identity: Any) -> Any:
        self.flush()
        pk_name = getattr(cls, "__primary_key__", None)
        if pk_name is None:
            return None
        for obj in self.engine.store.get(cls, []):
            if getattr(obj, pk_name) == identity:
                return obj
        return None

    def delete(self, obj: Any) -> None:
        cls = type(obj)
        collection = self.engine.store.get(cls, [])
        if obj in collection:
            collection.remove(obj)

    def scalars(self, stmt: Select) -> ScalarResult:
        self.flush()
        rows = self._run_select(stmt)
        values = [row[0] for row in rows]
        return ScalarResult(values)

    def execute(self, stmt: Select) -> Result:
        self.flush()
        rows = self._run_select(stmt)
        return Result(rows)

    def _apply_where(self, data: List[Any], stmt: Select) -> List[Any]:
        if not stmt._where:
            return data
        filtered = []
        for obj in data:
            if all(condition.evaluate(obj) for condition in stmt._where):
                filtered.append(obj)
        return filtered

    def _run_select(self, stmt: Select) -> List[Tuple[Any, ...]]:
        model = stmt._resolve_model()
        data = list(self.engine.store.get(model, []))
        data = self._apply_where(data, stmt)
        if stmt._order_by:
            for ordering in reversed(stmt._order_by):
                data.sort(
                    key=lambda obj, ord=ordering: ord.evaluate(obj),
                    reverse=ordering.descending,
                )
        if stmt._group_by:
            groups: Dict[Tuple[Any, ...], List[Any]] = defaultdict(list)
            for obj in data:
                key = tuple(column.evaluate(obj) for column in stmt._group_by)
                groups[key].append(obj)
            rows: List[Tuple[Any, ...]] = []
            for key, items in groups.items():
                row = []
                for entity in stmt._entities:
                    row.append(self._evaluate_group_entity(entity, items))
                rows.append(tuple(row))
            return rows
        rows = []
        for obj in data:
            row = []
            for entity in stmt._entities:
                row.append(self._evaluate_entity(entity, obj))
            rows.append(tuple(row))
        return rows

    def _evaluate_entity(self, entity: Any, obj: Any) -> Any:
        if isinstance(entity, type) and issubclass(entity, DeclarativeBase):
            return obj
        if isinstance(entity, ColumnExpression):
            return entity.evaluate(obj)
        if isinstance(entity, AggregateExpression):
            return entity.evaluate([obj])
        return entity

    def _evaluate_group_entity(self, entity: Any, items: Sequence[Any]) -> Any:
        if isinstance(entity, AggregateExpression):
            return entity.evaluate(items)
        if isinstance(entity, ColumnExpression):
            if not items:
                return None
            return entity.evaluate(items[0])
        if isinstance(entity, type) and issubclass(entity, DeclarativeBase):
            return items[0] if items else None
        return entity


