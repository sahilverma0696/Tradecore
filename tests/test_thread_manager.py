import unittest
import threading
import asyncio
import time
import concurrent.futures
from unittest.mock import patch, MagicMock

from src.core.thread_manager import ThreadManager, ThreadPoolType, ThreadPoolConfig
from src.system_config_manager import SystemConfigManager


class TestThreadManager(unittest.TestCase):
    """Comprehensive tests for ThreadManager class."""
    
    def setUp(self):
        """Reset ThreadManager singleton before each test."""
        # Reset singleton instance
        ThreadManager._instance = None
        ThreadManager._lock = threading.Lock()
        
    def tearDown(self):
        """Clean up after each test."""
        # Get instance if it exists and shut it down
        if ThreadManager._instance:
            try:
                ThreadManager._instance.shutdown(wait=True, timeout=5.0)
            except:
                pass
        
        # Reset singleton
        ThreadManager._instance = None
    
    def test_singleton_pattern(self):
        """Test that ThreadManager follows singleton pattern."""
        # Create two instances
        manager1 = ThreadManager()
        manager2 = ThreadManager()
        
        # Should be the same instance
        self.assertIs(manager1, manager2)
        self.assertEqual(id(manager1), id(manager2))
    
    def test_thread_safe_singleton(self):
        """Test that singleton creation is thread-safe."""
        instances = []
        barrier = threading.Barrier(5)
        
        def create_instance():
            barrier.wait()  # Synchronize thread start
            instance = ThreadManager()
            instances.append(instance)
        
        # Create multiple threads trying to create instances
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_instance)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All instances should be the same
        first_instance = instances[0]
        for instance in instances[1:]:
            self.assertIs(instance, first_instance)
    
    @patch('src.system_config_manager.SystemConfigManager')
    def test_initialization_with_mock_config(self, mock_config_class):
        """Test ThreadManager initialization with mocked config."""
        # Mock system config
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default: {
            'threading.event_bus_workers': 2,
            'threading.streamer_workers': 4,
            'threading.strategy_workers': 2,
            'threading.executor_workers': 2,
            'threading.system_workers': 2,
            'event_bus.max_event_history': 1000,
            'streamers.buffer_size': 1024
        }.get(key, default)
        
        mock_config_class.return_value = mock_config
        
        # Initialize ThreadManager
        manager = ThreadManager()
        self.assertIsNotNone(manager)
        self.assertEqual(len(manager._pool_configs), 5)
    
    def test_thread_pool_configs_loading(self):
        """Test loading of thread pool configurations."""
        manager = ThreadManager()
        configs = manager._pool_configs
        
        # Check that all pool types have configs
        expected_types = {
            ThreadPoolType.EVENT_BUS,
            ThreadPoolType.STREAMER,
            ThreadPoolType.STRATEGY,
            ThreadPoolType.EXECUTOR,
            ThreadPoolType.SYSTEM
        }
        
        self.assertEqual(set(configs.keys()), expected_types)
        
        # Check config structure
        for pool_type, config in configs.items():
            self.assertIsInstance(config, ThreadPoolConfig)
            self.assertEqual(config.pool_type, pool_type)
            self.assertGreater(config.max_workers, 0)
            self.assertTrue(config.thread_name_prefix)
    
    def test_initialize_pools(self):
        """Test initialization of thread pools."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        # Check that all pools are created
        self.assertEqual(len(manager._thread_pools), 5)
        
        # Check that async loops are created for appropriate pools
        self.assertIn(ThreadPoolType.STREAMER, manager._async_loops)
        self.assertIn(ThreadPoolType.EVENT_BUS, manager._async_loops)
        
        # Check that loop threads are started
        for pool_type in [ThreadPoolType.STREAMER, ThreadPoolType.EVENT_BUS]:
            self.assertIn(pool_type, manager._loop_threads)
            thread = manager._loop_threads[pool_type]
            self.assertTrue(thread.is_alive())
    
    def test_submit_task_to_pool(self):
        """Test submitting tasks to thread pools."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        # Define a simple test function
        result_value = 42
        def test_function(x):
            return x * 2
        
        # Submit task to system pool
        future = manager.submit_task(ThreadPoolType.SYSTEM, test_function, result_value)
        
        # Check that future is returned
        self.assertIsInstance(future, concurrent.futures.Future)
        
        # Wait for result
        result = future.result(timeout=5.0)
        self.assertEqual(result, result_value * 2)
        
        # Check task counters
        time.sleep(0.1)  # Allow callback to execute
        self.assertEqual(manager._completed_tasks[ThreadPoolType.SYSTEM], 1)
    
    def test_submit_task_with_exception(self):
        """Test task submission that raises an exception."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        def failing_function():
            raise ValueError("Test exception")
        
        # Submit failing task
        future = manager.submit_task(ThreadPoolType.SYSTEM, failing_function)
        
        # Should raise the exception
        with self.assertRaises(ValueError):
            future.result(timeout=5.0)
        
        # Check error counter
        time.sleep(0.1)  # Allow callback to execute
        self.assertEqual(manager._failed_tasks[ThreadPoolType.SYSTEM], 1)
    
    def test_submit_async_task(self):
        """Test submitting async tasks to async loops."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        async def async_test_function(x):
            await asyncio.sleep(0.1)
            return x * 3
        
        # Submit async task
        future = manager.submit_async_task(ThreadPoolType.STREAMER, async_test_function(10))
        
        # Wait for result
        result = future.result(timeout=5.0)
        self.assertEqual(result, 30)
    
    def test_invalid_pool_type_submission(self):
        """Test submitting task to non-existent pool type."""
        manager = ThreadManager()
        # Don't initialize pools
        
        def test_function():
            return "test"
        
        # Should raise ValueError for uninitialized pool
        with self.assertRaises(ValueError):
            manager.submit_task(ThreadPoolType.SYSTEM, test_function)
    
    def test_pool_statistics(self):
        """Test getting pool statistics."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        # Get initial stats
        stats = manager.get_pool_stats()
        
        # Check structure
        self.assertIsInstance(stats, dict)
        self.assertEqual(len(stats), 5)
        
        for pool_name, pool_stats in stats.items():
            self.assertIn('max_workers', pool_stats)
            self.assertIn('active_tasks', pool_stats)
            self.assertIn('completed_tasks', pool_stats)
            self.assertIn('failed_tasks', pool_stats)
            self.assertIn('has_async_loop', pool_stats)
            
            # Check initial values
            self.assertGreaterEqual(pool_stats['max_workers'], 1)
            self.assertEqual(pool_stats['active_tasks'], 0)
            self.assertEqual(pool_stats['completed_tasks'], 0)
            self.assertEqual(pool_stats['failed_tasks'], 0)
    
    def test_task_completion_tracking(self):
        """Test that task completion is properly tracked."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        def slow_task():
            time.sleep(0.2)
            return "completed"
        
        # Submit multiple tasks
        futures = []
        for i in range(3):
            future = manager.submit_task(ThreadPoolType.STRATEGY, slow_task)
            futures.append(future)
        
        # Check active tasks
        self.assertEqual(manager._active_tasks[ThreadPoolType.STRATEGY], 3)
        
        # Wait for completion
        for future in futures:
            future.result(timeout=5.0)
        
        # Allow callbacks to execute
        time.sleep(0.1)
        
        # Check completion tracking
        self.assertEqual(manager._active_tasks[ThreadPoolType.STRATEGY], 0)
        self.assertEqual(manager._completed_tasks[ThreadPoolType.STRATEGY], 3)
    
    def test_shutdown_graceful(self):
        """Test graceful shutdown of thread pools."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        # Submit a task that will be interrupted
        def long_running_task():
            time.sleep(2.0)
            return "completed"
        
        future = manager.submit_task(ThreadPoolType.EXECUTOR, long_running_task)
        
        # Shutdown with timeout
        start_time = time.time()
        manager.shutdown(wait=True, timeout=1.0)
        shutdown_time = time.time() - start_time
        
        # Should shutdown within reasonable time
        self.assertLess(shutdown_time, 2.0)
        
        # Async loops should be stopped
        for pool_type, thread in manager._loop_threads.items():
            thread.join(timeout=1.0)
            # Thread should finish (may still be alive due to timing)
    
    def test_async_loop_creation(self):
        """Test that async event loops are properly created."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        # Check that async loops exist for streamer and event bus
        self.assertIn(ThreadPoolType.STREAMER, manager._async_loops)
        self.assertIn(ThreadPoolType.EVENT_BUS, manager._async_loops)
        
        # Check that loops are running
        for pool_type in [ThreadPoolType.STREAMER, ThreadPoolType.EVENT_BUS]:
            loop = manager._async_loops[pool_type]
            self.assertIsInstance(loop, asyncio.AbstractEventLoop)
            self.assertTrue(loop.is_running())


