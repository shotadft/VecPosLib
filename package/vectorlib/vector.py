# 標準ライブラリ
from typing import (
    Final,
    Generic,
    Iterator,
    List,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
    Optional,
)

# サードパーティライブラリ
from numba import njit, prange

try:
    import cupy as xp  # type: ignore

    _USE_CUPY = True
except ImportError:
    import numpy as xp

    _USE_CUPY = False

# ローカルモジュール
from ..positionlib.position import Position

# 型定義
Number = Union[float, int]
T = TypeVar("T", bound=Number)

# 型関連定数
_DEF_INT_KIND: Final = ("i",)

# 数値計算定数
_DEFAULT_TOLERANCE: Final = 1e-8
_MAX_VECTOR_LENGTH: Final = 1024


def _is_int(arr) -> bool:
    return getattr(arr, "dtype", None) is not None and arr.dtype.kind in _DEF_INT_KIND


def _to_number(v, is_int: bool) -> Number:
    return int(v) if is_int else float(v)


def _calc_reflection(a: Number, b: Number, c: Number, factor: Number = 2) -> float:
    """反射計算: a - b * factor * c"""
    return float(a - b * factor * c)


def _calc_projection(a: Number, b: Number) -> float:
    """投影計算: a * b"""
    return float(a * b)


def _calc_inverse(a: Number) -> float:
    """逆ベクトル計算: -a"""
    return float(-a)


def _angle_cosine(dot: float, norm1: float, norm2: float) -> float:
    """角度計算のためのcosine値を計算"""
    cos_theta = dot / (norm1 * norm2)
    return xp.acos(xp.clip(cos_theta, -1.0, 1.0))


def _reflect_vector(
    incident: "Vector", normal: "Vector", dot_product: float
) -> "Vector":
    """反射ベクトルを計算"""
    return incident - normal * 2 * dot_product


def _project_vector(normal: "Vector", dot_product: float) -> "Vector":
    """投影ベクトルを計算"""
    return normal * dot_product


def _reflect_coords(
    coords: Sequence[Number], normal_coords: Sequence[Number], dot_product: float
) -> List[float]:
    """反射座標を計算"""
    return [
        _calc_reflection(coord, dot_product, n_coord)
        for coord, n_coord in zip(coords, normal_coords)
    ]


def _project_coords(normal_coords: Sequence[Number], dot_product: float) -> List[float]:
    """投影座標を計算"""
    return [_calc_projection(n_coord, dot_product) for n_coord in normal_coords]


def _inverse_coords(coords: Sequence[Number]) -> List[float]:
    """逆ベクトル座標を計算"""
    return [_calc_inverse(coord) for coord in coords]


@njit(cache=True, parallel=True, fastmath=True)
def _norm_fast(arr) -> float:
    s = 0.0
    for i in prange(arr.size):
        s += arr[i] * arr[i]
    return s**0.5


def _norm(arr) -> float:
    if not _USE_CUPY and hasattr(arr, "dtype") and hasattr(arr, "sum"):
        return _norm_fast(arr)
    else:
        return float((arr * arr).sum() ** 0.5)


@njit(cache=True, parallel=True, fastmath=True)
def _dot_fast(a, b) -> float:
    s = 0.0
    for i in prange(a.size):
        s += a[i] * b[i]
    return s


def _dot(a, b) -> float:
    if not _USE_CUPY and hasattr(a, "dtype"):
        return _dot_fast(a, b)
    else:
        return float((a * b).sum())


