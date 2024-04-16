import functools
import inspect

# Decorator for validating the number of arguments passed to a function with a *args parameter
# The assumption is that if the function has a . in its qualified name, it will be used as an
# instance method. To change that behavior, set static to True. By default, unlimited keyword
# arguments are permitted, but if keyword_allowed is set to False, none are
def num_arg(maximum, *, minimum=0, keyword_allowed=True, static=False):
    def num_arg_decorator(func):

        # This is kind of hacky, but there's no way to know if this is going to
        # be a method until an instance is instantiated
        add = 1 if '.' in func.__qualname__ and not static else 0

        if minimum == maximum:
            positional_message = f"exactly {maximum}"
        elif minimum == 0:
            positional_message = f"at most {maximum}"
        else:
            positional_message = f"between {minimum} and {maximum}"
        keyword_message = "" if keyword_allowed else " and no keyword arguments" 

        @functools.wraps(func)
        def num_arg_wrapper(*args, **kwargs):
            if not (minimum + add <= len(args) <= maximum + add) or (not keyword_allowed and kwargs):
                raise TypeError(f"{func.__qualname__} expected {positional_message} positional arguments{keyword_message}, found {len(args) - add} positional and {len(kwargs)} keyword.")
            return func(*args, **kwargs)

        return num_arg_wrapper

    return num_arg_decorator

# Special case of num_arg for maximum=1
def one_arg(func=None, /, **kwargs):
    if func:
        return num_arg(1, **kwargs)(func)
    else:
        return num_arg(1, **kwargs)

# Decorator for checking type signature on a function including return value if annotated
# If coerce_types is set to True, the wrapper will attempt to cast the value to
# the expected type if it doesn't match and send the result to the decorated
# function
def validated_types(func=None, /, *, coerce_types=True):
    def validated_types_generator(func):
        signature = inspect.signature(func)

        @functools.wraps(func)
        def validate_wrapper(*args, **kwargs):
            # Need something mutable if items need to be modified
            if coerce_types:
                args = list(args)
            pos_idx = 0
            for param in signature.parameters:
                comp = None
                setter = None
                if len(args) > pos_idx:
                    comp = args[pos_idx]
                    if coerce_types:
                        setter = (lambda idx: lambda val: args.__setitem__(idx, val))(pos_idx)
                    pos_idx += 1
                elif param in kwargs:
                    comp = kwargs[param]
                    if coerce_types:
                        setter = lambda val: kwargs.__setitem__(param, val)
                else:
                    # parameter not passed, nothing to validate
                    # function itself should validate number of parameters and
                    # whether they were option or mandatory
                    continue 
                if (t := signature.parameters[param].annotation) is not inspect._empty:
                    if coerce_types and not isinstance(comp, t) and callable(t):
                        # Give coercion a try...
                        setter(t(comp))
                    elif not isinstance(comp, t):
                        raise TypeError(f"{func.__qualname__} expected {param} to be of type {t.__name__}, found {type(comp).__name__}.")
            result = func(*args, **kwargs)
            if (t := signature.return_annotation) is not inspect._empty and not isinstance(result, t):
                raise TypeError(f"{func.__qualname__} was expected to return type {t.__name__}, found {type(result).__name__}.")
            return result
        return validate_wrapper
    if func:
        return validated_types_generator(func)
    else:
        return validated_types_generator

# Function decorator for checking an assertion across key/value data sent as a
# single object parameter or provided in kwargs. Ignores the first argument,
# assuming it to be self (or the class) unless static is set to True
# The assert_function passed should take key and value arguments and validate both
# If the assert_function returns a value, it replaces the value passed to the
# decorated function (so types can be coerced instead of just strictly checked)
def validated_structures(assert_function, static=False):
    def validate_structures_decorator(func):
        @functools.wraps(func)
        @one_arg(static=static)
        def validate_structures_wrapper(*args, **kwargs):
            args_tmp = args if static else args[1:]
            arg = args_tmp[0] if args_tmp else []
            to_check = [kwargs]
            if(hasattr(arg,"keys")):
                to_check.append(arg)
            else:
                new_arg = []
                for key,val in arg:
                    res = assert_function(key, val)
                    if res is not None:
                        new_arg.append((key,res))
                    else:
                        new_arg.append((key,val))
                    args = (args[0], new_arg, *args[2:])
            for x in to_check:
                for key in x.keys():
                    res = assert_function(key, x[key])
                    if res is not None:
                        x[key] = res
            return func(*args, **kwargs)
        return validate_structures_wrapper
    return validate_structures_decorator

# Class decorator to validate type annotations during creation of an instance,
# Note that any methods/attributes with type requirements need to be validated
# separately
def validated_instantiation(cls=None, /, *, replace="__new__"):
    def validated_instantiation_generator(cls):
        orig_func = getattr(cls, replace)
        def validator_func(c, *args, **kwargs):
            pos_idx = 0
            for param in (a := inspect.get_annotations(cls)):
                comp = None
                if(len(args) > pos_idx):
                    comp = args[pos_idx]
                    pos_idx += 1
                elif param in kwargs:
                    comp = kwargs[param]
                else:
                    continue
                if not isinstance(comp, (t := a[param])):
                    raise TypeError(f"{cls.__qualname__} expected {param} to be of type {t.__name__}, found {type(comp).__name__}.")
            return orig_func(c, *args, **kwargs)
        setattr(cls, replace, validator_func)
        return cls
    if cls:
        return validated_instantiation_generator(cls)
    else:
        return validated_instantiation_generator
