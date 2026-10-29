class Enum:
    def __init__(self, name):
        self.name = name

    def __or__(self, other):
        return Enum(f"{self.name}|{other.name}")

    def __and__(self, other):
        return Enum(f"{self.name}&{other.name}")

    def __bool__(self):
        return True

    def __eq__(self, other):                         # the same member of an enumeration is equal to itself (also if asked for twice)
        return isinstance(other, Enum) and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return self.name


class EnumGroup:
    def __init__(self, group, names):
        self._group, self._names = group, set(names)

    def __getattr__(self, name):
        if name not in self._names:
            raise AttributeError(f"Qt enumeration {self._group} has no member {name!r}")
        return Enum(f"{self._group}.{name}")


class Signal:
    def __init__(self):
        self.handlers = []

    def connect(self, fn):
        self.handlers.append(fn)

    def emit(self, *args):
        for h in list(self.handlers):
            h(*args)


# Methods whose first argument must be a Qt enumeration (PySide6 rejects a plain number with a TypeError)
ENUM_ARG_METHODS = {"setHorizontalScrollBarPolicy", "setVerticalScrollBarPolicy", "setLineWrapMode", "setFrameShape",
                    "setFrameShadow", "setAlignment", "setWindowFlag", "setSizeConstraint", "setEchoMode", "setSizePolicy", "setElideMode", "setLabelAlignment"}


class Base:
    methods: set = set()
    signals: set = set()

    @classmethod
    def _api(cls, attr):
        out = set()
        for k in cls.__mro__:
            out |= getattr(k, attr, set()) if attr in k.__dict__ else set()
        return out

    def __init__(self, *args, **kwargs):
        for given in (*args, *kwargs.values()):                 # like Qt (shiboken): an object whose base class is not initialised yet cannot be a parent or argument
            if isinstance(given, Base) and "_args" not in vars(given):
                raise RuntimeError(f"libshiboken: '__init__' method of object's base class ({type(given).__name__}) not called.")
        self._args = args
        self.calls = []
        self._signals = {}
        self.children_ = []
        parent = next((a for a in args if isinstance(a, Base)), None)
        self.parent_ = parent
        if parent is not None and hasattr(parent, "children_"):
            parent.children_.append(self)

    def __getattr__(self, name):
        if name.startswith("_") or name in ("calls", "children_", "parent_"):
            raise AttributeError(name)
        cls = type(self)
        if name in cls._api("signals"):
            return self._signals.setdefault(name, Signal())
        if name in cls._api("methods"):
            def call(*a, **k):
                if name in ENUM_ARG_METHODS and a and not isinstance(a[0], Enum):
                    raise TypeError(f"{cls.__name__}.{name} expects a Qt enumeration, not {type(a[0]).__name__} ({a[0]!r})")
                self.calls.append((name, a))
                return getattr(self, "_ret_" + name, lambda *x: None)(*a)
            return call
        raise AttributeError(f"{cls.__name__} has no method or signal {name!r} in Qt")

    def called(self, name):
        return [a for n, a in self.calls if n == name]