class TestThreadPoolConfig(unittest.TestCase):
    """Test ThreadPoolConfig dataclass."""
    
    def test_config_creation(self):
        """Test creating ThreadPoolConfig instances."""
        config = ThreadPoolConfig(
            pool_type=ThreadPoolType.STREAMER,
            max_workers=4,
            thread_name_prefix="TestStreamer",
            daemon=True,
            queue_size=100
        )
        
        self.assertEqual(config.pool_type, ThreadPoolType.STREAMER)
        self.assertEqual(config.max_workers, 4)
        self.assertEqual(config.thread_name_prefix, "TestStreamer")
        self.assertTrue(config.daemon)
        self.assertEqual(config.queue_size, 100)
    
    def test_config_defaults(self):
        """Test default values in ThreadPoolConfig."""
        config = ThreadPoolConfig(
            pool_type=ThreadPoolType.SYSTEM,
            max_workers=2,
            thread_name_prefix="System"
        )
        
        self.assertTrue(config.daemon)  # Default should be True
        self.assertIsNone(config.queue_size)  # Default should be None


class TestThreadPoolIntegration(unittest.TestCase):
    """Integration tests for ThreadManager with real workloads."""
    
    def setUp(self):
        """Reset ThreadManager singleton."""
        ThreadManager._instance = None
        ThreadManager._lock = threading.Lock()
    
    def tearDown(self):
        """Clean up after tests."""
        if ThreadManager._instance:
            try:
                ThreadManager._instance.shutdown(wait=True, timeout=5.0)
            except:
                pass
        ThreadManager._instance = None
    
    def test_concurrent_task_submission(self):
        """Test submitting tasks from multiple threads concurrently."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        results = []
        results_lock = threading.Lock()
        
        def submit_tasks():
            for i in range(5):
                future = manager.submit_task(
                    ThreadPoolType.SYSTEM,
                    lambda x=i: x * 10
                )
                result = future.result(timeout=5.0)
                with results_lock:
                    results.append(result)
        
        # Create multiple submitter threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=submit_tasks)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertEqual(len(results), 15)  # 3 threads * 5 tasks each
        expected_values = [0, 10, 20, 30, 40] * 3
        self.assertEqual(sorted(results), sorted(expected_values))
    
    def test_mixed_sync_async_workload(self):
        """Test handling both sync and async tasks simultaneously."""
        manager = ThreadManager()
        manager.initialize_pools()
        
        # Sync task
        def sync_task(value):
            time.sleep(0.1)
            return f"sync_{value}"
        
        # Async task
        async def async_task(value):
            await asyncio.sleep(0.1)
            return f"async_{value}"
        
        # Submit mixed workload
        sync_future = manager.submit_task(ThreadPoolType.SYSTEM, sync_task, "test1")
        async_future = manager.submit_async_task(ThreadPoolType.STREAMER, async_task("test2"))
        
        # Get results
        sync_result = sync_future.result(timeout=5.0)
        async_result = async_future.result(timeout=5.0)
        
        self.assertEqual(sync_result, "sync_test1")
        self.assertEqual(async_result, "async_test2")


if __name__ == '__main__':
    unittest.main()
