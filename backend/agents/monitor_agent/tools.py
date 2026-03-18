"""Tools for the Monitor Agent."""

from typing import List
from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.agents.data_agent.tools import build_data_agent_tools
import json
import logging

logger = logging.getLogger(__name__)


def build_monitor_agent_tools(context: AgentContext) -> List:
    """
    Build tools for the monitor agent.

    Includes data exploration tools plus monitoring-specific tools.
    Communication tools are injected by AgentRuntime.
    """
    # Reuse data agent's exploration tools
    data_tools = build_data_agent_tools(context)

    @tool
    def check_threshold(
        metric_name: str,
        current_value: float,
        expected_value: float,
        threshold_percent: float = 20.0,
    ) -> str:
        """
        Check if a metric deviates from expected by more than threshold%.

        Args:
            metric_name: Name of the metric being checked
            current_value: Current observed value
            expected_value: Expected/baseline value
            threshold_percent: Deviation threshold in percent (default 20%)

        Returns:
            JSON with is_anomaly, severity, deviation_percent
        """
        if expected_value == 0:
            deviation = 100.0 if current_value != 0 else 0.0
        else:
            deviation = abs((current_value - expected_value) / expected_value) * 100

        is_anomaly = deviation > threshold_percent
        severity = "INFO"
        if deviation > threshold_percent * 2:
            severity = "CRITICAL"
        elif deviation > threshold_percent:
            severity = "WARNING"

        return json.dumps({
            "metric": metric_name,
            "current_value": current_value,
            "expected_value": expected_value,
            "deviation_percent": round(deviation, 2),
            "is_anomaly": is_anomaly,
            "severity": severity,
        })

    @tool
    def analyze_trend(
        values: str,
        window_size: int = 3,
    ) -> str:
        """
        Analyze a series of values for trends.

        Args:
            values: JSON array of numbers (time-ordered)
            window_size: Moving average window size (default 3)

        Returns:
            JSON with trend direction, moving_average, volatility
        """
        try:
            nums = json.loads(values)
            if not isinstance(nums, list) or len(nums) < 2:
                return json.dumps({"error": "Need at least 2 numeric values"})
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "Invalid values format — expected JSON array"})

        nums = [float(n) for n in nums]

        # Trend direction
        if nums[-1] > nums[0]:
            direction = "increasing"
        elif nums[-1] < nums[0]:
            direction = "decreasing"
        else:
            direction = "flat"

        # Moving average
        moving_avg = []
        for i in range(len(nums)):
            start = max(0, i - window_size + 1)
            window = nums[start:i + 1]
            moving_avg.append(round(sum(window) / len(window), 2))

        # Volatility (std dev)
        mean = sum(nums) / len(nums)
        variance = sum((x - mean) ** 2 for x in nums) / len(nums)
        volatility = round(variance ** 0.5, 2)

        return json.dumps({
            "trend": direction,
            "moving_average": moving_avg,
            "volatility": volatility,
            "latest_value": nums[-1],
            "period_change_percent": round(
                ((nums[-1] - nums[0]) / nums[0] * 100) if nums[0] != 0 else 0, 2
            ),
        })

    return data_tools + [check_threshold, analyze_trend]
