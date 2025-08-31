import asyncio
from datetime import datetime
from typing import Callable, Any, Optional, Dict
from functools import wraps
from loguru import logger


class RetryableError(Exception):
    """Exception that indicates an operation should be retried"""
    pass


class CriticalError(Exception):
    """Exception that indicates a critical system error"""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (RetryableError, ConnectionError, TimeoutError)
):
    """Decorator for retrying functions with exponential backoff"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                except Exception as e:
                    # Don't retry non-retryable exceptions
                    logger.error(f"Function {func.__name__} failed with non-retryable error: {e}")
                    raise
                    
            raise last_exception
            
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                except Exception as e:
                    logger.error(f"Function {func.__name__} failed with non-retryable error: {e}")
                    raise
                    
            raise last_exception
            
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def handle_errors(
    default_return: Any = None,
    log_errors: bool = True,
    re_raise: bool = False
):
    """Decorator for handling errors gracefully"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                
                if re_raise:
                    raise
                    
                return default_return
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                
                if re_raise:
                    raise
                    
                return default_return
                
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def log_performance(operation_name: str = None):
    """Decorator to log performance metrics"""
    
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.bind(performance=True).info(f"PERFORMANCE | {op_name} | SUCCESS | {duration:.2f}s")
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.bind(performance=True).info(f"PERFORMANCE | {op_name} | ERROR | {duration:.2f}s | {e}")
                raise
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.bind(performance=True).info(f"PERFORMANCE | {op_name} | SUCCESS | {duration:.2f}s")
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.bind(performance=True).info(f"PERFORMANCE | {op_name} | ERROR | {duration:.2f}s | {e}")
                raise
                
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


class ErrorTracker:
    """Track and analyze application errors"""
    
    def __init__(self):
        self.errors = []
        self.error_counts = {}
        
    def record_error(self, error: Exception, context: Dict[str, Any] = None):
        """Record an error occurrence"""
        error_info = {
            'timestamp': datetime.now(),
            'error_type': type(error).__name__,
            'message': str(error),
            'context': context or {}
        }
        
        self.errors.append(error_info)
        
        # Update error counts
        error_key = f"{error_info['error_type']}: {error_info['message']}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        logger.error(f"Error recorded: {error_info['error_type']} - {error_info['message']}", extra=error_info)
        
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the specified time window"""
        cutoff_time = datetime.now() - datetime.timedelta(hours=hours)
        recent_errors = [e for e in self.errors if e['timestamp'] > cutoff_time]
        
        error_types = {}
        for error in recent_errors:
            error_type = error['error_type']
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
        return {
            'total_errors': len(recent_errors),
            'unique_errors': len(set(e['error_type'] + e['message'] for e in recent_errors)),
            'error_types': error_types,
            'most_recent': recent_errors[-1] if recent_errors else None
        }
        
    def clear_old_errors(self, hours: int = 168):  # Default: 1 week
        """Clear errors older than specified hours"""
        cutoff_time = datetime.now() - datetime.timedelta(hours=hours)
        self.errors = [e for e in self.errors if e['timestamp'] > cutoff_time]


# Global error tracker instance
error_tracker = ErrorTracker()


def safe_async_task(coro):
    """Safely run an async task and log any exceptions"""
    
    async def wrapper():
        try:
            await coro
        except Exception as e:
            logger.error(f"Unhandled exception in async task: {e}", exc_info=True)
            error_tracker.record_error(e, {'task': 'background_task'})
            
    return wrapper()


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                else:
                    raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
                    
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                else:
                    raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
                    
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise
                
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    def _should_attempt_reset(self) -> bool:
        return (
            self.last_failure_time and
            (datetime.now() - self.last_failure_time).total_seconds() >= self.recovery_timeout
        )
        
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
        
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'