class Vector(Generic[T]):
    def __init__(self, data: Union[Sequence[T], Position[T]]):
        if isinstance(data, Position):
            data = data.to_tuple()  # type: ignore

        if not 1 <= len(data) <= _MAX_VECTOR_LENGTH:
            raise ValueError(f"Vector length must be 1 to {_MAX_VECTOR_LENGTH}")

        has_float = any(isinstance(x, float) for x in data)
        dtype = float if has_float else int
        arr = xp.array(data, dtype=dtype)
        arr.setflags(write=False)

        self._vec, self._locked, self._is_int = arr, True, _is_int(arr)

    def _create_instance(self, data: Sequence[Number]) -> "Vector[float]":
        """新しいVectorインスタンスを作成するファクトリーメソッド"""
        return Vector[float](data)

    def _get_coord(self, index: int) -> T:
        """指定されたインデックスの座標を取得"""
        if index < 0 or index >= self._vec.size:
            raise IndexError(f"Coordinate index {index} out of range")
        v = self._vec[index]
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(v))
        else:
            return cast(T, float(v))

    def _from_array(self, arr: xp.ndarray) -> "Vector[float]":
        """配列から新しいVectorインスタンスを作成"""
        return self._create_instance(arr.tolist())

    def __setattr__(self, name, value):
        if (
            hasattr(self, "_locked")
            and self._locked
            and name not in {"_vec", "_locked", "_is_int"}
        ):
            raise AttributeError("Vector is immutable")
        super().__setattr__(name, value)

    @property
    def ndim(self) -> int:
        return self._vec.size

    def to_list(self) -> List[T]:
        target_type = int if self._is_int else float
        if target_type == int:
            return [cast(T, int(v)) for v in self._vec]
        else:
            return [cast(T, float(v)) for v in self._vec]

    def to_tuple(self) -> Tuple[T, ...]:
        target_type = int if self._is_int else float
        if target_type == int:
            return tuple(cast(T, int(v)) for v in self._vec)
        else:
            return tuple(cast(T, float(v)) for v in self._vec)

    def norm(self) -> float:
        return _norm(self._vec)

    def normalize(self) -> "Vector[float]":
        n = self.norm()
        if n == 0:
            raise ValueError("Cannot normalize zero vector")
        return self._from_array(self._vec / n)

    def dot(self, other: "Vector[T]") -> float:
        return _dot(self._vec, other._vec)

    def __add__(self, other: "Vector[T]") -> "Vector[float]":
        return self._create_instance((self._vec + other._vec).tolist())

    def __sub__(self, other: "Vector[T]") -> "Vector[float]":
        return self._create_instance((self._vec - other._vec).tolist())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_list()})"

    def __getitem__(self, idx: int) -> T:
        v = self._vec[idx]
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(v))
        else:
            return cast(T, float(v))

    def __len__(self) -> int:
        return self._vec.size

    def __iter__(self) -> Iterator[T]:
        is_int = self._is_int
        target_type = int if is_int else float
        if target_type == int:
            return (cast(T, int(v)) for v in self._vec)
        else:
            return (cast(T, float(v)) for v in self._vec)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return False
        return (self._vec == other._vec).all()

    def __mul__(self, scalar: Number) -> "Vector[float]":
        return Vector[float]((self._vec * scalar).tolist())

    def __rmul__(self, scalar: Number) -> "Vector[float]":
        return self.__mul__(scalar)

    def distance(self, other: "Vector[T]") -> float:
        diff = self._vec - other._vec
        return float((diff * diff).sum() ** 0.5)

    def manhattan(self, other: "Vector[T]") -> T:
        diff = abs(self._vec - other._vec)
        s = diff.sum()
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(s))
        else:
            return cast(T, float(s))

    def lerp(self, other: "Vector[T]", t: float) -> "Vector[float]":
        return self._from_array(self._vec * (1 - t) + other._vec * t)

    def clamp(self, min_val: Number, max_val: Number) -> "Vector[float]":
        arr = xp.clip(self._vec, min_val, max_val)
        return self._from_array(arr)

    def abs(self) -> "Vector[float]":
        arr = xp.abs(self._vec)
        return self._from_array(arr)

    def sum(self) -> T:
        s = self._vec.sum()
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(s))
        else:
            return cast(T, float(s))

    def prod(self) -> T:
        p = self._vec.prod()
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(p))
        else:
            return cast(T, float(p))

    def min(self) -> T:
        m = self._vec.min()
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(m))
        else:
            return cast(T, float(m))

    def max(self) -> T:
        m = self._vec.max()
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(m))
        else:
            return cast(T, float(m))

    def is_unit(self, tol: float = _DEFAULT_TOLERANCE) -> bool:
        return abs(self.norm() - 1.0) < tol

    def inverse(self) -> "Vector[float]":
        return self._from_array(-self._vec)

    def astype(self, dtype: type) -> "Vector[float]":
        arr = self._vec.astype(dtype)
        return self._from_array(arr)

    def reflect(self, normal: "Vector[T]") -> "Vector[float]":
        s, n = self.astype(float), normal.normalize()
        d = s.dot(n)
        return _reflect_vector(s, n, d).normalize() * s.norm()

    def project(self, other: "Vector[T]") -> "Vector[float]":
        s, n = self.astype(float), other.normalize()
        d = s.dot(n)
        return _project_vector(n, d)

    def angle_between(self, other: "Vector[T]") -> float:
        dot, norm1, norm2 = self.dot(other), self.norm(), other.norm()
        return _angle_cosine(dot, norm1, norm2)

    def _get_coord_property(self, index: int) -> T:
        """共通の座標プロパティ取得ヘルパー"""
        return self._get_coord(index)

    def _calc_inverse_coords(self) -> List[float]:
        """共通の逆ベクトル座標計算ヘルパー"""
        coords = [self._get_coord(i) for i in range(self._vec.size)]
        return _inverse_coords(coords)

    def _calc_reflect_coords(self, normal: "Vector[T]") -> List[float]:
        """共通の反射ベクトル座標計算ヘルパー"""
        n_vec = normal.normalize()
        n_coords = [n_vec[i] for i in range(self._vec.size)]
        d = sum(self._get_coord(i) * n_coords[i] for i in range(self._vec.size))
        coords = [self._get_coord(i) for i in range(self._vec.size)]
        return _reflect_coords(coords, n_coords, d)

    def _calc_project_coords(self, other: "Vector[T]") -> List[float]:
        """共通の投影ベクトル座標計算ヘルパー"""
        n_vec = other.normalize()
        n_coords = [n_vec[i] for i in range(self._vec.size)]
        d = sum(self._get_coord(i) * n_coords[i] for i in range(self._vec.size))
        return _project_coords(n_coords, d)


