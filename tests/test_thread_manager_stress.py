import unittest
import threading
import time
import random
import asyncio
from concurrent.futures import TimeoutError

from src.core.thread_manager import ThreadManager, ThreadPoolType


class TestThreadManagerStress(unittest.TestCase):
    """Stress tests for ThreadManager under extreme conditions."""
    
    def setUp(self):
        """Reset ThreadManager singleton."""
        ThreadManager._instance = None
        ThreadManager._lock = threading.Lock()
        
        self.manager = ThreadManager()
        self.manager.initialize_pools()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.manager:
            self.manager.shutdown(wait=True, timeout=15.0)
        ThreadManager._instance = None
    
    def test_exception_handling_stress(self):
        """Test handling of many failing tasks."""
        num_failing_tasks = 100
        
        def random_failing_task():
            error_type = random.choice([ValueError, RuntimeError, TypeError])
            raise error_type(f"Random error: {random.randint(1, 1000)}")
        
        # Submit many failing tasks
        futures = []
        for i in range(num_failing_tasks):
            future = self.manager.submit_task(
                ThreadPoolType.SYSTEM,
                random_failing_task
            )
            futures.append(future)
        
        # Count exceptions
        exception_count = 0
        for future in futures:
            try:
                future.result(timeout=10.0)
            except (ValueError, RuntimeError, TypeError):
                exception_count += 1
        
        # All tasks should have failed
        self.assertEqual(exception_count, num_failing_tasks)
        
        # Thread pool should still be functional
        time.sleep(0.5)  # Allow error callbacks to complete
        self.assertEqual(self.manager._failed_tasks[ThreadPoolType.SYSTEM], num_failing_tasks)
        
        # Test that pool still works after exceptions
        test_future = self.manager.submit_task(ThreadPoolType.SYSTEM, lambda: "recovery_test")
        result = test_future.result(timeout=5.0)
        self.assertEqual(result, "recovery_test")
    
    def test_rapid_start_stop_cycles(self):
        """Test rapid shutdown and reinitialization cycles."""
        cycles = 5
        
        for cycle in range(cycles):
            print(f"Cycle {cycle + 1}/{cycles}")
            
            # Shutdown current manager
            self.manager.shutdown(wait=True, timeout=5.0)
            
            # Reset singleton and create new manager
            ThreadManager._instance = None
            self.manager = ThreadManager()
            self.manager.initialize_pools()
            
            # Test that new manager works
            future = self.manager.submit_task(
                ThreadPoolType.SYSTEM,
                lambda x=cycle: f"cycle_{x}"
            )
            result = future.result(timeout=5.0)
            self.assertEqual(result, f"cycle_{cycle}")
    
    def test_thread_pool_saturation(self):
        """Test behavior when thread pools are saturated."""
        # Get max workers for system pool
        system_config = self.manager._pool_configs[ThreadPoolType.SYSTEM]
        max_workers = system_config.max_workers
        
        # Submit tasks that will saturate the pool
        def blocking_task(duration):
            time.sleep(duration)
            return "completed"
        
        # Submit max_workers + 5 long-running tasks
        oversaturation_count = max_workers + 5
        futures = []
        
        for i in range(oversaturation_count):
            future = self.manager.submit_task(
                ThreadPoolType.SYSTEM,
                blocking_task,
                1.0  # 1 second sleep
            )
            futures.append(future)
        
        # All tasks should eventually complete
        start_time = time.time()
        completed = 0
        for future in futures:
            try:
                future.result(timeout=30.0)
                completed += 1
            except TimeoutError:
                pass
        
        total_time = time.time() - start_time
        
        # Should complete all tasks, but may take longer due to queuing
        self.assertEqual(completed, oversaturation_count)
        
        # Time should be reasonable (tasks will be queued)
        expected_min_time = 1.0  # At least one batch duration
        expected_max_time = 15.0  # Reasonable upper bound
        self.assertGreaterEqual(total_time, expected_min_time)
        self.assertLess(total_time, expected_max_time)
    
    def test_async_loop_stress(self):
        """Test async loops under heavy concurrent load."""
        num_concurrent_coroutines = 500
        
        async def concurrent_async_task(task_id, delay):
            await asyncio.sleep(delay)
            return f"task_{task_id}_completed"
        
        # Submit many concurrent async tasks
        futures = []
        for i in range(num_concurrent_coroutines):
            delay = random.uniform(0.01, 0.1)  # 10-100ms random delay
            future = self.manager.submit_async_task(
                ThreadPoolType.STREAMER,
                concurrent_async_task(i, delay)
            )
            futures.append((i, future))
        
        # Wait for all to complete
        results = {}
        timeout_count = 0
        
        for task_id, future in futures:
            try:
                result = future.result(timeout=20.0)
                results[task_id] = result
            except TimeoutError:
                timeout_count += 1
        
        # Most tasks should complete successfully
        success_rate = len(results) / num_concurrent_coroutines
        self.assertGreater(success_rate, 0.95, "Should have >95% success rate")
        
        print(f"Async stress test: {len(results)}/{num_concurrent_coroutines} completed")
        print(f"Success rate: {success_rate:.2%}")
    
    def test_mixed_workload_chaos(self):
        """Test with chaotic mixed workload of sync/async/failing tasks."""
        duration = 10  # seconds
        start_time = time.time()
        
        submitted_tasks = 0
        completed_tasks = 0
        failed_tasks = 0
        futures = []
        
        def quick_task():
            return "quick"
        
        def slow_task():
            time.sleep(random.uniform(0.1, 0.5))
            return "slow"
        
        def failing_task():
            if random.random() < 0.3:  # 30% failure rate
                raise RuntimeError("Chaos failure")
            return "survived"
        
        async def async_task():
            await asyncio.sleep(random.uniform(0.01, 0.1))
            return "async"
        
        # Submit tasks randomly for duration
        while time.time() - start_time < duration:
            task_type = random.choice(['quick', 'slow', 'failing', 'async'])
            pool_type = random.choice(list(ThreadPoolType))
            
            try:
                if task_type == 'quick':
                    future = self.manager.submit_task(pool_type, quick_task)
                elif task_type == 'slow':
                    future = self.manager.submit_task(pool_type, slow_task)
                elif task_type == 'failing':
                    future = self.manager.submit_task(pool_type, failing_task)
                elif task_type == 'async' and pool_type in [ThreadPoolType.STREAMER, ThreadPoolType.EVENT_BUS]:
                    future = self.manager.submit_async_task(pool_type, async_task())
                else:
                    continue  # Skip async for pools without async loops
                
                futures.append(future)
                submitted_tasks += 1
                
                # Don't overwhelm the system
                if len(futures) > 100:
                    time.sleep(0.01)
                
            except Exception as e:
                print(f"Submission error: {e}")
        
        print(f"Chaos test submitted {submitted_tasks} tasks")
        
        # Wait for all submitted tasks to complete
        for future in futures:
            try:
                future.result(timeout=30.0)
                completed_tasks += 1
            except Exception:
                failed_tasks += 1
        
        completion_rate = completed_tasks / submitted_tasks if submitted_tasks > 0 else 0
        
        print(f"Chaos results: {completed_tasks} completed, {failed_tasks} failed")
        print(f"Completion rate: {completion_rate:.2%}")
        
        # Should have reasonable completion rate despite chaos
        self.assertGreater(completion_rate, 0.7, "Should complete >70% of tasks despite chaos")
    
    def test_shutdown_with_pending_tasks(self):
        """Test graceful shutdown with many pending tasks."""
        # Submit many long-running tasks
        num_tasks = 50
        
        def long_task(task_id):
            time.sleep(2.0)  # Long enough to be interrupted
            return f"completed_{task_id}"
        
        futures = []
        for i in range(num_tasks):
            future = self.manager.submit_task(ThreadPoolType.EXECUTOR, long_task, i)
            futures.append(future)
        
        # Let some tasks start
        time.sleep(0.5)
        
        # Shutdown with timeout
        start_shutdown = time.time()
        self.manager.shutdown(wait=True, timeout=3.0)
        shutdown_duration = time.time() - start_shutdown
        
        # Shutdown should respect timeout
        self.assertLess(shutdown_duration, 5.0, "Shutdown should complete within reasonable time")
        
        # Check how many tasks completed vs were cancelled
        completed = 0
        cancelled = 0
        
        for future in futures:
            if future.done():
                try:
                    future.result(timeout=0.1)
                    completed += 1
                except:
                    cancelled += 1
        
        print(f"Shutdown results: {completed} completed, {cancelled} cancelled/failed")
        
        # Some tasks should have been interrupted
        self.assertLess(completed, num_tasks, "Not all tasks should complete during shutdown")


if __name__ == '__main__':
    unittest.main(verbosity=2)
