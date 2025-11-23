import asyncio
import threading
import time

import pytest
import server


# @pytest.mark.skip(reason="Disabled until TCG API is responsive again")
# def test_lifespan_runs_set_icon_refresh_in_background(monkeypatch):
#     call_details: dict[str, threading.Thread] = {}
# 
#     def slow_ensure() -> list[object]:
#         call_details["thread"] = threading.current_thread()
#         time.sleep(0.2)
#         return []
# 
#     monkeypatch.setattr(server, "init_db", lambda: None)
#     monkeypatch.setattr(server.set_icons, "ensure_set_icons", slow_ensure)
# 
#     async def exercise_lifespan():
#         async with server.lifespan(server.app):
#             pass
# 
#     async def run_test():
#         start = time.perf_counter()
#         task = asyncio.create_task(exercise_lifespan())
#         await asyncio.sleep(0)
#         mid = time.perf_counter()
#         assert mid - start < 0.1
#         await asyncio.wait_for(task, timeout=1.0)
# 
#     asyncio.run(run_test())
# 
#     thread = call_details.get("thread")
#     assert thread is not None
#     assert thread is not threading.main_thread()