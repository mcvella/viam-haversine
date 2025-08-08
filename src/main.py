import asyncio
from viam.module.module import Module
try:
    from models.haversine import Haversine
except ModuleNotFoundError:
    # when running as local module with run.sh
    from .models.haversine import Haversine


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
