"""
Base class for log collectors.

This defines the interface that all log collectors must implement,
similar to BaseServerManager for servers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path