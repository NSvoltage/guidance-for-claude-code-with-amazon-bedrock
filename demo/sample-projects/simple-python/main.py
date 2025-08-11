#!/usr/bin/env python3
"""
Simple Python project for Claude Code enterprise demo.
This demonstrates typical development tasks that Claude Code can help with.
"""

import json
from typing import Dict, List, Optional

def calculate_statistics(numbers: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of numbers."""
    if not numbers:
        return {}
    
    return {
        "mean": sum(numbers) / len(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "count": len(numbers)
    }

def main():
    """Main function demonstrating various operations."""
    print("Claude Code Enterprise Demo - Simple Python Project")
    
    # Demo calculation
    sample_data = [1.5, 2.3, 3.7, 4.1, 5.9, 2.8, 3.4]
    stats = calculate_statistics(sample_data)
    print(f"Statistics: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    main()