def multiprocessing_available() -> bool:
    """Return True if importing multiprocessing synchronization primitives works."""
    try:
        import multiprocessing as _mp  # noqa: F401
        from multiprocessing import synchronize  # noqa: F401
        return True
    except Exception:
        return False
