#                  _   _                 _     _
#    ___  ___ ___ | |_| |_ ______ _  ___| |__ / |
#   / __|/ __/ _ \| __| __|_  / _` |/ __| '_ \| |
#   \__ \ (_| (_) | |_| |_ / / (_| | (__| | | | |
#   |___/\___\___/ \__|\__/___\__,_|\___|_| |_|_|
#
#        Zac Scott (github.com/scottzach1)
#
#  https://github.com/scottzach1/python-injector-framework

import functools
import importlib
import inspect
import itertools
import types
from typing import Any, Callable

from pif import providers


def patch_args(
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """
    Patch the args and kwargs at runtime using the signature for reference.

    :param signature: to lookup method parameters.
    :param args: provided at runtime
    :param kwargs: provided at runtime.
    :return: injected args and kwargs to pass to func.
    """
    for i, (name, value) in enumerate(signature.parameters.items()):
        if isinstance(value.default, providers.Provider) and i >= len(args):
            if value.kind == inspect.Parameter.POSITIONAL_ONLY:
                args = (
                    *args,
                    *(p.default for p in itertools.islice(signature.parameters.values(), len(args), i)),
                    value.default(),
                )
            if (
                value.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
                and name not in kwargs
            ):
                kwargs[name] = value.default()
    return args, kwargs


def injected[T: Callable](func: T) -> T:
    """
    Get a decorated copy of `func` with patched arguments.

    :param func: to decorate.
    :return: the decorated function.
    """
    signature = inspect.signature(func)

    if not any(p for p in signature.parameters.values() if isinstance(p.default, providers.Provider)):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        args, kwargs = patch_args(signature, args, kwargs)

        return func(*args, **kwargs)

    wrapper._patched_func = func
    return wrapper


def is_patched(func: Callable | types.FunctionType) -> bool:
    """
    Checks if a function has been "patched" by the `patch_args_decorator`

    :param func: the function to check.
    :return: True if patched, False otherwise.
    """
    return hasattr(func, "_patched_func")


def patch_method[T: Callable | types.FunctionType](func: T) -> T:
    """
    Return a "patched" version of the method provided.

    If no values required patching, the provided function will be returned unchanged.

    :param func: to patch default values.
    :return: a "patched" version of the method provided.
    """
    if any(1 for param in inspect.signature(func).parameters.values() if isinstance(param.default, providers.Provider)):
        return injected(func)

    return func


def unpatch_method[T: Callable | types.FunctionType](func: T) -> T:
    """
    Get an "unpatched" copy of a method.

    If the value was not patched, the provided function will be returned unchanged.

    :param func: the function to unpatch.
    :return: the unpatched provided function.
    """
    return getattr(func, "_patched_func", func)


def wire(modules: list[types.ModuleType | str]) -> None:
    """
    Patch all methods in the module containing `Provide` default arguments.

    :param modules: list of modules to wire.
    """
    for module in modules:
        if isinstance(module, str):
            module = importlib.import_module(module)

        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                if obj is not (patched := patch_method(obj)):
                    setattr(module, name, patched)
            elif inspect.isclass(obj):
                for method_name, method in inspect.getmembers(obj, inspect.isfunction):
                    if method is not (patched := patch_method(method)):
                        setattr(obj, method_name, patched)


def unwire(modules: list[types.ModuleType]) -> None:
    """
    Unpatch all methods in the module containing `Provide` default arguments.

    :param modules: list of modules to wire.
    """
    for module in modules:
        if isinstance(module, str):
            module = importlib.import_module(module)

        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                if obj is not (unpatched := unpatch_method(obj)):
                    setattr(module, name, unpatched)
            elif inspect.isclass(obj):
                for method_name, method in inspect.getmembers(obj, inspect.isfunction):
                    if method is not (unpatched := unpatch_method(method)):
                        setattr(obj, method_name, unpatched)
