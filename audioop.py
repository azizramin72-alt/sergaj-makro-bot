# audioop was removed in Python 3.13
# This shim prevents discord.py from crashing on import
import sys
import types

module = types.ModuleType("audioop")
module.tostereo = None
module.ratecv = None
sys.modules["audioop"] = module