class Vec2(Vector[T]):
    @overload
    def __init__(self, x: Position[T], y: None = None): ...
    @overload
    def __init__(self, x: T, y: T): ...

    def __init__(self, x: Union[T, Position[T]], y: Optional[T] = None):
        if isinstance(x, Position):
            if len(x) != 2:
                raise ValueError
            super().__init__(x)
        else:
            if y is None:
                raise TypeError("y must not be None when x is not Position")
            super().__init__([x, y])

    def _create_instance(self, data: Sequence[Number]) -> "Vec2[float]":
        return Vec2[float](data[0], data[1])

    @property
    def x(self) -> T:
        return self._get_coord_property(0)

    @property
    def y(self) -> T:
        return self._get_coord_property(1)

    def cross(self, other: "Vec2[T]") -> T:
        result = self.x * other.y - self.y * other.x
        target_type = int if self._is_int else float
        if target_type == int:
            return cast(T, int(result))
        else:
            return cast(T, float(result))

    def angle(self, other: "Vec2[T]") -> float:
        dot = self.x * other.x + self.y * other.y
        norm1, norm2 = xp.sqrt(self.x**2 + self.y**2), xp.sqrt(other.x**2 + other.y**2)
        return _angle_cosine(dot, norm1, norm2)

    def inverse(self) -> "Vec2[float]":
        inverse_coords = self._calc_inverse_coords()
        return Vec2[float](*inverse_coords)

    def reflect(self, normal: "Vec2[T]") -> "Vec2[float]":  # type: ignore[override]
        reflection_coords = self._calc_reflect_coords(normal)
        return Vec2[float](*reflection_coords)

    def project(self, other: "Vec2[T]") -> "Vec2[float]":  # type: ignore[override]
        projection_coords = self._calc_project_coords(other)
        return Vec2[float](*projection_coords)


