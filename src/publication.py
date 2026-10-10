"""Ordinary-exception batch promotion; not a power-loss/concurrency transaction."""
import os
from pathlib import Path


def promote(staged):
    staged = list(staged)
    before = {target: target.read_bytes() if target.exists() else None for _, target in staged}
    installed = []
    try:
        for temporary, target in staged:
            os.replace(temporary, target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            previous = before[target]
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                rollback = target.with_name(target.name + '.rollback')
                rollback.write_bytes(previous)
                os.replace(rollback, target)
        raise
    finally:
        for temporary, _ in staged:
            Path(temporary).unlink(missing_ok=True)
