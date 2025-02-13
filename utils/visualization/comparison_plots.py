"""
Generic visualization utilities for benchmarking different LLM techniques and implementations.
Supports comparison of various metrics across different approaches (RAG, SQL, etc.).
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Union, Any
import numpy as np
from datetime import datetime


class BenchmarkVisualizer:
    """
    Generic visualization tools for comparing different LLM techniques and implementations.
    Supports various types of comparisons and metrics visualization.
    """
    
    def __init__(self, style: str = 'whitegrid'):
        """
        Initialize visualizer with plot style.
        
        Args:
            style: Seaborn style ('whitegrid', 'darkgrid', etc.)
        """
        sns.set_style(style)
        self.default_colors = sns.color_palette("husl", 8)
    
    def plot_comparison(
        self,
        data: Union[Dict[str, Dict[str, float]], pd.DataFrame],
        comparison_type: str = "metrics",
        plot_type: str = "bar",
        title: Optional[str] = None,
        figsize: tuple = (10, 6),
        save_path: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Create a comparison plot for any type of benchmarking data.
        
        Args:
            data: Dictionary or DataFrame containing comparison data
            comparison_type: Type of comparison ('metrics', 'performance', 'accuracy', etc.)
            plot_type: Type of plot ('bar', 'radar', 'heatmap', 'line', etc.)
            title: Plot title (auto-generated if None)
            figsize: Figure size (width, height)
            save_path: Optional path to save the plot
            **kwargs: Additional plotting parameters
        """
        # Convert dictionary to DataFrame if needed
        df = pd.DataFrame(data) if isinstance(data, dict) else data
        
        # Auto-generate title if not provided
        if title is None:
            title = f"{comparison_type.title()} Comparison"
        
        plt.figure(figsize=figsize)
        
        if plot_type == "bar":
            self._create_bar_plot(df, title, **kwargs)
        elif plot_type == "radar":
            self._create_radar_plot(df, title, **kwargs)
        elif plot_type == "heatmap":
            self._create_heatmap(df, title, **kwargs)
        elif plot_type == "line":
            self._create_line_plot(df, title, **kwargs)
        elif plot_type == "scatter":
            self._create_scatter_plot(df, title, **kwargs)
        
        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
        plt.close()
    
    def _create_bar_plot(self, df: pd.DataFrame, title: str, **kwargs):
        """Create a bar plot with error bars if standard deviation is provided."""
        if 'std' in kwargs:
            ax = df.plot(kind='bar', yerr=kwargs['std'], capsize=5, rot=45)
        else:
            ax = df.plot(kind='bar', rot=45)
        
        plt.title(title)
        plt.xlabel(kwargs.get('xlabel', ''))
        plt.ylabel(kwargs.get('ylabel', 'Score'))
        plt.legend(title=kwargs.get('legend_title', ''), bbox_to_anchor=(1.05, 1))
        plt.tight_layout()
    
    def _create_radar_plot(self, df: pd.DataFrame, title: str, **kwargs):
        """Create a radar plot for comparing multiple metrics."""
        angles = np.linspace(0, 2*np.pi, len(df.index), endpoint=False)
        angles = np.concatenate((angles, [angles[0]]))
        
        fig, ax = plt.subplots(subplot_kw=dict(projection='polar'))
        
        for idx, col in enumerate(df.columns):
            values = df[col].values
            values = np.concatenate((values, [values[0]]))
            ax.plot(angles, values, 'o-', linewidth=2, label=col)
            ax.fill(angles, values, alpha=0.25)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(df.index)
        ax.set_title(title)
        plt.legend(bbox_to_anchor=(0.95, 0.95))
    
    def _create_heatmap(self, df: pd.DataFrame, title: str, **kwargs):
        """Create a heatmap with customizable color scheme."""
        sns.heatmap(
            df,
            annot=True,
            cmap=kwargs.get('cmap', 'YlOrRd'),
            fmt=kwargs.get('fmt', '.3f'),
            cbar_kws={'label': kwargs.get('cbar_label', 'Score')}
        )
        plt.title(title)
        plt.xlabel(kwargs.get('xlabel', ''))
        plt.ylabel(kwargs.get('ylabel', ''))
    
    def _create_line_plot(self, df: pd.DataFrame, title: str, **kwargs):
        """Create a line plot for time series or progression data."""
        for col in df.columns:
            plt.plot(df.index, df[col], marker='o', label=col)
        
        plt.title(title)
        plt.xlabel(kwargs.get('xlabel', 'Time'))
        plt.ylabel(kwargs.get('ylabel', 'Value'))
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.7)
    
    def _create_scatter_plot(self, df: pd.DataFrame, title: str, **kwargs):
        """Create a scatter plot for comparing two metrics."""
        x_col = kwargs.get('x_column', df.columns[0])
        y_col = kwargs.get('y_column', df.columns[1])
        
        plt.scatter(df[x_col], df[y_col])
        plt.title(title)
        plt.xlabel(x_col)
        plt.ylabel(y_col)
    
    def create_comparison_report(
        self,
        results: Dict[str, Any],
        output_dir: str,
        timestamp: bool = True
    ) -> None:
        """
        Generate a comprehensive comparison report with multiple visualizations.
        
        Args:
            results: Dictionary containing all comparison data
            output_dir: Directory to save report files
            timestamp: Whether to include timestamp in filenames
        """
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S") if timestamp else ""
        
        # Create different visualizations based on data type
        for metric_type, data in results.items():
            if isinstance(data, pd.DataFrame) or isinstance(data, dict):
                # Generate appropriate plots based on data characteristics
                if self._is_time_series(data):
                    self.plot_comparison(
                        data,
                        comparison_type=metric_type,
                        plot_type="line",
                        save_path=f"{output_dir}/{metric_type}_timeline_{time_str}.png"
                    )
                
                self.plot_comparison(
                    data,
                    comparison_type=metric_type,
                    plot_type="bar",
                    save_path=f"{output_dir}/{metric_type}_bar_{time_str}.png"
                )
                
                self.plot_comparison(
                    data,
                    comparison_type=metric_type,
                    plot_type="heatmap",
                    save_path=f"{output_dir}/{metric_type}_heatmap_{time_str}.png"
                )
    
    @staticmethod
    def _is_time_series(data: Union[Dict, pd.DataFrame]) -> bool:
        """Check if the data represents a time series."""
        if isinstance(data, pd.DataFrame):
            return isinstance(data.index, pd.DatetimeIndex)
        return False


# Example usage:
"""
visualizer = BenchmarkVisualizer()

# Compare different types of implementations
results = {
    'rag_comparison': {
        'baseline_rag': {'accuracy': 0.8, 'latency': 0.2},
        'graph_rag': {'accuracy': 0.85, 'latency': 0.25}
    },
    'sql_comparison': {
        'llm_generated': {'accuracy': 0.75, 'complexity_handling': 0.8},
        'traditional': {'accuracy': 0.9, 'complexity_handling': 0.7}
    }
}

# Create visualizations for each comparison type
visualizer.plot_comparison(
    results['rag_comparison'],
    comparison_type="RAG Implementations",
    plot_type="bar"
)

visualizer.plot_comparison(
    results['sql_comparison'],
    comparison_type="SQL Query Generation",
    plot_type="radar"
)

# Generate comprehensive report
visualizer.create_comparison_report(results, "benchmark_results")
"""