class Vec3(Vector[T]):
    @overload
    def __init__(self, x: Position[T], y: None = None, z: None = None): ...
    @overload
    def __init__(self, x: T, y: T, z: T): ...
    def __init__(
        self, x: Union[T, Position[T]], y: Optional[T] = None, z: Optional[T] = None
    ):
        if isinstance(x, Position):
            if len(x) != 3:
                raise ValueError
            super().__init__(x)
        else:
            if y is None or z is None:
                raise TypeError("y and z must not be None when x is not Position")
            super().__init__([x, y, z])

    def _create_instance(self, data: Sequence[Number]) -> "Vec3[float]":
        return Vec3[float](data[0], data[1], data[2])

    @property
    def x(self) -> T:
        return self._get_coord_property(0)

    @property
    def y(self) -> T:
        return self._get_coord_property(1)

    @property
    def z(self) -> T:
        return self._get_coord_property(2)

    def cross(self, other: "Vec3[T]") -> "Vec3[float]":
        cx = self.y * other.z - self.z * other.y
        cy = self.z * other.x - self.x * other.z
        cz = self.x * other.y - self.y * other.x
        return Vec3[float](float(cx), float(cy), float(cz))

    def angle(self, other: "Vec3[T]") -> float:
        dot = self.x * other.x + self.y * other.y + self.z * other.z
        norm1, norm2 = xp.sqrt(self.x**2 + self.y**2 + self.z**2), xp.sqrt(
            other.x**2 + other.y**2 + other.z**2
        )
        return _angle_cosine(dot, norm1, norm2)

    def inverse(self) -> "Vec3[float]":
        inverse_coords = self._calc_inverse_coords()
        return Vec3[float](*inverse_coords)

    def reflect(self, normal: "Vec3[T]") -> "Vec3[float]":  # type: ignore[override]
        reflection_coords = self._calc_reflect_coords(normal)
        return Vec3[float](*reflection_coords)

    def project(self, other: "Vec3[T]") -> "Vec3[float]":  # type: ignore[override]
        projection_coords = self._calc_project_coords(other)
        return Vec3[float](*projection_coords)


class Vec4(Vector[T]):
    @overload
    def __init__(
        self, x: Position[T], y: None = None, z: None = None, w: None = None
    ): ...
    @overload
    def __init__(self, x: T, y: T, z: T, w: T): ...
    def __init__(
        self,
        x: Union[T, Position[T]],
        y: Optional[T] = None,
        z: Optional[T] = None,
        w: Optional[T] = None,
    ):
        if isinstance(x, Position):
            if len(x) != 4:
                raise ValueError
            super().__init__(x)
        else:
            if y is None or z is None or w is None:
                raise TypeError("y, z, w must not be None when x is not Position")
            super().__init__([x, y, z, w])

    def _create_instance(self, data: Sequence[Number]) -> "Vec4[float]":
        return Vec4[float](data[0], data[1], data[2], data[3])

    @property
    def x(self) -> T:
        return self._get_coord_property(0)

    @property
    def y(self) -> T:
        return self._get_coord_property(1)

    @property
    def z(self) -> T:
        return self._get_coord_property(2)

    @property
    def w(self) -> T:
        return self._get_coord_property(3)

    def inverse(self) -> "Vec4[float]":
        inverse_coords = self._calc_inverse_coords()
        return Vec4[float](*inverse_coords)

    def reflect(self, normal: "Vec4[T]") -> "Vec4[float]":  # type: ignore[override]
        reflection_coords = self._calc_reflect_coords(normal)
        return Vec4[float](*reflection_coords)

    def project(self, other: "Vec4[T]") -> "Vec4[float]":  # type: ignore[override]
        projection_coords = self._calc_project_coords(other)
        return Vec4[float](*projection_coords)
