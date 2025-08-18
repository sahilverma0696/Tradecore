import unittest
import time
import threading
import asyncio
import concurrent.futures
from statistics import mean, median

from src.core.thread_manager import ThreadManager, ThreadPoolType


class TestThreadManagerPerformance(unittest.TestCase):
    """Performance tests for ThreadManager under various load conditions."""
    
    def setUp(self):
        """Reset ThreadManager singleton before each test."""
        ThreadManager._instance = None
        ThreadManager._lock = threading.Lock()
        
        # Initialize fresh manager
        self.manager = ThreadManager()
        self.manager.initialize_pools()
    
    def tearDown(self):
        """Clean up after each test."""
        if self.manager:
            self.manager.shutdown(wait=True, timeout=10.0)
        ThreadManager._instance = None
    
    def test_high_volume_task_submission(self):
        """Test submitting a large number of tasks quickly."""
        num_tasks = 1000
        start_time = time.time()
        
        # Submit many small tasks
        futures = []
        for i in range(num_tasks):
            future = self.manager.submit_task(
                ThreadPoolType.SYSTEM,
                lambda x=i: x * 2
            )
            futures.append(future)
        
        submission_time = time.time() - start_time
        
        # Wait for all tasks to complete
        results = []
        for future in futures:
            results.append(future.result(timeout=30.0))
        
        total_time = time.time() - start_time
        
        # Verify results
        expected_results = [i * 2 for i in range(num_tasks)]
        self.assertEqual(sorted(results), sorted(expected_results))
        
        # Performance assertions
        self.assertLess(submission_time, 5.0, "Task submission should be fast")
        self.assertLess(total_time, 30.0, "All tasks should complete in reasonable time")
        
        # Log performance metrics
        print(f"\nHigh Volume Test Results:")
        print(f"Tasks: {num_tasks}")
        print(f"Submission time: {submission_time:.3f}s")
        print(f"Total time: {total_time:.3f}s")
        print(f"Tasks per second: {num_tasks / total_time:.1f}")
    
    def test_concurrent_pool_usage(self):
        """Test using multiple thread pools concurrently."""
        num_tasks_per_pool = 100
        
        def cpu_intensive_task(n):
            """Simulate CPU-intensive work."""
            total = 0
            for i in range(n * 1000):
                total += i
            return total
        
        def io_simulation_task():
            """Simulate I/O-bound work."""
            time.sleep(0.01)
            return "io_complete"
        
        start_time = time.time()
        
        # Submit to different pools simultaneously
        futures = []
        
        # CPU tasks to system pool
        for i in range(num_tasks_per_pool):
            future = self.manager.submit_task(
                ThreadPoolType.SYSTEM,
                cpu_intensive_task,
                10
            )
            futures.append(('cpu', future))
        
        # I/O tasks to streamer pool
        for i in range(num_tasks_per_pool):
            future = self.manager.submit_task(
                ThreadPoolType.STREAMER,
                io_simulation_task
            )
            futures.append(('io', future))
        
        # Strategy tasks
        for i in range(num_tasks_per_pool):
            future = self.manager.submit_task(
                ThreadPoolType.STRATEGY,
                lambda: "strategy_result"
            )
            futures.append(('strategy', future))
        
        # Wait for all tasks
        results = {}
        for task_type, future in futures:
            if task_type not in results:
                results[task_type] = []
            results[task_type].append(future.result(timeout=30.0))
        
        total_time = time.time() - start_time
        
        # Verify all tasks completed
        self.assertEqual(len(results['cpu']), num_tasks_per_pool)
        self.assertEqual(len(results['io']), num_tasks_per_pool)
        self.assertEqual(len(results['strategy']), num_tasks_per_pool)
        
        print(f"\nConcurrent Pool Test Results:")
        print(f"Tasks per pool: {num_tasks_per_pool}")
        print(f"Total pools used: 3")
        print(f"Total time: {total_time:.3f}s")
        print(f"Total throughput: {len(futures) / total_time:.1f} tasks/sec")
    
    def test_async_task_performance(self):
        """Test performance of async task submission and execution."""
        num_async_tasks = 200
        
        async def async_workload(delay, value):
            await asyncio.sleep(delay)
            return value * 2
        
        start_time = time.time()
        
        # Submit async tasks
        futures = []
        for i in range(num_async_tasks):
            future = self.manager.submit_async_task(
                ThreadPoolType.STREAMER,
                async_workload(0.01, i)  # 10ms delay each
            )
            futures.append(future)
        
        submission_time = time.time() - start_time
        
        # Wait for results
        results = []
        for future in futures:
            results.append(future.result(timeout=30.0))
        
        total_time = time.time() - start_time
        
        # Verify results
        expected = [i * 2 for i in range(num_async_tasks)]
        self.assertEqual(sorted(results), sorted(expected))
        
        print(f"\nAsync Task Performance:")
        print(f"Async tasks: {num_async_tasks}")
        print(f"Submission time: {submission_time:.3f}s")
        print(f"Total time: {total_time:.3f}s")
        print(f"Async tasks per second: {num_async_tasks / total_time:.1f}")
        
        # Async tasks should complete concurrently, not sequentially
        # Even with 10ms delay each, total time should be much less than sum of delays
        max_expected_time = 5.0  # Should be much faster than 200 * 0.01 = 2.0s
        self.assertLess(total_time, max_expected_time)
    
    def test_memory_usage_under_load(self):
        """Test that thread pools don't leak memory under sustained load."""
        import gc
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run multiple rounds of tasks
        rounds = 10
        tasks_per_round = 100
        
        for round_num in range(rounds):
            futures = []
            
            # Submit tasks
            for i in range(tasks_per_round):
                future = self.manager.submit_task(
                    ThreadPoolType.SYSTEM,
                    lambda x=i: [j for j in range(x * 100)]  # Create some temporary objects
                )
                futures.append(future)
            
            # Wait for completion
            for future in futures:
                future.result(timeout=10.0)
            
            # Force garbage collection
            gc.collect()
            
            # Check memory usage periodically
            if round_num % 3 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                print(f"Round {round_num}: Memory usage: {current_memory:.1f}MB (+{memory_growth:.1f}MB)")
                
                # Memory growth should be reasonable (less than 50MB for this test)
                self.assertLess(memory_growth, 50.0, "Memory usage growing too fast")
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory
        
        print(f"\nMemory Usage Summary:")
        print(f"Initial: {initial_memory:.1f}MB")
        print(f"Final: {final_memory:.1f}MB")
        print(f"Growth: {total_growth:.1f}MB")
        
        # Total growth should be reasonable for the workload
        self.assertLess(total_growth, 100.0, "Excessive memory growth detected")
    
    def test_latency_distribution(self):
        """Test latency distribution of task execution."""
        num_samples = 100
        latencies = []
        
        def timed_task():
            return time.time()
        
        for i in range(num_samples):
            submit_time = time.time()
            future = self.manager.submit_task(ThreadPoolType.EXECUTOR, timed_task)
            execution_time = future.result(timeout=10.0)
            
            # Calculate latency (time from submission to execution start)
            latency = execution_time - submit_time
            latencies.append(latency * 1000)  # Convert to milliseconds
        
        # Calculate statistics
        mean_latency = mean(latencies)
        median_latency = median(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        
        print(f"\nLatency Distribution (ms):")
        print(f"Mean: {mean_latency:.3f}")
        print(f"Median: {median_latency:.3f}")
        print(f"Min: {min_latency:.3f}")
        print(f"Max: {max_latency:.3f}")
        
        # Performance assertions
        self.assertLess(mean_latency, 10.0, "Mean latency should be low")
        self.assertLess(median_latency, 5.0, "Median latency should be very low")
        self.assertLess(max_latency, 100.0, "Max latency should be reasonable")


if __name__ == '__main__':
    # Run with verbosity to see performance metrics
    unittest.main(verbosity=2)
